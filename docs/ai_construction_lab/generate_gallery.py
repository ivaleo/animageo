"""Generate the AI construction lab gallery.

Run from the repository root:

    PYTHONPATH=. python3 docs/ai_construction_lab/generate_gallery.py
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
LAB = Path(__file__).resolve().parent
CASES_PATH = LAB / "cases.json"
ASSETS = LAB / "assets"
RESULTS = ASSETS / "results"
DSL_OUT = ASSETS / "dsl"
LIBRARY_PATH = ASSETS / "library.json"
INDEX_PATH = LAB / "index.html"

sys.path.insert(0, str(REPO))

logging.getLogger().setLevel(logging.ERROR)
for noisy in ["manim", "animageo", "animageo.parsers.ggb_parser"]:
    logging.getLogger(noisy).setLevel(logging.ERROR)

from manim import config  # noqa: E402

config.pixel_width = 820
config.pixel_height = 520
config.verbosity = "ERROR"

from animageo.animageo import AnimaGeoScene  # noqa: E402
from validate_library import validate_record  # noqa: E402


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def read_cases() -> dict[str, Any]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def ensure_dirs() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    DSL_OUT.mkdir(parents=True, exist_ok=True)
    (LAB / "feedback").mkdir(parents=True, exist_ok=True)


def apply_viewport(scene: AnimaGeoScene, viewport: dict[str, Any], style: Any) -> tuple[int, int, float]:
    width = int(viewport.get("width", 640))
    height = int(viewport.get("height", 420))
    scale = float(viewport.get("scale", 58))
    scene.style.export["ptUnit"] = scale
    scene.style.export["ptWidth"] = width
    scene.style.export["ptHeight"] = height
    scene.style.export["ptXZero"] = width / 2
    scene.style.export["ptYZero"] = height / 2
    scene.applyStyle(style=style, export={"size": {"width": width, "height": height}})
    return width, height, scale


def fit_rendered_bounds(scene: AnimaGeoScene, viewport: dict[str, Any], style: Any) -> tuple[int, int, float]:
    width = int(viewport.get("width", 700))
    height = int(viewport.get("height", 460))
    padding = float(viewport.get("bounds_padding", 24))
    scene.applyStyle(
        style=style,
        content={
            "source": "rendered_bounds",
            "fit": "contain",
            "padding": padding,
            "infinite_policy": viewport.get("bounds_infinite_policy", "ignore"),
        },
        export={"size": {"width": width, "height": height}},
    )
    export = scene.style.export
    return int(export.get("ptWidth", width)), int(export.get("ptHeight", height)), float(export.get("ptUnit", 1))


def render_case(case: dict[str, Any]) -> dict[str, Any]:
    response = case["response"]
    code = response["construction_dsl"].strip() + "\n"
    style = response.get("style")
    case_id = case["id"]
    svg_path = RESULTS / f"{case_id}.svg"
    dsl_path = DSL_OUT / f"{case_id}.py"
    dsl_path.write_text(code, encoding="utf-8")

    record: dict[str, Any] = {
        "id": case_id,
        "title": case.get("title", case_id),
        "variant": case.get("variant", "flash"),
        "model": case.get("model", "deepseek-v4-flash"),
        "kind": case.get("kind", "create"),
        "prompt": case.get("prompt", ""),
        "expected": case.get("expected", []),
        "mode": response.get("mode"),
        "notes": response.get("notes", []),
        "style": style,
        "dsl": code,
        "dsl_path": str(dsl_path.relative_to(LAB)),
        "svg_path": str(svg_path.relative_to(LAB)),
        "hash": stable_hash({"dsl": code, "style": style}),
        "status": "pending",
        "diagnostics": [],
    }

    try:
        scene = AnimaGeoScene()
        width, height, scale = apply_viewport(scene, case.get("viewport", {}), style)
        record["viewport"] = {"width": width, "height": height, "scale": scale}
        scene.putCode(code)
        scene.addAllGeometry(show=True)
        scene.updateAllGeometry()
        if case.get("auto_place_labels", True):
            try:
                scene.autoPlaceLabels()
            except Exception as exc:
                record["diagnostics"].append({
                    "type": "autoplace_warning",
                    "message": str(exc),
                })
        if case.get("fit_rendered_bounds", True):
            width, height, scale = fit_rendered_bounds(scene, case.get("viewport", {}), style)
            record["viewport"] = {"width": width, "height": height, "scale": scale}
            scene.updateAllGeometry()
        scene.exportSVG(str(svg_path))
        record["summary"] = {
            "schema": "animageo-construction-render-summary/v1",
            "element_count": len(scene.geo.elements),
            "diagnostics": [],
        }
        record["status"] = "rendered"
    except Exception as exc:
        record["status"] = "error"
        record["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=8),
        }
        error_svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" '
            f'viewBox="0 0 640 420"><rect width="640" height="420" fill="#fff3f3"/>'
            f'<text x="24" y="48" font-family="monospace" font-size="18" fill="#a00000">'
            f'{html.escape(type(exc).__name__)}</text>'
            f'<text x="24" y="82" font-family="monospace" font-size="14" fill="#333">'
            f'{html.escape(str(exc)[:120])}</text></svg>'
        )
        svg_path.write_text(error_svg, encoding="utf-8")
    record["diagnostics"].extend(validate_record(record))
    return record


def render_all(cases_doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [render_case(case) for case in cases_doc.get("cases", [])]


def build_index(records: list[dict[str, Any]], cases_doc: dict[str, Any]) -> str:
    payload = {
        "schema": "animageo-ai-construction-lab-library/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context": cases_doc.get("context"),
        "records": records,
    }
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AnimaGeo AI Construction Lab</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f6f7f9;
  --paper: #ffffff;
  --ink: #1f2328;
  --muted: #667085;
  --line: #d9dee7;
  --accent: #1f77b4;
  --bad: #b42318;
  --good: #067647;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
header {{
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(255,255,255,.94);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(8px);
}}
.bar {{
  max-width: 1380px;
  margin: 0 auto;
  padding: 14px 18px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 16px;
  align-items: center;
}}
h1 {{
  font-size: 20px;
  margin: 0;
  letter-spacing: 0;
}}
.sub {{ color: var(--muted); margin-top: 2px; }}
.actions {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
button, select, input[type="search"] {{
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  border-radius: 6px;
  padding: 8px 10px;
  font: inherit;
}}
button.primary {{
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}}
main {{
  max-width: 1380px;
  margin: 0 auto;
  padding: 18px;
}}
.stats {{
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  color: var(--muted);
}}
.case {{
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-bottom: 18px;
  overflow: hidden;
}}
.case-head {{
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: start;
}}
.case-title {{
  font-size: 17px;
  font-weight: 650;
  margin: 0 0 6px;
}}
.prompt {{ margin: 0; color: #344054; }}
.badges {{ display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }}
.badge {{
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 8px;
  color: var(--muted);
  white-space: nowrap;
  font-size: 12px;
}}
.case-grid {{
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(360px, 1fr);
  gap: 0;
}}
.pane {{
  padding: 14px 16px;
  min-width: 0;
}}
.pane + .pane {{ border-left: 1px solid var(--line); }}
.svg-wrap {{
  background: #fbfbfc;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px;
  min-height: 280px;
  display: grid;
  place-items: center;
}}
.svg-wrap img {{
  max-width: 100%;
  height: auto;
  display: block;
}}
h2 {{
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: var(--muted);
  margin: 0 0 8px;
}}
pre {{
  overflow: auto;
  margin: 0;
  padding: 12px;
  background: #0f172a;
  color: #e6edf7;
  border-radius: 6px;
  font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  max-height: 420px;
}}
.notes, .expected {{
  margin: 0 0 12px;
  padding-left: 18px;
  color: #344054;
}}
.feedback {{
  border-top: 1px solid var(--line);
  padding: 14px 16px;
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 14px;
  background: #fcfcfd;
}}
.checks {{
  display: grid;
  grid-template-columns: repeat(3, minmax(160px, 1fr));
  gap: 8px 12px;
}}
label.check {{ color: #344054; }}
textarea {{
  width: 100%;
  min-height: 82px;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 9px 10px;
  font: inherit;
}}
.saved {{ color: var(--good); font-size: 12px; min-height: 18px; }}
.hidden {{ display: none; }}
@media (max-width: 900px) {{
  .bar, .case-head, .feedback {{ grid-template-columns: 1fr; }}
  .case-grid {{ grid-template-columns: 1fr; }}
  .pane + .pane {{ border-left: 0; border-top: 1px solid var(--line); }}
  .checks {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<header>
  <div class="bar">
    <div>
      <h1>AnimaGeo AI Construction Lab</h1>
      <div class="sub">Запросы, AI DSL, SVG и ручная обратная связь</div>
    </div>
    <div class="actions">
      <input id="search" type="search" placeholder="Search">
      <select id="statusFilter">
        <option value="">All statuses</option>
        <option value="unset">Unset</option>
        <option value="pass">Pass</option>
        <option value="partial">Partial</option>
        <option value="fail">Fail</option>
        <option value="unsafe">Unsafe</option>
      </select>
      <button id="importBtn">Import feedback</button>
      <button class="primary" id="exportBtn">Export feedback</button>
      <input id="importFile" type="file" accept="application/json" class="hidden">
    </div>
  </div>
</header>
<main>
  <details class="add-case" id="addCasePanel">
    <summary>Generate manual case</summary>
    <form id="addCaseForm">
      <div class="add-grid">
        <label class="field"><span>Title</span><input id="addTitle" type="text" placeholder="Optional"></label>
        <label class="field field-wide"><span>Prompt</span><textarea id="addPrompt" required placeholder="Запрос пользователя. Сервер вызовет AI с текущим context-файлом и отрендерит SVG."></textarea></label>
        <details class="field field-wide advanced-add">
          <summary>Advanced: paste AI response JSON or construction DSL instead of calling AI</summary>
          <textarea id="addResponse" class="mono-input" placeholder='{"schema":"animageo-ai-construction-response/v1","mode":"create","construction_dsl":"A = Point(0, 0)\\n...","style":null,"notes":[]}'></textarea>
        </details>
      </div>
      <div class="add-actions"><button class="primary" type="submit">Generate and render</button><span id="addCaseStatus" class="add-status"></span></div>
    </form>
  </details>
  <div class="stats" id="stats"></div>
  <div id="cases"></div>
</main>
<script id="library-data" type="application/json">{data_json}</script>
<script>
(function () {{
  "use strict";
  const payload = JSON.parse(document.getElementById("library-data").textContent);
  const records = payload.records || [];
  const storageKey = "animageo-ai-construction-lab-feedback-v1";
  const issueKeys = [
    ["construction_error", "Ошибка конструкции"],
    ["style_misuse", "Стиль засунут в DSL"],
    ["unsupported", "Неподдержано"],
    ["ambiguity", "Не снята неоднозначность"],
    ["naming", "Проблемы с именами"],
    ["good_pattern", "Хороший паттерн"]
  ];

  function loadFeedback() {{
    try {{ return JSON.parse(localStorage.getItem(storageKey) || "{{}}"); }}
    catch (_) {{ return {{}}; }}
  }}
  let feedback = loadFeedback();

  function saveFeedback() {{
    localStorage.setItem(storageKey, JSON.stringify(feedback));
  }}

  function escapeHtml(s) {{
    return String(s || "").replace(/[&<>"]/g, ch => ({{
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"
    }}[ch]));
  }}

  function caseFeedback(id) {{
    if (!feedback[id]) feedback[id] = {{ rating: "unset", issues: {{}}, comment: "" }};
    return feedback[id];
  }}

  function renderCase(rec) {{
    const fb = caseFeedback(rec.id);
    const card = document.createElement("section");
    card.className = "case";
    card.dataset.id = rec.id;
    card.dataset.search = [rec.id, rec.title, rec.prompt, rec.kind, rec.mode].join(" ").toLowerCase();

    const expected = (rec.expected || []).map(x => `<li>${{escapeHtml(x)}}</li>`).join("");
    const notes = (rec.notes || []).map(x => `<li>${{escapeHtml(x)}}</li>`).join("");
    const issueControls = issueKeys.map(([key, label]) => `
      <label class="check"><input type="checkbox" data-issue="${{key}}" ${{fb.issues && fb.issues[key] ? "checked" : ""}}> ${{escapeHtml(label)}}</label>
    `).join("");
    const styleBlock = rec.style ? `<h2>Style JSON</h2><pre>${{escapeHtml(JSON.stringify(rec.style, null, 2))}}</pre>` : "";
    const errorBlock = rec.error ? `<h2>Render Error</h2><pre>${{escapeHtml(JSON.stringify(rec.error, null, 2))}}</pre>` : "";

    card.innerHTML = `
      <div class="case-head">
        <div>
          <h2>${{escapeHtml(rec.id)}}</h2>
          <div class="case-title">${{escapeHtml(rec.title)}}</div>
          <p class="prompt">${{escapeHtml(rec.prompt)}}</p>
        </div>
        <div class="badges">
          <span class="badge">${{escapeHtml(rec.kind)}}</span>
          <span class="badge">${{escapeHtml(rec.mode)}}</span>
          <span class="badge">${{escapeHtml(rec.status)}}</span>
          <span class="badge">${{escapeHtml(rec.hash)}}</span>
        </div>
      </div>
      <div class="case-grid">
        <div class="pane">
          <h2>SVG</h2>
          <div class="svg-wrap"><img src="${{escapeHtml(rec.svg_path)}}?h=${{escapeHtml(rec.hash)}}" alt="${{escapeHtml(rec.title)}}"></div>
        </div>
        <div class="pane">
          <h2>Expected Checks</h2>
          <ul class="expected">${{expected}}</ul>
          <h2>Notes</h2>
          <ul class="notes">${{notes}}</ul>
          <h2>Construction DSL</h2>
          <pre>${{escapeHtml(rec.dsl)}}</pre>
          ${{styleBlock}}
          ${{errorBlock}}
        </div>
      </div>
      <div class="feedback">
        <div>
          <h2>Manual Rating</h2>
          <select data-rating>
            <option value="unset">Unset</option>
            <option value="pass">Pass</option>
            <option value="partial">Partial</option>
            <option value="fail">Fail</option>
            <option value="unsafe">Unsafe</option>
          </select>
          <div class="saved" data-saved></div>
        </div>
        <div>
          <h2>Issues</h2>
          <div class="checks">${{issueControls}}</div>
          <h2 style="margin-top:12px">Comment</h2>
          <textarea data-comment placeholder="Что неверно, что улучшить в context-файле или validator?">${{escapeHtml(fb.comment || "")}}</textarea>
        </div>
      </div>
    `;
    card.querySelector("[data-rating]").value = fb.rating || "unset";

    card.addEventListener("input", function (event) {{
      const current = caseFeedback(rec.id);
      const target = event.target;
      if (target.matches("[data-rating]")) current.rating = target.value;
      if (target.matches("[data-comment]")) current.comment = target.value;
      if (target.matches("[data-issue]")) {{
        current.issues[target.dataset.issue] = target.checked;
      }}
      current.updated_at = new Date().toISOString();
      current.hash = rec.hash;
      saveFeedback();
      const saved = card.querySelector("[data-saved]");
      saved.textContent = "Saved";
      setTimeout(() => {{ saved.textContent = ""; }}, 900);
      updateStats();
    }});
    return card;
  }}

  function render() {{
    const root = document.getElementById("cases");
    root.innerHTML = "";
    records.forEach(rec => root.appendChild(renderCase(rec)));
    updateVisibility();
    updateStats();
  }}

  function updateVisibility() {{
    const q = document.getElementById("search").value.trim().toLowerCase();
    const status = document.getElementById("statusFilter").value;
    document.querySelectorAll(".case").forEach(card => {{
      const id = card.dataset.id;
      const fb = caseFeedback(id);
      const okSearch = !q || card.dataset.search.includes(q);
      const okStatus = !status || (fb.rating || "unset") === status;
      card.classList.toggle("hidden", !(okSearch && okStatus));
    }});
  }}

  function updateStats() {{
    const counts = {{ total: records.length, unset: 0, pass: 0, partial: 0, fail: 0, unsafe: 0 }};
    const active = document.getElementById("statusFilter").value;
    records.forEach(rec => {{
      const rating = (feedback[rec.id] && feedback[rec.id].rating) || "unset";
      counts[rating] = (counts[rating] || 0) + 1;
    }});
    document.getElementById("stats").innerHTML = Object.entries(counts)
      .map(([k, v]) => {{
        const filter = k === "total" ? "" : k;
        const selected = active === filter;
        return `<button type="button" class="stat${{selected ? " selected" : ""}}" data-stat-filter="${{escapeHtml(filter)}}">${{escapeHtml(k)}}: ${{v}}</button>`;
      }}).join("");
  }}

  function exportFeedback() {{
    const out = {{
      schema: "animageo-ai-construction-lab-feedback/v1",
      exported_at: new Date().toISOString(),
      library_generated_at: payload.generated_at,
      context: payload.context,
      cases: records.map(rec => ({{
        id: rec.id,
        title: rec.title,
        prompt: rec.prompt,
        hash: rec.hash,
        feedback: caseFeedback(rec.id)
      }}))
    }};
    const blob = new Blob([JSON.stringify(out, null, 2)], {{ type: "application/json" }});
    const a = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    a.href = URL.createObjectURL(blob);
    a.download = `ai-construction-feedback-${{stamp}}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }}

  function importFeedbackFile(file) {{
    const reader = new FileReader();
    reader.onload = function () {{
      const imported = JSON.parse(String(reader.result || "{{}}"));
      if (Array.isArray(imported.cases)) {{
        imported.cases.forEach(item => {{
          if (item && item.id && item.feedback) feedback[item.id] = item.feedback;
        }});
      }}
      saveFeedback();
      render();
    }};
    reader.readAsText(file);
  }}

  document.getElementById("search").addEventListener("input", updateVisibility);
  document.getElementById("statusFilter").addEventListener("change", () => {{ updateVisibility(); updateStats(); }});
  document.getElementById("stats").addEventListener("click", event => {{
    const target = event.target.closest("[data-stat-filter]");
    if (!target) return;
    document.getElementById("statusFilter").value = target.dataset.statFilter;
    updateVisibility();
    updateStats();
  }});
  document.getElementById("exportBtn").addEventListener("click", exportFeedback);
  document.getElementById("importBtn").addEventListener("click", () => document.getElementById("importFile").click());
  document.getElementById("importFile").addEventListener("change", event => {{
    const file = event.target.files && event.target.files[0];
    if (file) importFeedbackFile(file);
  }});

  render();
}}());
</script>
</body>
</html>
"""


