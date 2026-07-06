"""Regenerate AI construction lab cases selected from a feedback export.

Run from the repository root:

    PYTHONPATH=. python3.13 docs/ai_construction_lab/regenerate_from_feedback.py

By default the script uses the latest feedback export and regenerates cases
whose rating is fail/partial/unsafe or whose feedback comment is non-empty.
The reviewer feedback is used only for selecting cases; it is not injected into
the model prompt. This keeps the run a clean test of the current context file.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
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

from generate_gallery import build_compact_index, ensure_dirs, render_case, stable_hash  # noqa: E402
from serve import _generate_response_from_prompt, _read_json, _write_json  # noqa: E402


def latest_feedback_path() -> Path:
    files = sorted(FEEDBACK_DIR.glob("ai-construction-feedback-*.json"), key=lambda path: path.stat().st_mtime)
    if not files:
        raise SystemExit(f"No feedback exports found in {FEEDBACK_DIR}")
    return files[-1]


def feedback_by_id(feedback_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in feedback_doc.get("cases", []):
        case_id = str(item.get("id") or "")
        if case_id:
            result[case_id] = item.get("feedback") if isinstance(item.get("feedback"), dict) else {}
    return result


def has_issue(feedback: dict[str, Any]) -> bool:
    issues = feedback.get("issues")
    return isinstance(issues, dict) and any(value is True for value in issues.values())


def selected_case_ids(
    cases: list[dict[str, Any]],
    feedback: dict[str, dict[str, Any]],
    ratings: set[str],
    explicit_ids: set[str],
    include_unset: bool,
) -> list[str]:
    selected: list[str] = []
    for case in cases:
        case_id = str(case.get("id") or "")
        if not case_id:
            continue
        fb = feedback.get(case_id, {})
        rating = str(fb.get("rating") or "unset")
        comment = str(fb.get("comment") or "").strip()
        if case_id in explicit_ids:
            selected.append(case_id)
        elif rating in ratings:
            selected.append(case_id)
        elif comment or has_issue(fb):
            selected.append(case_id)
        elif include_unset and rating == "unset":
            selected.append(case_id)
    return selected


def record_sort_key(case_order: dict[str, int]):
    def key(record: dict[str, Any]) -> tuple[int, str]:
        record_id = str(record.get("id") or "")
        return (case_order.get(record_id, 10**9), record_id)

    return key


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feedback", type=Path, default=None)
    parser.add_argument("--id", dest="ids", action="append", default=[])
    parser.add_argument("--only-ids", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=None)
    parser.add_argument("--thinking", choices=("enabled", "disabled"), default=None)
    parser.add_argument(
        "--ratings",
        default="fail,partial,unsafe",
        help="Comma-separated ratings to regenerate; comments and issue flags are always included.",
    )
    parser.add_argument("--include-unset", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.timeout_seconds is not None:
        os.environ["DEEPSEEK_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
    if args.thinking is not None:
        os.environ["DEEPSEEK_THINKING"] = args.thinking

    feedback_path = args.feedback or latest_feedback_path()
    feedback_doc = json.loads(feedback_path.read_text(encoding="utf-8"))
    cases_doc = _read_json(CASES_PATH, {"cases": []})
    cases = cases_doc.get("cases", [])
    if not isinstance(cases, list):
        raise SystemExit("cases.json has no cases array")

    feedback = feedback_by_id(feedback_doc)
    ratings = {item.strip() for item in args.ratings.split(",") if item.strip()}
    if args.only_ids:
        selected_ids = [str(case.get("id")) for case in cases if str(case.get("id")) in set(args.ids)]
    else:
        selected_ids = selected_case_ids(cases, feedback, ratings, set(args.ids), args.include_unset)
    print(f"Feedback: {feedback_path.relative_to(REPO)}", flush=True)
    print(f"Selected: {len(selected_ids)} case(s)", flush=True)
    for case_id in selected_ids:
        print(f"  {case_id}", flush=True)
    if args.dry_run or not selected_ids:
        return

    ensure_dirs()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = CASES_PATH.with_name(f"cases.before-regenerate-{stamp}.json")
    shutil.copy2(CASES_PATH, backup)
    print(f"Backup: {backup.relative_to(REPO)}", flush=True)

    selected = set(selected_ids)
    rendered_records: dict[str, dict[str, Any]] = {}
    errors: list[tuple[str, str]] = []

    for index, case in enumerate(cases, start=1):
        case_id = str(case.get("id") or "")
        if case_id not in selected:
            continue
        prompt = str(case.get("prompt") or "").strip()
        if not prompt:
            errors.append((case_id, "missing prompt"))
            continue
        print(f"[{index}/{len(cases)}] Generate {case_id}", flush=True)
        try:
            case["response"] = _generate_response_from_prompt(prompt)
            case["kind"] = case.get("kind") or "create"
            rendered_records[case_id] = render_case(case)
        except Exception as exc:  # noqa: BLE001
            errors.append((case_id, str(exc)))
            print(f"  ERROR: {exc}", flush=True)

    cases_doc["generated_at"] = datetime.now(timezone.utc).date().isoformat()
    _write_json(CASES_PATH, cases_doc)

    library = _read_json(LIBRARY_PATH, {"records": []})
    old_records = {
        str(record.get("id") or ""): record
        for record in library.get("records", [])
        if isinstance(record, dict)
    }
    for case in cases:
        case_id = str(case.get("id") or "")
        if case_id in rendered_records:
            old_records[case_id] = rendered_records[case_id]
        elif case_id not in old_records and isinstance(case.get("response"), dict):
            old_records[case_id] = render_case(case)

    case_order = {str(case.get("id") or ""): idx for idx, case in enumerate(cases)}
    records = sorted(old_records.values(), key=record_sort_key(case_order))
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
    print(f"Updated: {CASES_PATH.relative_to(REPO)}", flush=True)
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
