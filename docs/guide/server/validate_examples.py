"""Validate every interactive example embedded in the guide HTML.

Parses each ``docs/guide/*.html`` chapter, pulls out the ``.ex.interactive``
blocks (their ``data-example`` template + the initial ``<pre><code>`` text),
and renders each Python example through the real ``render_example`` — the same
path the live server uses. Reports which examples render and which throw, so the
guide can be validated against the current code base in one command.

Bash / JSON / non-Python examples (``data-lang`` other than python, or blocks
with no ``data-example``) are skipped — they are static text, not rendered.

    PYTHONPATH=. python3.13 docs/guide/server/validate_examples.py
    PYTHONPATH=. python3.13 docs/guide/server/validate_examples.py 03-dsl.html
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/guide/examples"))

from docs.guide.server.runner import ExampleSpec, render_example  # noqa: E402

GUIDE = REPO / "docs/guide"

# Each interactive render block carries a data-example template. Find every one
# by its attribute, then take the body as the text up to the next data-example
# (or end). The first <pre><code> after the attribute holds the initial code.
_EX_AT = re.compile(r"data-example='([^']*)'")
_LANG = re.compile(r'data-lang="([^"]*)"')
_CODE = re.compile(r"<pre><code>(.*?)</code></pre>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
# A bash/CLI example: the code starts with a shell prompt or `python -m`.
_BASHY = re.compile(r"^\s*(\$|#|pip |python |cd |PYTHONPATH=|export )")


def _strip_tags(s: str) -> str:
    return html.unescape(_TAG.sub("", s))


def iter_examples(html_text: str):
    """Yield (template_dict_or_bad, lang, code) for each data-example block."""
    starts = [m.start() for m in _EX_AT.finditer(html_text)]
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(html_text)
        chunk = html_text[start:end]
        m_ex = _EX_AT.search(chunk)
        try:
            template = json.loads(m_ex.group(1))
        except json.JSONDecodeError:
            template = {"_bad_json": True}
        code_m = _CODE.search(chunk)
        code = _strip_tags(code_m.group(1)).strip("\n") if code_m else ""
        lang_m = _LANG.search(chunk)
        if lang_m:
            lang = lang_m.group(1)
        elif code and _BASHY.match(code):
            lang = "bash"
        elif code.lstrip().startswith(("{", "[")):
            lang = "json"
        else:
            lang = "python"
        yield template, lang, code


def _spec_from(template: dict, code: str) -> ExampleSpec:
    fields = {
        k: template[k]
        for k in (
            "w", "h", "scale", "labels", "tex_labels", "hide", "overrides",
            "rendering_extra", "overlay_extra", "auto_place", "style",
        )
        if k in template
    }
    return ExampleSpec(code=code, **fields)


def validate(files):
    total = ok = skipped = failed = 0
    failures = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        idx = 0
        for template, lang, code in iter_examples(text):
            idx += 1
            tag = f"{path.name}#{idx}"
            if template.get("_bad_json"):
                failed += 1
                failures.append((tag, "bad data-example JSON"))
                continue
            if lang != "python" or not code:
                skipped += 1
                continue
            total += 1
            try:
                svg = render_example(_spec_from(template, code))
                if not svg.lstrip().startswith("<?xml"):
                    raise ValueError("output is not SVG")
                ok += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                failures.append((tag, f"{type(e).__name__}: {e}"))
    return total, ok, skipped, failed, failures


def main(argv):
    if argv:
        files = [GUIDE / a for a in argv]
    else:
        files = sorted(GUIDE.glob("*.html"))
    total, ok, skipped, failed, failures = validate(files)
    print(f"rendered {ok}/{total} python examples ok | "
          f"{skipped} non-python skipped | {failed} failed")
    for tag, why in failures:
        print(f"  FAIL {tag}: {why}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
