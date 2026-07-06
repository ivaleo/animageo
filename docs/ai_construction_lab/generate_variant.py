"""Generate an alternate AI/model variant for construction lab cases.

The script appends variant records to ``assets/library.json`` without replacing
the baseline cases in ``cases.json``. UI feedback is keyed by
``variant::case_id``, so flash and pro evaluations stay separate.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LAB = Path(__file__).resolve().parent
REPO = LAB.parents[1]
CASES_PATH = LAB / "cases.json"
FEEDBACK_DIR = LAB / "feedback"
LIBRARY_PATH = LAB / "assets" / "library.json"
INDEX_PATH = LAB / "index.html"

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(LAB))

from generate_gallery import build_compact_index, ensure_dirs, render_case  # noqa: E402
from regenerate_from_feedback import feedback_by_id, latest_feedback_path, selected_case_ids  # noqa: E402
from serve import _generate_response_from_prompt, _load_env_files, _read_json, _write_json  # noqa: E402


def current_deepseek_model() -> str:
    _load_env_files()
    return (
        os.environ.get("DEEPSEEK_CONSTRUCTION_MODEL")
        or os.environ.get("DEEPSEEK_MODEL")
        or os.environ.get("DEEPSEEK_STYLE_MODEL")
        or "deepseek-v4-pro"
    )


def default_pro_model() -> str:
    model = current_deepseek_model()
    if "flash" in model:
        return model.replace("flash", "pro")
    return os.environ.get("DEEPSEEK_REASONING_MODEL", "deepseek-v4-pro")


def current_kimi_model() -> str:
    _load_env_files()
    return (
        os.environ.get("KIMI_CONSTRUCTION_MODEL")
        or os.environ.get("KIMI_MODEL")
        or os.environ.get("MOONSHOT_MODEL")
        or "kimi-k2.6"
    )


def provider_for_variant(variant: str) -> str:
    if variant == "kimi":
        return "kimi"
    if variant == "openai":
        return "openai"
    return "deepseek"


def default_model(provider: str, variant: str) -> str:
    if provider == "kimi":
        return current_kimi_model()
    if provider == "openai":
        _load_env_files()
        return os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    if variant == "pro":
        return default_pro_model()
    return current_deepseek_model()


def sort_records(records: list[dict[str, Any]], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    case_order = {str(case.get("id") or ""): idx for idx, case in enumerate(cases)}
    variant_order_map = {"flash": 0, "pro": 1, "kimi": 2, "openai": 3}

    def key(record: dict[str, Any]) -> tuple[int, int, str]:
        variant = str(record.get("variant") or "flash")
        variant_order = variant_order_map.get(variant, 100)
        record_id = str(record.get("id") or "")
        return (variant_order, case_order.get(record_id, 10**9), variant)

    return sorted(records, key=key)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="pro")
    parser.add_argument("--provider", choices=("deepseek", "kimi", "openai"), default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--feedback", type=Path, default=None)
    parser.add_argument("--id", dest="ids", action="append", default=[])
    parser.add_argument("--only-ids", action="store_true")
    parser.add_argument("--ratings", default="fail,partial,unsafe")
    parser.add_argument("--include-unset", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=180)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--validation-attempts", type=int, default=1)
    parser.add_argument("--thinking", choices=("enabled", "disabled"), default=None)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    provider = args.provider or provider_for_variant(args.variant)
    model = args.model or default_model(provider, args.variant)
    os.environ["AI_CONSTRUCTION_PROVIDER"] = provider
    if provider == "deepseek":
        os.environ["DEEPSEEK_CONSTRUCTION_MODEL"] = model
        os.environ["DEEPSEEK_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
        if args.thinking is not None:
            os.environ["DEEPSEEK_THINKING"] = args.thinking
        else:
            os.environ.pop("DEEPSEEK_THINKING", None)
        if args.reasoning_effort is not None:
            if args.reasoning_effort:
                os.environ["DEEPSEEK_REASONING_EFFORT"] = args.reasoning_effort
            else:
                os.environ.pop("DEEPSEEK_REASONING_EFFORT", None)
        else:
            os.environ.pop("DEEPSEEK_REASONING_EFFORT", None)
    elif provider == "kimi":
        os.environ["KIMI_CONSTRUCTION_MODEL"] = model
        os.environ["KIMI_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
        if args.thinking is not None:
            os.environ["KIMI_THINKING"] = args.thinking
    elif provider == "openai":
        os.environ["OPENAI_MODEL"] = model
        os.environ["OPENAI_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
        if args.reasoning_effort is not None:
            os.environ["OPENAI_REASONING_EFFORT"] = args.reasoning_effort

    cases_doc = _read_json(CASES_PATH, {"cases": []})
    cases = cases_doc.get("cases", [])
    if not isinstance(cases, list):
        raise SystemExit("cases.json has no cases array")

    feedback_path = args.feedback or latest_feedback_path()
    feedback_doc = json.loads(feedback_path.read_text(encoding="utf-8"))
    feedback = feedback_by_id(feedback_doc)
    ratings = {item.strip() for item in args.ratings.split(",") if item.strip()}
    if args.only_ids:
        selected = [str(case.get("id")) for case in cases if str(case.get("id")) in set(args.ids)]
    else:
        selected = selected_case_ids(cases, feedback, ratings, set(args.ids), args.include_unset)
    if args.limit is not None:
        selected = selected[:args.limit]

    print(f"Variant: {args.variant}", flush=True)
    print(f"Provider: {provider}", flush=True)
    print(f"Model: {model}", flush=True)
    print(f"Feedback: {feedback_path.relative_to(REPO)}", flush=True)
    print(f"Selected: {len(selected)} case(s)", flush=True)
    for case_id in selected:
        print(f"  {case_id}", flush=True)
    if args.dry_run or not selected:
        return

    ensure_dirs()
    selected_set = set(selected)
    records_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    library = _read_json(LIBRARY_PATH, {"records": []})
    for record in library.get("records", []):
        if not isinstance(record, dict):
            continue
        variant = str(record.get("variant") or "flash")
        record_id = str(record.get("id") or "")
        records_by_key[(variant, record_id)] = record

    errors: list[tuple[str, str]] = []
    for index, case in enumerate(cases, start=1):
        case_id = str(case.get("id") or "")
        if case_id not in selected_set:
            continue
        prompt = str(case.get("prompt") or "").strip()
        if not prompt:
            errors.append((case_id, "missing prompt"))
            continue
        print(f"[{index}/{len(cases)}] Generate {args.variant} {case_id}", flush=True)
        last_error: Exception | None = None
        prompt_for_attempt = prompt
        for validation_attempt in range(max(0, args.validation_attempts) + 1):
            record: dict[str, Any] | None = None
            for attempt in range(max(0, args.retries) + 1):
                try:
                    if attempt:
                        print(f"  retry {attempt}/{args.retries}", flush=True)
                    response = _generate_response_from_prompt(prompt_for_attempt)
                    render_id = f"{args.variant}__{case_id}"
                    render_input = {
                        **case,
                        "id": render_id,
                        "response": response,
                    }
                    record = render_case(render_input)
                    record["id"] = case_id
                    record["variant"] = args.variant
                    record["model"] = model
                    record["title"] = case.get("title", case_id)
                    record["prompt"] = prompt
                    record["expected"] = case.get("expected", [])
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    print(f"  ERROR: {exc}", flush=True)
            if record is None:
                break
            validation = [
                item for item in record.get("diagnostics", [])
                if item.get("type") == "validation"
            ]
            if validation and validation_attempt < max(0, args.validation_attempts):
                print(f"  validation retry {validation_attempt + 1}/{args.validation_attempts}", flush=True)
                messages = "\n".join(
                    f"- {item.get('severity', 'warning')}: {item.get('message', item.get('code', 'validation issue'))}"
                    for item in validation
                )
                prompt_for_attempt = (
                    f"{prompt}\n\n"
                    "The previous DSL rendered but failed lab validation. "
                    "Regenerate a corrected AnimaGeo response. Fix all of these diagnostics:\n"
                    f"{messages}"
                )
                continue
            records_by_key[(args.variant, case_id)] = record
            break
        if last_error is not None:
            errors.append((case_id, str(last_error)))

    records = sort_records(list(records_by_key.values()), cases)
    library = {
        "schema": "animageo-ai-construction-lab-library/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context": cases_doc.get("context"),
        "records": records,
    }
    _write_json(LIBRARY_PATH, library)
    INDEX_PATH.write_text(build_compact_index(records, cases_doc), encoding="utf-8")
    rendered = sum(1 for record in records if record.get("status") == "rendered")
    errored = sum(1 for record in records if record.get("status") == "error")
    print(f"Updated: {LIBRARY_PATH.relative_to(REPO)}", flush=True)
    print(f"Updated: {INDEX_PATH.relative_to(REPO)}", flush=True)
    print(f"Rendered records: {rendered}; render errors: {errored}", flush=True)
    if errors:
        print("Generation errors:", flush=True)
        for case_id, message in errors:
            print(f"  {case_id}: {message}", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
