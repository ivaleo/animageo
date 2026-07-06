"""Serve the AI construction lab and save feedback exports locally.

Run from the repository root:

    PYTHONPATH=. python3.13 docs/ai_construction_lab/serve.py --port 8765

Then open:

    http://127.0.0.1:8765/
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LAB = Path(__file__).resolve().parent
REPO = LAB.parents[1]
FEEDBACK = LAB / "feedback"
CASES_PATH = LAB / "cases.json"
LIBRARY_PATH = LAB / "assets" / "library.json"
INDEX_PATH = LAB / "index.html"
CONTEXT_PATH = LAB.parent / "ai_construction_generation_context.md"
MAX_BODY_BYTES = 2_000_000
SCHEMA = "animageo-ai-construction-lab-feedback/v1"
ADD_CASE_SCHEMA = "animageo-ai-construction-lab-add-case/v1"
AI_RESPONSE_SCHEMA = "animageo-ai-construction-response/v1"
ENV_PATHS = (
    REPO / ".env",
    LAB / ".env",
    REPO.parent / "animageo_web" / ".env",
    Path.home() / ".animageo.env",
    Path.home() / ".config" / "animageo" / ".env",
)


def _feedback_filename(doc: dict) -> str:
    stamp = doc.get("exported_at") or datetime.now(timezone.utc).isoformat()
    stamp = re.sub(r"[^0-9A-Za-z_-]+", "-", str(stamp)).strip("-")
    if not stamp:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    return f"ai-construction-feedback-{stamp}.json"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(2, 1000):
        candidate = path.with_name(f"{stem}-{idx}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate a unique feedback filename for {path.name}")


def _read_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^0-9a-zA-Zа-яА-ЯёЁ]+", "_", value, flags=re.IGNORECASE).strip("_")
    value = re.sub(r"_+", "_", value)
    if not value:
        value = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return "manual_" + value[:56]


def _safe_case_id(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z_-]+", "_", value).strip("_")
    if not value:
        value = datetime.now(timezone.utc).strftime("manual_%Y%m%d_%H%M%S")
    if not value.startswith("manual_"):
        value = "manual_" + value
    return value[:80]


def _unique_case_id(cases: list[dict], requested: str) -> str:
    base = _safe_case_id(requested)
    used = {str(case.get("id")) for case in cases}
    if base not in used:
        return base
    for idx in range(2, 1000):
        candidate = f"{base}_{idx}"
        if candidate not in used:
            return candidate
    raise RuntimeError(f"could not allocate unique case id for {base}")


def _split_lines(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _load_env_files() -> None:
    extra_env = os.environ.get("ANIMAGEO_LAB_ENV")
    paths = list(ENV_PATHS)
    if extra_env:
        paths.insert(0, Path(extra_env).expanduser())

    for path in paths:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key.split(None, 1)[1].strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _key_lookup_hint(names: tuple[str, ...]) -> str:
    paths = list(ENV_PATHS)
    extra_env = os.environ.get("ANIMAGEO_LAB_ENV")
    if extra_env:
        paths.insert(0, Path(extra_env).expanduser())
    env_paths = ", ".join(str(path) for path in paths)
    names_text = ", ".join(names)
    return (
        f"checked process env vars [{names_text}] and .env files [{env_paths}] "
        f"for server pid {os.getpid()}"
    )


def _extract_output_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]

    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                chunks.append(content["text"])
            if content.get("type") == "refusal":
                raise ValueError(f"model refusal: {content.get('refusal', '')}")
    text = "".join(chunks).strip()
    if not text:
        raise ValueError("model response did not contain output_text")
    return text


def _parse_model_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("AI response must be a JSON object")
    return parsed


def _validate_ai_response(response: dict) -> dict:
    dsl = str(response.get("construction_dsl") or "").strip()
    if not dsl:
        raise ValueError("AI response is missing construction_dsl")
    mode = response.get("mode") or "create"
    if mode not in {"create", "patch", "replace"}:
        raise ValueError(f"unsupported AI response mode: {mode}")
    notes = _split_lines(response.get("notes"))
    return {
        "schema": response.get("schema") or AI_RESPONSE_SCHEMA,
        "mode": mode,
        "construction_dsl": dsl,
        "style": response.get("style"),
        "notes": notes,
    }


def _env_first(*names: str) -> str | None:
    _load_env_files()
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _ai_instructions() -> str:
    return CONTEXT_PATH.read_text(encoding="utf-8") + (
        "\n\nReturn exactly one JSON object matching the AnimaGeo construction "
        "response contract. Do not wrap it in Markdown fences. The JSON object "
        "must contain construction_dsl."
    )


def _post_json(url: str, payload: dict, api_key: str, timeout: float, provider: str) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"{provider} API error {exc.code}: {body}") from exc
    except URLError as exc:
        raise ValueError(f"{provider} API request failed: {exc.reason}") from exc


def _extract_chat_completion_text(response: dict) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("model response did not contain choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ValueError("model response did not contain message")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        text = "".join(chunks).strip()
        if text:
            return text
    raise ValueError("model response did not contain message content")


def _generate_with_deepseek(prompt: str) -> dict:
    key_names = ("DEEPSEEK_API_KEY", "deepseek_api", "DEEPSEEK_API", "DEEPSEEK_KEY")
    api_key = _env_first(*key_names)
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is required for prompt-only generation "
            "(also accepts deepseek_api, DEEPSEEK_API, or DEEPSEEK_KEY); "
            + _key_lookup_hint(key_names)
        )

    model = (
        os.environ.get("DEEPSEEK_CONSTRUCTION_MODEL")
        or os.environ.get("DEEPSEEK_MODEL")
        or os.environ.get("DEEPSEEK_STYLE_MODEL")
        or "deepseek-v4-pro"
    )
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    timeout = float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "180"))
    thinking = os.environ.get("DEEPSEEK_THINKING", "disabled").strip().lower()
    effort = os.environ.get("DEEPSEEK_REASONING_EFFORT", "").strip()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _ai_instructions()},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "temperature": float(os.environ.get("DEEPSEEK_TEMPERATURE", "0.2")),
        "max_tokens": int(os.environ.get("DEEPSEEK_MAX_TOKENS", "6000")),
    }
    if thinking in {"enabled", "disabled"}:
        payload["thinking"] = {"type": thinking}
    if effort:
        payload["reasoning_effort"] = effort

    api_response = _post_json(
        f"{base_url}/chat/completions",
        payload,
        api_key,
        timeout,
        "DeepSeek",
    )
    return _validate_ai_response(_parse_model_json(_extract_chat_completion_text(api_response)))


def _generate_with_kimi(prompt: str) -> dict:
    key_names = ("KIMI_API_KEY", "MOONSHOT_API_KEY", "moonshot_api", "KIMI_KEY", "MOONSHOT_KEY")
    api_key = _env_first(*key_names)
    if not api_key:
        raise ValueError(
            "KIMI_API_KEY is required for prompt-only generation "
            "(also accepts MOONSHOT_API_KEY, moonshot_api, KIMI_KEY, or MOONSHOT_KEY); "
            + _key_lookup_hint(key_names)
        )

    model = (
        os.environ.get("KIMI_CONSTRUCTION_MODEL")
        or os.environ.get("KIMI_MODEL")
        or os.environ.get("MOONSHOT_MODEL")
        or "kimi-k2.6"
    )
    configured_base_url = os.environ.get("KIMI_BASE_URL") or os.environ.get("MOONSHOT_BASE_URL")
    if configured_base_url:
        base_urls = [configured_base_url.rstrip("/")]
    else:
        # Kimi has independent international and mainland China platforms; keys
        # from one platform return 401 on the other.
        base_urls = ["https://api.moonshot.ai/v1", "https://api.moonshot.cn/v1"]
    timeout = float(os.environ.get("KIMI_TIMEOUT_SECONDS", "180"))
    thinking = os.environ.get("KIMI_THINKING", "disabled").strip().lower()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _ai_instructions()},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "temperature": float(os.environ.get("KIMI_TEMPERATURE", "0.2")),
        "max_completion_tokens": int(os.environ.get("KIMI_MAX_TOKENS", "6000")),
    }
    if thinking in {"enabled", "disabled"}:
        payload["thinking"] = {"type": thinking}

    last_auth_error: Exception | None = None
    for base_url in base_urls:
        chat_url = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
        try:
            api_response = _post_json(
                chat_url,
                payload,
                api_key,
                timeout,
                "Kimi",
            )
            break
        except ValueError as exc:
            if "Kimi API error 401" not in str(exc) or configured_base_url:
                raise
            last_auth_error = exc
    else:
        raise ValueError(
            "Kimi API authentication failed on both supported platforms "
            "(https://api.moonshot.ai/v1 and https://api.moonshot.cn/v1). "
            "Set KIMI_BASE_URL explicitly if this key belongs to a third-party endpoint."
        ) from last_auth_error
    return _validate_ai_response(_parse_model_json(_extract_chat_completion_text(api_response)))


def _generate_with_openai(prompt: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for prompt-only generation")

    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    timeout = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "120"))
    effort = os.environ.get("OPENAI_REASONING_EFFORT", "medium").strip()
    payload = {
        "model": model,
        "store": False,
        "instructions": _ai_instructions(),
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    if effort:
        payload["reasoning"] = {"effort": effort}

    api_response = _post_json(
        f"{base_url}/responses",
        payload,
        api_key,
        timeout,
        "OpenAI",
    )
    return _validate_ai_response(_parse_model_json(_extract_output_text(api_response)))


def _generate_response_from_prompt(prompt: str) -> dict:
    provider = os.environ.get("AI_CONSTRUCTION_PROVIDER", "auto").strip().lower()
    if provider in {"deepseek", "ds"}:
        return _generate_with_deepseek(prompt)
    if provider in {"kimi", "moonshot"}:
        return _generate_with_kimi(prompt)
    if provider in {"openai", "oa"}:
        return _generate_with_openai(prompt)
    if provider != "auto":
        raise ValueError("AI_CONSTRUCTION_PROVIDER must be auto, deepseek, kimi, or openai")

    deepseek_key_names = ("DEEPSEEK_API_KEY", "deepseek_api", "DEEPSEEK_API", "DEEPSEEK_KEY")
    kimi_key_names = ("KIMI_API_KEY", "MOONSHOT_API_KEY", "moonshot_api", "KIMI_KEY", "MOONSHOT_KEY")
    if _env_first(*deepseek_key_names):
        return _generate_with_deepseek(prompt)
    if _env_first(*kimi_key_names):
        return _generate_with_kimi(prompt)
    if os.environ.get("OPENAI_API_KEY"):
        return _generate_with_openai(prompt)
    raise ValueError(
        "DeepSeek or Kimi API key is required for prompt-only generation "
        "(set DEEPSEEK_API_KEY/deepseek_api or KIMI_API_KEY); "
        + _key_lookup_hint(deepseek_key_names + kimi_key_names)
    )


def _coerce_add_case(doc: dict) -> dict:
    if doc.get("schema") not in (None, ADD_CASE_SCHEMA):
        raise ValueError("invalid add-case schema")

    prompt = str(doc.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    response = doc.get("response")
    if response is None and isinstance(doc.get("response_json"), str) and doc["response_json"].strip():
        response = json.loads(doc["response_json"])
    if response is None and (
        doc.get("construction_dsl") is None
        or not str(doc.get("construction_dsl") or "").strip()
    ):
        response = _generate_response_from_prompt(prompt)
    elif response is None:
        response = {
            "schema": AI_RESPONSE_SCHEMA,
            "mode": "create",
            "construction_dsl": doc.get("construction_dsl"),
            "style": doc.get("style"),
            "notes": _split_lines(doc.get("notes")),
        }
    if not isinstance(response, dict):
        raise ValueError("response must be an object")

    response = _validate_ai_response(response)

    title = str(doc.get("title") or prompt[:72] or "Manual Case").strip()
    viewport = doc.get("viewport") if isinstance(doc.get("viewport"), dict) else {}
    return {
        "id": str(doc.get("id") or _slug(title or prompt)),
        "title": title,
        "kind": "manual",
        "prompt": prompt,
        "expected": _split_lines(doc.get("expected")),
        "viewport": {
            "width": int(viewport.get("width", 700)),
            "height": int(viewport.get("height", 460)),
            "scale": float(viewport.get("scale", 56)),
        },
        "response": response,
    }


def _append_and_render_case(case: dict) -> tuple[dict, dict]:
    from generate_gallery import build_compact_index, ensure_dirs, render_case

    ensure_dirs()
    cases_doc = _read_json(CASES_PATH, {
        "schema": "animageo-ai-construction-lab-cases/v1",
        "generated_at": datetime.now(timezone.utc).date().isoformat(),
        "context": "../ai_construction_generation_context.md",
        "cases": [],
    })
    cases = cases_doc.setdefault("cases", [])
    case["id"] = _unique_case_id(cases, case.get("id") or _slug(case.get("title", "")))
    cases.append(case)
    _write_json(CASES_PATH, cases_doc)

    record = render_case(case)

    library = _read_json(LIBRARY_PATH, {
        "schema": "animageo-ai-construction-lab-library/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context": cases_doc.get("context"),
        "records": [],
    })
    records = [rec for rec in library.get("records", []) if rec.get("id") != record["id"]]
    records.insert(0, record)
    library = {
        "schema": "animageo-ai-construction-lab-library/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context": cases_doc.get("context"),
        "records": records,
    }
    _write_json(LIBRARY_PATH, library)
    INDEX_PATH.write_text(build_compact_index(records, cases_doc), encoding="utf-8")
    return case, record


class LabHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(LAB), **kwargs)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/feedback":
            self._handle_feedback_post(parsed)
            return
        if parsed.path == "/cases":
            self._handle_case_post(parsed)
            return
        self._send_json({"ok": False, "error": "unknown endpoint"}, status=404)

    def _read_body_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"ok": False, "error": "invalid Content-Length"}, status=400)
            return None
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json({"ok": False, "error": "invalid payload size"}, status=413)
            return None

        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            self._send_json({"ok": False, "error": f"invalid JSON: {exc}"}, status=400)
            return None

    def _handle_feedback_post(self, parsed) -> None:
        doc = self._read_body_json()
        if doc is None:
            return

        if doc.get("schema") != SCHEMA or not isinstance(doc.get("cases"), list):
            self._send_json({"ok": False, "error": "invalid feedback schema"}, status=400)
            return

        filename = _feedback_filename(doc)
        path = _unique_path(FEEDBACK / filename)
        dry_run = parse_qs(parsed.query).get("dry_run") == ["1"]
        if not dry_run:
            FEEDBACK.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        self._send_json({
            "ok": True,
            "dry_run": dry_run,
            "filename": path.name,
            "path": str(path.relative_to(LAB)),
        })

    def _handle_case_post(self, parsed) -> None:
        doc = self._read_body_json()
        if doc is None:
            return

        try:
            dry_run = parse_qs(parsed.query).get("dry_run") == ["1"]
            if dry_run and not any(
                str(doc.get(key) or "").strip()
                for key in ("response_json", "construction_dsl")
            ) and not isinstance(doc.get("response"), dict):
                prompt = str(doc.get("prompt") or "").strip()
                if not prompt:
                    raise ValueError("prompt is required")
                self._send_json({"ok": True, "dry_run": True, "would_generate": True, "prompt": prompt})
                return
            case = _coerce_add_case(doc)
            if dry_run:
                self._send_json({"ok": True, "dry_run": True, "case": case})
                return
            case, record = _append_and_render_case(case)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)
            return

        self._send_json({"ok": True, "case": case, "record": record})

    def _send_json(self, payload: dict, *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    FEEDBACK.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), LabHandler)
    print(f"AI construction lab: http://{args.host}:{args.port}/")
    print(f"Feedback saves to: {FEEDBACK.relative_to(LAB)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
