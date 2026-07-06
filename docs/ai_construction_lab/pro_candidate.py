"""Generate/review/promote a single pro candidate without immediate gallery write."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LAB = Path(__file__).resolve().parent
REPO = LAB.parents[1]
CASES_PATH = LAB / "cases.json"
LIBRARY_PATH = LAB / "assets" / "library.json"
INDEX_PATH = LAB / "index.html"
CANDIDATES = LAB / "candidates"

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(LAB))

from generate_gallery import build_compact_index, ensure_dirs, render_case  # noqa: E402
from generate_variant import sort_records  # noqa: E402
from serve import _generate_response_from_prompt, _read_json, _write_json  # noqa: E402


def find_case(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    for case in cases:
        if str(case.get("id")) == case_id:
            return case
    raise SystemExit(f"case not found: {case_id}")


def candidate_paths(variant: str, case_id: str) -> tuple[Path, Path]:
    return CANDIDATES / f"{variant}__{case_id}.json", CANDIDATES / f"{variant}__{case_id}.py"


def write_candidate(path: Path, dsl_path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dsl_path.write_text(payload["response"]["construction_dsl"].strip() + "\n", encoding="utf-8")


def promote_candidate(path: Path, variant: str, model: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases_doc = _read_json(CASES_PATH, {"cases": []})
    cases = cases_doc.get("cases", [])
    case = find_case(cases, payload["case_id"])
    render_id = f"{variant}__{payload['case_id']}"
    render_input = {**case, "id": render_id, "response": payload["response"]}
    record = render_case(render_input)
    record["id"] = payload["case_id"]
    record["variant"] = variant
    record["model"] = model
    record["title"] = case.get("title", payload["case_id"])
    record["prompt"] = case.get("prompt", "")
    record["expected"] = case.get("expected", [])

    library = _read_json(LIBRARY_PATH, {"records": []})
    records_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for old in library.get("records", []):
        if not isinstance(old, dict):
            continue
        old_variant = str(old.get("variant") or "flash")
        old_id = str(old.get("id") or "")
        if (old_variant, old_id) == (variant, payload["case_id"]):
            continue
        records_by_key[(old_variant, old_id)] = old
    records_by_key[(variant, payload["case_id"])] = record
    records = sort_records(list(records_by_key.values()), cases)
    library = {
        "schema": "animageo-ai-construction-lab-library/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context": cases_doc.get("context"),
        "records": records,
    }
    _write_json(LIBRARY_PATH, library)
    INDEX_PATH.write_text(build_compact_index(records, cases_doc), encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--variant", default="pro")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()

    json_path, dsl_path = candidate_paths(args.variant, args.case_id)
    if args.promote:
        record = promote_candidate(json_path, args.variant, args.model)
        print(json.dumps({
            "promoted": str(json_path.relative_to(REPO)),
            "status": record.get("status"),
            "diagnostics": record.get("diagnostics", []),
        }, ensure_ascii=False, indent=2))
        return

    os.environ["DEEPSEEK_CONSTRUCTION_MODEL"] = args.model
    os.environ["DEEPSEEK_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
    os.environ.pop("DEEPSEEK_THINKING", None)
    os.environ.pop("DEEPSEEK_REASONING_EFFORT", None)

    cases_doc = _read_json(CASES_PATH, {"cases": []})
    case = find_case(cases_doc.get("cases", []), args.case_id)
    response = None
    last_error: Exception | None = None
    for attempt in range(1, max(1, args.retries) + 1):
        try:
            response = _generate_response_from_prompt(str(case.get("prompt") or ""))
            break
        except Exception as exc:  # noqa: BLE001 - lab tool should retry transient provider failures.
            last_error = exc
            if attempt >= max(1, args.retries):
                raise
            print(
                f"generation attempt {attempt} failed: {exc.__class__.__name__}: {exc}; retrying",
                file=sys.stderr,
            )
            time.sleep(min(2 * attempt, 8))
    if response is None:
        raise RuntimeError("generation did not return a response") from last_error
    payload = {
        "schema": "animageo-ai-construction-lab-candidate/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": args.case_id,
        "variant": args.variant,
        "model": args.model,
        "prompt": case.get("prompt", ""),
        "expected": case.get("expected", []),
        "response": response,
    }
    ensure_dirs()
    write_candidate(json_path, dsl_path, payload)
    print(json.dumps({
        "candidate": str(json_path.relative_to(REPO)),
        "dsl": str(dsl_path.relative_to(REPO)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