def build_compact_index(
    records: list[dict[str, Any]],
    cases_doc: dict[str, Any],
) -> str:
    payload = {
        "schema": "animageo-ai-construction-lab-library/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context": cases_doc.get("context"),
        "records": records,
    }
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    template = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AnimaGeo AI Construction Lab</title>
<style>
:root {
  color-scheme: light;
  --bg:#f7f8fa; --paper:#fff; --paper-2:#fbfcfd; --ink:#1a1f26;
  --muted:#667085; --line:#e1e4e8; --accent:#4d87c6; --accent-bg:#e4edf8;
  --bad:#b42318; --bad-bg:#fce6e4; --warn:#b54708; --warn-bg:#fff3d6;
  --good:#067647; --good-bg:#e3f4e9; --code-bg:#272b32; --code-fg:#e8eaed;
  --code-kw:#c591e0; --code-str:#9dce65; --code-num:#e5a73c;
  --code-cmt:#7e8894; --code-dsl:#7eb0e0;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:13px/1.42 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif; }
header { position:sticky; top:0; z-index:10; background:rgba(255,255,255,.94); border-bottom:1px solid var(--line); backdrop-filter:blur(8px); }
.bar { max-width:1480px; margin:0 auto; padding:9px 14px; display:grid; grid-template-columns:1fr auto; gap:12px; align-items:center; }
h1 { font-size:17px; margin:0; letter-spacing:0; }
.sub { color:var(--muted); margin-top:1px; font-size:12px; }
.actions { display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
button, select, input[type="search"], input[type="text"] { border:1px solid var(--line); background:#fff; color:var(--ink); border-radius:6px; padding:6px 9px; font:inherit; }
button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
.export-status { color:var(--muted); font-size:12px; min-width:120px; }
.export-status.ok { color:var(--good); }
.export-status.err { color:var(--bad); }
main { max-width:1480px; margin:0 auto; padding:12px 14px; }
.add-case { margin-bottom:10px; border:1px solid var(--line); border-radius:8px; background:var(--paper); overflow:hidden; }
.add-case summary { cursor:pointer; padding:8px 11px; color:#344054; font-weight:650; }
.add-case form { border-top:1px solid var(--line); padding:10px 11px; background:var(--paper-2); }
.add-grid { display:grid; grid-template-columns:300px 1fr; gap:8px 10px; align-items:start; }
.field { display:grid; gap:4px; min-width:0; }
.field-wide { grid-column:1 / -1; }
.field span { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.055em; }
.advanced-add { border:1px solid var(--line); border-radius:6px; background:#fff; }
.advanced-add summary { padding:7px 9px; color:var(--muted); font-size:12px; font-weight:600; cursor:pointer; }
.advanced-add textarea { border:0; border-top:1px solid var(--line); border-radius:0 0 6px 6px; width:100%; }
.mono-input { min-height:132px; font:11.5px/1.48 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.add-actions { display:flex; align-items:center; gap:8px; margin-top:8px; }
.add-status { color:var(--muted); font-size:12px; }
.add-status.ok { color:var(--good); }
.add-status.err { color:var(--bad); }
.stats { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; }
.variant-tabs { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; }
.variant-tab { cursor:pointer; border:1px solid var(--line); border-radius:999px; padding:4px 10px; background:#fff; color:#344054; font:inherit; }
.variant-tab.selected { border-color:var(--accent); color:var(--accent); background:#eef6ff; font-weight:650; }
.case { background:var(--paper); border:1px solid var(--line); border-radius:8px; margin-bottom:10px; overflow:hidden; }
.case-head { padding:9px 11px; border-bottom:1px solid var(--line); display:grid; grid-template-columns:1fr auto; gap:10px; align-items:start; }
.case-title { font-size:15px; font-weight:650; margin:0 0 3px; }
.prompt { margin:0; color:#344054; }
.badges { display:flex; gap:5px; flex-wrap:wrap; justify-content:flex-end; }
.badge, .stat { border:1px solid var(--line); border-radius:999px; padding:2px 7px; color:var(--muted); white-space:nowrap; font-size:11.5px; background:#fff; }
.stat { cursor:pointer; font:inherit; line-height:1.45; }
.stat.selected { border-color:var(--accent); color:var(--accent); background:#eef6ff; }
.case-grid { display:grid; grid-template-columns:minmax(330px,.92fr) minmax(420px,1.08fr); gap:0; }
.pane { padding:9px 11px; min-width:0; }
.pane + .pane { border-left:1px solid var(--line); }
.svg-wrap { background:#fbfbfc; border:1px solid var(--line); border-radius:6px; padding:6px; min-height:220px; display:grid; place-items:center; }
.svg-wrap img { max-width:100%; height:auto; display:block; }
h2 { font-size:11px; text-transform:uppercase; letter-spacing:.055em; color:var(--muted); margin:0 0 6px; }
pre { overflow:auto; margin:0; padding:9px 10px; background:var(--code-bg); color:var(--code-fg); border-radius:6px; border:1px solid #1d222a; font:11.5px/1.48 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; max-height:260px; }
pre code { color:inherit; background:none; padding:0; }
.kw { color:var(--code-kw); } .str { color:var(--code-str); } .num { color:var(--code-num); } .cmt { color:var(--code-cmt); font-style:italic; } .dsl { color:var(--code-dsl); }
.meta-row { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:8px; }
.notes, .expected { margin:0; padding-left:16px; color:#344054; }
.notes li, .expected li { margin:1px 0; }
details.style-details { margin-top:8px; border:1px solid var(--line); border-radius:6px; background:var(--paper-2); }
details.style-details summary { cursor:pointer; padding:6px 8px; color:var(--muted); font-weight:650; font-size:11px; text-transform:uppercase; letter-spacing:.055em; }
details.style-details pre { border:0; border-top:1px solid var(--line); border-radius:0 0 6px 6px; max-height:220px; }
.feedback { border-top:1px solid var(--line); padding:8px 11px 9px; display:grid; grid-template-columns:minmax(230px,.72fr) minmax(420px,1.28fr); gap:10px; background:#fcfcfd; }
.feedback-head { display:flex; align-items:center; gap:8px; margin-bottom:5px; }
.chip-row { display:flex; gap:5px; flex-wrap:wrap; align-items:center; }
.chip { display:inline-flex; align-items:center; min-height:24px; border:1px solid var(--line); border-radius:999px; padding:3px 8px; background:#fff; color:#344054; cursor:pointer; user-select:none; font-size:12px; }
.chip input { position:absolute; opacity:0; pointer-events:none; }
.chip.selected { border-color:var(--accent); background:var(--accent-bg); color:#174a76; font-weight:650; }
.chip.rating-pass.selected { border-color:var(--good); background:var(--good-bg); color:var(--good); }
.chip.rating-fail.selected, .chip.rating-unsafe.selected { border-color:var(--bad); background:var(--bad-bg); color:var(--bad); }
.chip.rating-partial.selected { border-color:var(--warn); background:var(--warn-bg); color:var(--warn); }
textarea { width:100%; min-height:54px; resize:vertical; border:1px solid var(--line); border-radius:6px; padding:6px 8px; font:inherit; }
.saved { color:var(--good); font-size:11px; min-height:15px; }
.hidden { display:none; }
@media (max-width:980px) {
  .bar, .case-head, .feedback { grid-template-columns:1fr; }
  .case-grid, .meta-row, .add-grid { grid-template-columns:1fr; }
  .pane + .pane { border-left:0; border-top:1px solid var(--line); }
}
</style>
</head>
<body>
<header>
  <div class="bar">
    <div>
      <h1>AnimaGeo AI Construction Lab</h1>
      <div class="sub">Запросы, AI DSL, SVG и ручная обратная связь</div>
    </div>
    <div class="actions">
      <input id="search" type="search" placeholder="Search">
      <select id="statusFilter">
        <option value="">All statuses</option>
        <option value="unset">Unset</option>
        <option value="pass">Pass</option>
        <option value="partial">Partial</option>
        <option value="fail">Fail</option>
        <option value="unsafe">Unsafe</option>
      </select>
      <button id="importBtn">Import feedback</button>
      <button class="primary" id="exportBtn">Export feedback</button>
      <span id="exportStatus" class="export-status"></span>
      <input id="importFile" type="file" accept="application/json" class="hidden">
    </div>
  </div>
</header>
<main>
  <details class="add-case" id="addCasePanel">
    <summary>Generate manual case</summary>
    <form id="addCaseForm">
      <div class="add-grid">
        <label class="field"><span>Title</span><input id="addTitle" type="text" placeholder="Optional"></label>
        <label class="field field-wide"><span>Prompt</span><textarea id="addPrompt" required placeholder="Запрос пользователя. Сервер вызовет AI с текущим context-файлом и отрендерит SVG."></textarea></label>
        <details class="field field-wide advanced-add">
          <summary>Advanced: paste AI response JSON or construction DSL instead of calling AI</summary>
          <textarea id="addResponse" class="mono-input" placeholder='{"schema":"animageo-ai-construction-response/v1","mode":"create","construction_dsl":"A = Point(0, 0)\\n...","style":null,"notes":[]}'></textarea>
        </details>
      </div>
      <div class="add-actions"><button class="primary" type="submit">Generate and render</button><span id="addCaseStatus" class="add-status"></span></div>
    </form>
  </details>
  <div class="variant-tabs" id="variantTabs"></div>
  <div class="stats" id="stats"></div>
  <div id="cases"></div>
</main>
<script id="library-data" type="application/json">__DATA_JSON__</script>
<script>
(function () {
  "use strict";
  const payload = JSON.parse(document.getElementById("library-data").textContent);
  const records = payload.records || [];
  records.forEach(rec => { if (!rec.variant) rec.variant = "flash"; });
  const variants = Array.from(new Set(records.map(rec => rec.variant || "flash")));
  let activeVariant = variants[0] || "flash";
  const storageKey = "animageo-ai-construction-lab-feedback-v1";
  const ratingOptions = [["unset","Unset"],["pass","Pass"],["partial","Partial"],["fail","Fail"],["unsafe","Unsafe"]];
  const issueKeys = [
    ["construction_error", "Ошибка конструкции"],
    ["style_misuse", "Стиль засунут в DSL"],
    ["unsupported", "Неподдержано"],
    ["ambiguity", "Не снята неоднозначность"],
    ["naming", "Проблемы с именами"],
    ["good_pattern", "Хороший паттерн"]
  ];
  const PY_KEYWORDS = new Set(["for","if","else","elif","while","def","class","return","with","as","in","not","and","or","is","lambda","True","False","None","pass","break","continue","try","except","finally"]);
  const DSL_NAMES = new Set(["Point","Line","Segment","Ray","Vector","Circle","Arc","CircleArc","CircleSector","Polygon","Angle","Midpoint","Intersect","PerpendicularLine","OrthogonalLine","PerpendicularBisector","AngularBisector","Center","Centroid","Tangent","Polar","Focus","Vertex","Directrix","Axes","MajorAxis","MinorAxis","Ellipse","Hyperbola","Parabola","Conic","Function","ImplicitCurve","Incircle","Distance","Length","Radius","Area","Perimeter","Circumference","Rotate","Translate","Reflect","Mirror","Locus","style","hide","show","pi","sqrt","sin","cos","tan"]);

  function loadFeedback() { try { return JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch (_) { return {}; } }
  let feedback = loadFeedback();
  function saveFeedback() { localStorage.setItem(storageKey, JSON.stringify(feedback)); }
  function escapeHtml(s) { return String(s || "").replace(/[&<>"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[ch])); }
  function caseKey(rec) { return `${rec.variant || "flash"}::${rec.id}`; }
  function caseFeedback(recOrKey) {
    const key = typeof recOrKey === "string" ? recOrKey : caseKey(recOrKey);
    if (!feedback[key]) feedback[key] = { rating:"unset", issues:{}, comment:"" };
    if (!feedback[key].issues) feedback[key].issues = {};
    return feedback[key];
  }
  function highlightPython(code) {
    let out = "", i = 0;
    while (i < code.length) {
      const c = code[i];
      if (c === "#") {
        const end = code.indexOf("\\n", i), j = end === -1 ? code.length : end;
        out += '<span class="cmt">' + escapeHtml(code.slice(i, j)) + "</span>"; i = j;
      } else if (c === '"' || c === "'") {
        const q = c; let j = i + 1;
        while (j < code.length && code[j] !== q && code[j] !== "\\n") { if (code[j] === "\\\\" && j + 1 < code.length) j += 1; j += 1; }
        if (j < code.length && code[j] === q) j += 1;
        out += '<span class="str">' + escapeHtml(code.slice(i, j)) + "</span>"; i = j;
      } else if ((c >= "0" && c <= "9") || (c === "-" && code[i + 1] >= "0" && code[i + 1] <= "9")) {
        let j = c === "-" ? i + 1 : i; while (j < code.length && /[0-9.]/.test(code[j])) j += 1;
        out += '<span class="num">' + escapeHtml(code.slice(i, j)) + "</span>"; i = j;
      } else if (/[A-Za-z_]/.test(c)) {
        let j = i + 1; while (j < code.length && /[A-Za-z0-9_]/.test(code[j])) j += 1;
        const word = code.slice(i, j), cls = PY_KEYWORDS.has(word) ? "kw" : DSL_NAMES.has(word) ? "dsl" : "";
        out += cls ? `<span class="${cls}">${escapeHtml(word)}</span>` : escapeHtml(word); i = j;
      } else { out += escapeHtml(c); i += 1; }
    }
    return out;
  }
  function highlightJson(code) {
    return escapeHtml(code)
      .replace(/("(?:\\\\.|[^"\\\\])*")(?=\\s*:)/g, '<span class="dsl">$1</span>')
      .replace(/(:\\s*)("(?:\\\\.|[^"\\\\])*")/g, '$1<span class="str">$2</span>')
      .replace(/\\b(true|false|null)\\b/g, '<span class="kw">$1</span>')
      .replace(/(-?\\b\\d+(?:\\.\\d+)?\\b)/g, '<span class="num">$1</span>');
  }
  function ratingChips(rec, fb) {
    return ratingOptions.map(([value, label]) => {
      const selected = (fb.rating || "unset") === value;
      return `<label class="chip rating-${value}${selected ? " selected" : ""}"><input type="radio" name="rating-${escapeHtml(caseKey(rec))}" data-rating-input value="${value}" ${selected ? "checked" : ""}>${escapeHtml(label)}</label>`;
    }).join("");
  }
  function issueChips(fb) {
    return issueKeys.map(([key, label]) => {
      const selected = fb.issues && fb.issues[key];
      return `<label class="chip issue${selected ? " selected" : ""}"><input type="checkbox" data-issue="${key}" ${selected ? "checked" : ""}>${escapeHtml(label)}</label>`;
    }).join("");
  }
  function renderCase(rec) {
    const fb = caseFeedback(rec);
    const key = caseKey(rec);
    const card = document.createElement("section");
    card.className = "case";
    card.dataset.id = rec.id;
    card.dataset.key = key;
    card.dataset.variant = rec.variant || "flash";
    card.dataset.search = [rec.id, rec.title, rec.prompt, rec.kind, rec.mode, rec.variant, rec.model].join(" ").toLowerCase();
    const expected = (rec.expected || []).map(x => `<li>${escapeHtml(x)}</li>`).join("");
    const notes = (rec.notes || []).map(x => `<li>${escapeHtml(x)}</li>`).join("");
    const diagnostics = (rec.diagnostics || []).map(item => `<li><strong>${escapeHtml(item.severity || item.type || "diagnostic")}</strong>: ${escapeHtml(item.message || item.code || JSON.stringify(item))}</li>`).join("");
    const diagnosticsBlock = diagnostics ? `<h2>Diagnostics</h2><ul class="notes diagnostics">${diagnostics}</ul>` : "";
    const styleBlock = rec.style ? `<details class="style-details"><summary>Style JSON</summary><pre class="code json"><code>${highlightJson(JSON.stringify(rec.style, null, 2))}</code></pre></details>` : "";
    const errorBlock = rec.error ? `<h2>Render Error</h2><pre><code>${highlightJson(JSON.stringify(rec.error, null, 2))}</code></pre>` : "";
    card.innerHTML = `
      <div class="case-head">
        <div><h2>${escapeHtml(rec.id)}</h2><div class="case-title">${escapeHtml(rec.title)}</div><p class="prompt">${escapeHtml(rec.prompt)}</p></div>
        <div class="badges"><span class="badge">${escapeHtml(rec.variant || "flash")}</span><span class="badge">${escapeHtml(rec.model || "")}</span><span class="badge">${escapeHtml(rec.kind)}</span><span class="badge">${escapeHtml(rec.mode)}</span><span class="badge">${escapeHtml(rec.status)}</span><span class="badge">${escapeHtml(rec.hash)}</span></div>
      </div>
      <div class="case-grid">
        <div class="pane"><h2>SVG</h2><div class="svg-wrap"><img src="${escapeHtml(rec.svg_path)}?h=${escapeHtml(rec.hash)}" alt="${escapeHtml(rec.title)}"></div></div>
        <div class="pane">
          <div class="meta-row"><div><h2>Expected</h2><ul class="expected">${expected}</ul></div><div><h2>Notes</h2><ul class="notes">${notes}</ul>${diagnosticsBlock}</div></div>
          <h2>Construction DSL</h2><pre class="code python"><code>${highlightPython(rec.dsl)}</code></pre>${styleBlock}${errorBlock}
        </div>
      </div>
      <div class="feedback">
        <div>
          <div class="feedback-head"><h2>Manual Rating</h2><span class="saved" data-saved></span></div>
          <div class="chip-row">${ratingChips(rec, fb)}</div>
          <h2 style="margin-top:8px">Issues</h2><div class="chip-row">${issueChips(fb)}</div>
        </div>
        <div><div class="feedback-head"><h2>Comment</h2><span class="saved" data-saved></span></div><textarea data-comment placeholder="Что неверно, что улучшить в context-файле или validator?">${escapeHtml(fb.comment || "")}</textarea></div>
      </div>`;
    card.addEventListener("input", function (event) {
      const current = caseFeedback(rec), target = event.target;
      if (target.matches("[data-rating-input]")) {
        current.rating = target.value;
        card.querySelectorAll("[data-rating-input]").forEach(input => input.closest(".chip").classList.toggle("selected", input.checked));
      }
      if (target.matches("[data-comment]")) current.comment = target.value;
      if (target.matches("[data-issue]")) {
        current.issues[target.dataset.issue] = target.checked;
        target.closest(".chip").classList.toggle("selected", target.checked);
      }
      current.updated_at = new Date().toISOString();
      current.hash = rec.hash;
      saveFeedback();
      card.querySelectorAll("[data-saved]").forEach(saved => { saved.textContent = "Saved"; setTimeout(() => { saved.textContent = ""; }, 900); });
      updateStats();
    });
    return card;
  }
  function renderVariantTabs() {
    document.getElementById("variantTabs").innerHTML = variants.map(variant => {
      const count = records.filter(rec => (rec.variant || "flash") === variant).length;
      return `<button type="button" class="variant-tab${variant === activeVariant ? " selected" : ""}" data-variant="${escapeHtml(variant)}">${escapeHtml(variant)}: ${count}</button>`;
    }).join("");
  }
  function render() {
    renderVariantTabs();
    const root = document.getElementById("cases");
    root.innerHTML = "";
    records.forEach(rec => root.appendChild(renderCase(rec)));
    updateVisibility();
    updateStats();
  }
  function updateVisibility() {
    const q = document.getElementById("search").value.trim().toLowerCase(), status = document.getElementById("statusFilter").value;
    document.querySelectorAll(".case").forEach(card => {
      const fb = caseFeedback(card.dataset.key);
      const variantOk = card.dataset.variant === activeVariant;
      card.classList.toggle("hidden", !(variantOk && (!q || card.dataset.search.includes(q)) && (!status || (fb.rating || "unset") === status)));
    });
  }
  function updateStats() {
    const activeRecords = records.filter(rec => (rec.variant || "flash") === activeVariant);
    const counts = { total: activeRecords.length, unset: 0, pass: 0, partial: 0, fail: 0, unsafe: 0 };
    const active = document.getElementById("statusFilter").value;
    activeRecords.forEach(rec => { const fb = feedback[caseKey(rec)] || {}; const rating = fb.rating || "unset"; counts[rating] = (counts[rating] || 0) + 1; });
    document.getElementById("stats").innerHTML = Object.entries(counts).map(([k, v]) => {
      const filter = k === "total" ? "" : k;
      const selected = active === filter;
      return `<button type="button" class="stat${selected ? " selected" : ""}" data-stat-filter="${escapeHtml(filter)}">${escapeHtml(k)}: ${v}</button>`;
    }).join("");
  }
  function feedbackPayload() {
    return { schema:"animageo-ai-construction-lab-feedback/v1", exported_at:new Date().toISOString(), library_generated_at:payload.generated_at, context:payload.context, cases:records.map(rec => ({ id:rec.id, variant:rec.variant || "flash", model:rec.model || null, feedback_key:caseKey(rec), title:rec.title, prompt:rec.prompt, hash:rec.hash, feedback:caseFeedback(rec) })) };
  }
  function setExportStatus(message, cls) {
    const el = document.getElementById("exportStatus");
    el.textContent = message || "";
    el.className = "export-status" + (cls ? ` ${cls}` : "");
  }
  function downloadFeedback(out) {
    const blob = new Blob([JSON.stringify(out, null, 2)], { type:"application/json" });
    const a = document.createElement("a"), stamp = new Date().toISOString().replace(/[:.]/g, "-");
    a.href = URL.createObjectURL(blob); a.download = `ai-construction-feedback-${stamp}.json`; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  async function saveFeedbackToServer(out) {
    if (!/^https?:$/.test(window.location.protocol)) return false;
    const response = await fetch("/feedback", { method:"POST", headers:{ "Content-Type":"application/json" }, body:JSON.stringify(out) });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }
  async function exportFeedback() {
    const out = feedbackPayload();
    try {
      const saved = await saveFeedbackToServer(out);
      if (saved && saved.ok) { setExportStatus(`Saved ${saved.path}`, "ok"); return; }
    } catch (exc) {
      console.warn("Local feedback save failed; falling back to download.", exc);
      setExportStatus("Downloaded fallback", "err");
    }
    downloadFeedback(out);
  }
  function importFeedbackFile(file) {
    const reader = new FileReader();
    reader.onload = function () {
      const imported = JSON.parse(String(reader.result || "{}"));
      if (Array.isArray(imported.cases)) imported.cases.forEach(item => {
        if (item && item.id && item.feedback) feedback[item.feedback_key || `${item.variant || "flash"}::${item.id}`] = item.feedback;
      });
      saveFeedback(); render();
    };
    reader.readAsText(file);
  }
  function setAddStatus(message, cls) {
    const el = document.getElementById("addCaseStatus");
    el.textContent = message || "";
    el.className = "add-status" + (cls ? ` ${cls}` : "");
  }
  function parseManualResponse(raw) {
    const text = String(raw || "").trim();
    if (!text) return { response: null, expected: [] };
    if (text.startsWith("{")) {
      const parsed = JSON.parse(text);
      if (parsed.response && typeof parsed.response === "object") {
        return { response: parsed.response, expected: parsed.expected || [] };
      }
      if (parsed.construction_dsl) {
        return { response: parsed, expected: [] };
      }
      throw new Error("JSON must contain response or construction_dsl");
    }
    return {
      response: {
        schema: "animageo-ai-construction-response/v1",
        mode: "create",
        construction_dsl: text,
        style: null,
        notes: []
      },
      expected: []
    };
  }
  async function addManualCase(event) {
    event.preventDefault();
    try {
      if (!/^https?:$/.test(window.location.protocol)) throw new Error("Open through the local lab server");
      const parsed = parseManualResponse(document.getElementById("addResponse").value);
      const payloadOut = {
        schema: "animageo-ai-construction-lab-add-case/v1",
        title: document.getElementById("addTitle").value.trim(),
        prompt: document.getElementById("addPrompt").value.trim(),
        expected: parsed.expected
      };
      if (parsed.response) payloadOut.response = parsed.response;
      if (!payloadOut.prompt) throw new Error("Prompt is required");
      setAddStatus(parsed.response ? "Rendering..." : "Generating via AI...", "");
      const response = await fetch("/cases", { method:"POST", headers:{ "Content-Type":"application/json" }, body:JSON.stringify(payloadOut) });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || response.statusText);
      records.unshift(result.record);
      if (!result.record.variant) result.record.variant = "flash";
      if (!variants.includes(result.record.variant)) variants.unshift(result.record.variant);
      activeVariant = result.record.variant;
      feedback[caseKey(result.record)] = { rating:"unset", issues:{}, comment:"", hash:result.record.hash };
      saveFeedback();
      document.getElementById("addTitle").value = "";
      document.getElementById("addPrompt").value = "";
      document.getElementById("addResponse").value = "";
      setAddStatus(`Added ${result.record.id}`, "ok");
      render();
      document.querySelector(`[data-key="${CSS.escape(caseKey(result.record))}"]`)?.scrollIntoView({ behavior:"smooth", block:"start" });
    } catch (exc) {
      setAddStatus(exc.message || String(exc), "err");
    }
  }
  document.getElementById("search").addEventListener("input", updateVisibility);
  document.getElementById("statusFilter").addEventListener("change", () => { updateVisibility(); updateStats(); });
  document.getElementById("stats").addEventListener("click", event => {
    const target = event.target.closest("[data-stat-filter]");
    if (!target) return;
    document.getElementById("statusFilter").value = target.dataset.statFilter;
    updateVisibility();
    updateStats();
  });
  document.getElementById("variantTabs").addEventListener("click", event => {
    const target = event.target.closest("[data-variant]");
    if (!target) return;
    activeVariant = target.dataset.variant;
    renderVariantTabs();
    updateVisibility();
    updateStats();
  });
  document.getElementById("exportBtn").addEventListener("click", exportFeedback);
  document.getElementById("importBtn").addEventListener("click", () => document.getElementById("importFile").click());
  document.getElementById("importFile").addEventListener("change", event => { const file = event.target.files && event.target.files[0]; if (file) importFeedbackFile(file); });
  const addCaseForm = document.getElementById("addCaseForm");
  if (addCaseForm) addCaseForm.addEventListener("submit", addManualCase);
  render();
}());
</script>
</body>
</html>
"""
    return template.replace("__DATA_JSON__", data_json)


def main() -> None:
    ensure_dirs()
    cases_doc = read_cases()
    records = render_all(cases_doc)
    library = {
        "schema": "animageo-ai-construction-lab-library/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context": cases_doc.get("context"),
        "records": records,
    }
    LIBRARY_PATH.write_text(json.dumps(library, ensure_ascii=False, indent=2), encoding="utf-8")
    INDEX_PATH.write_text(build_compact_index(records, cases_doc), encoding="utf-8")
    rendered = sum(1 for rec in records if rec["status"] == "rendered")
    errored = sum(1 for rec in records if rec["status"] == "error")
    print(f"Generated {INDEX_PATH.relative_to(REPO)}")
    print(f"Rendered: {rendered}; errors: {errored}")


if __name__ == "__main__":
    main()
