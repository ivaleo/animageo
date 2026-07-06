"""Generate an interactive before/after comparison + feedback-capture page for
the label-placement mechanism.

Renders a spread of ``examples/*.ggb`` in three variants (Original / current Auto
/ Auto+P0), embeds them as inline SVG, and wraps them in an HTML tool where you
can rate and comment on each drawing. Comments persist in localStorage and can
be exported to ``label_placement_feedback.json`` / ``.md`` for the agent to
process into general criteria/improvements.

Run from the repo root so the local ``animageo`` package is importable:

    PYTHONPATH=. python3.13 docs/archive/label_placement_examples/build_feedback_compare.py

Output (gitignored): docs/archive/label_placement_examples/compare.html
"""
import os
import re
import glob
import zipfile
import html
import json
import logging

logging.disable(logging.CRITICAL)

from animageo.animageo import AnimaGeoScene  # noqa: E402

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_HTML = os.path.join(OUT_DIR, "compare.html")
TMP_SVG = os.path.join(OUT_DIR, "_tmp.svg")

# Feedback round. Bump for each fresh pass: it changes the localStorage key (so
# the page starts empty, the previous round's comments are NOT loaded) and the
# exported filename (label_placement_feedback_round{N}.json).
ROUND = 22

# Variant config: (label_placement overlay cfg or None, run autoPlaceLabels?)
VARIANTS = {
    "orig": (None, False),
    "auto": ({"enabled": True}, True),
    "p0": ({"enabled": True, "repair_iterations": 6, "soft_falloff_px": 0.0,
            "respect_current_position": True, "point_bisector": True,
            "geom_gap_px": 2.0, "directional_placement": False,
            "directional_cap_px": 16.0, "viewport_clamp": True,
            "declutter_labels": True, "label_gap_px": 2.5,
            "w_assoc": 3.0, "dashed_overlap_factor": 0.3,
            "continuous_placement": True, "continuous_steps": 72,
            "angle_label_max_arm_fraction": 0.45,
            "cluster_consistency": True, "compact_labels": True,
            "compact_gap_px": 1.0, "compact_max_push_px": 4.0,
            "overlap_tol_px": 2.5}, True),
    # NOTE: direction_tolerance and consistent_placement are intentionally OFF.
    # - direction_tolerance: routes hard labels to a better direction but pushes
    #   many others out, breaking gap UNIFORMITY (round-10).
    # - consistent_placement: snaps labels to the GLOBAL majority direction, which
    #   yanks correctly-placed labels "в бок" (W/S/B/C → down-left) when points
    #   have genuinely different natural directions (round-11 bug). Needs a
    #   region/cluster-aware rewrite before it can be enabled.
}
RENDER_EXTRA = {"p0": {"rendering": {"label_contrast": "auto"}}}
VARIANT_TITLE = {"orig": "Original (GGB, без autoplace)",
                 "auto": "Auto (текущий greedy)",
                 "p0": "Auto + P0 (repair+soft+respect+contrast)"}


def _label_count(path):
    """Number of labels the placement solver would actually lay out for a scene.

    This is the authoritative "does it have labels" signal: the XML
    ``show label="true"`` count over-reports (auxiliary/empty/numeric labels
    that animageo does not render), which let label-less scenes through in
    earlier rounds. Loading the scene and asking ``_collect_labels`` removes
    them reliably. Returns -1 on any load failure so the caller can skip.
    """
    try:
        from animageo.label_placement import _collect_labels
        sc = AnimaGeoScene()
        sc.loadGGB(path)
        sc.applyStyle(style={"overlay": {"label_placement": {"enabled": True}}})
        return len(_collect_labels(sc, 14.0))
    except Exception:
        return -1


def _dedup_key(path):
    """Group near-duplicate scene variants (scene26_, scene26_3, scene26_4 →
    one group) by folder + basename with a trailing ``_<digits>`` suffix
    stripped. Keeps genuinely different drawings while collapsing reductions
    of the same construction."""
    name = os.path.splitext(os.path.basename(path))[0]
    folder = os.path.basename(os.path.dirname(path))
    base = re.sub(r"_+\d*$", "", name)
    return (folder, base)


# Continuity set: the specific scenes the visual-feedback rounds flagged with
# unresolved problems (sector changes, angle-inside, edge cropping, dense
# clusters). Kept verbatim so each new round re-checks the SAME drawings after a
# fix. The rest of the slots are auto-filled with fresh, diverse scenes.
CURATED = [
    "examples/6 - Задача для канала Макса - площадь прямоугольника в секторе/scene6a.ggb",
    "examples/26 -  Задача Феди про треугольник/scene26_.ggb",
    "examples/19 - Задача Феди прямые RGB/scene19.ggb",
    "examples/4 - Пример из учебника - параллелограммы 8 кл/scene4.ggb",
    "examples/5 - Наброски для свойства ромба - 8 кл/scene5.ggb",
    "examples/27 -  Задача Феди про треугольник2/scene27_3.ggb",
    "examples/7 - Задача для канала Макса - два подобных прямоугольника/scene7.ggb",
    "examples/18 - Задача Феди про касательные/scene18.ggb",
    "examples/test_style/scene.ggb",   # 45° angle — external attachment (FP-8)
    "examples/test_style/test3.ggb",   # 45° inside-vs-outside + point cluster
    "examples/test_style/test6.ggb",   # edge cropping + scatter
    "examples/test1/10-4_.ggb",        # dense central area
    "examples/TestPoints/scene5___.ggb",  # points near diagonals/axes
]


def select_examples(limit=22):
    # 1) gather candidates that *claim* labels in the XML (cheap pre-filter)
    cands = []
    for f in glob.glob("examples/**/*.ggb", recursive=True):
        try:
            xml = zipfile.ZipFile(f).read("geogebra.xml").decode("utf8", "ignore")
        except Exception:
            continue
        shown = len(re.findall(r'show[^>]*label="true"', xml))
        nel = xml.count("<element ")
        if shown >= 3:
            cands.append((nel, f))
    cands.sort(reverse=True)

    # 2) the continuity set first (only those that exist and still have labels)
    picked, seen_groups = [], set()
    for f in CURATED:
        if not os.path.exists(f):
            print(f"  curated missing: {f}")
            continue
        nlab = _label_count(f)
        if nlab < 1:
            print(f"  curated drop {f} (labels={nlab})")
            continue
        picked.append(f)
        seen_groups.add(_dedup_key(f))

    # 3) keep the richest variant per dedup group, only scenes the solver finds
    #    >= 1 real label for (drops label-less scenes that slip past the XML
    #    heuristic), excluding groups already covered by the continuity set.
    best_per_group = {}
    for nel, f in cands:
        k = _dedup_key(f)
        if k in seen_groups or k in best_per_group:
            continue  # cands sorted by element count desc → first = richest
        nlab = _label_count(f)
        if nlab < 1:
            print(f"  drop {f} (labels={nlab})")
            continue
        best_per_group[k] = (nel, nlab, f)

    # 4) spread the fillers across the complexity range (not only the densest).
    fillers = [t[2] for t in sorted(best_per_group.values(), reverse=True)]
    room = max(0, limit - len(picked))
    if len(fillers) > room and room > 0:
        step = len(fillers) / room
        fillers = [fillers[int(i * step)] for i in range(room)]
    picked += fillers[:room]
    print(f"selected {len(picked)} ({len(seen_groups)} continuity + "
          f"{len(picked) - len(seen_groups)} fresh) of "
          f"{len(best_per_group) + len(seen_groups)} labelled groups")
    return picked


def render(path, variant):
    lp_cfg, do_auto = VARIANTS[variant]
    sc = AnimaGeoScene()
    sc.loadGGB(path)
    style = {}
    if lp_cfg is not None:
        style.setdefault("overlay", {})["label_placement"] = lp_cfg
    style.update(RENDER_EXTRA.get(variant, {}))
    if style:
        sc.applyStyle(style=style)
    if do_auto:
        sc.autoPlaceLabels()
    sc.exportSVG(TMP_SVG)
    s = open(TMP_SVG).read()
    s = re.sub(r"<\?xml[^>]*\?>", "", s).strip()
    s = re.sub(r'width="[^"]*"\s*height="[^"]*"', "", s, count=1)
    return s


def main():
    picked = select_examples()
    items = []
    for i, path in enumerate(picked):
        name = os.path.splitext(os.path.basename(path))[0]
        folder = os.path.basename(os.path.dirname(path))
        label = f"{folder} / {name}" if folder not in ("examples", "") else name
        svgs, ok = {}, True
        for v in VARIANTS:
            try:
                svgs[v] = render(path, v)
            except Exception as e:
                ok = False
                print(f"  skip {label} [{v}]: {str(e)[:60]}")
                break
        if ok:
            items.append((f"ex{i}", label, svgs))
            print(f"OK  {label}")
    if os.path.exists(TMP_SVG):
        os.remove(TMP_SVG)
    print(f"\n{len(items)} examples rendered")

    labels = {k: lbl for k, lbl, _ in items}
    buttons = "\n".join(
        f'<button class="exbtn" id="b-{k}" data-k="{k}" onclick="show(\'{k}\')">'
        f'<span class="dot" id="d-{k}"></span>{html.escape(lbl)}</button>'
        for k, lbl, _ in items)
    store = "\n".join(
        f'<div class="store" data-k="{k}" data-v="{v}">{s}</div>'
        for k, _, svgs in items for v, s in svgs.items())
    first = items[0][0] if items else ""

    htmldoc = (PAGE
               .replace("%BUTTONS%", buttons)
               .replace("%STORE%", store)
               .replace("%LABELS_JSON%", json.dumps(labels, ensure_ascii=False))
               .replace("%VTITLE_JSON%", json.dumps(VARIANT_TITLE, ensure_ascii=False))
               .replace("%ROUND%", str(ROUND))
               .replace("%FIRST%", first))
    with open(OUT_HTML, "w") as fh:
        fh.write(htmldoc)
    print(f"WROTE {OUT_HTML} ({len(htmldoc) // 1024} KB)")


PAGE = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>AnimaGeo — авторасположение надписей: фидбек</title>
<style>
 body{font:14px/1.45 system-ui,Segoe UI,Arial;margin:0;color:#1f2937;background:#f3f4f6}
 header{padding:10px 16px;background:#111827;color:#fff;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
 header h1{font-size:15px;margin:0;flex:1}
 header .tools{display:flex;gap:8px;align-items:center}
 header button{padding:6px 10px;border:0;border-radius:6px;cursor:pointer;font-size:12px;background:#374151;color:#fff}
 header button.primary{background:#4f46e5}
 header button:hover{filter:brightness(1.12)}
 #counter{font-size:12px;color:#cbd5e1}
 .hint{padding:6px 16px;background:#eef2ff;color:#3730a3;font-size:12px}
 .wrap{display:flex;height:calc(100vh - 92px)}
 .side{width:270px;min-width:270px;overflow:auto;border-right:1px solid #e5e7eb;padding:8px;background:#fff}
 .exbtn{display:flex;align-items:center;gap:6px;width:100%;text-align:left;margin:2px 0;padding:6px 8px;
   border:1px solid #e5e7eb;background:#fff;border-radius:6px;cursor:pointer;font-size:12px;color:#1f2937}
 .exbtn:hover{background:#eef2ff} .exbtn.on{background:#4f46e5;color:#fff;border-color:#4f46e5}
 .dot{width:8px;height:8px;border-radius:50%;background:transparent;flex:0 0 auto}
 .exbtn.has .dot{background:#22c55e} .exbtn.on .dot{background:#fff}
 .main{flex:1;overflow:auto;padding:12px}
 .panels{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
 .panel{border:1px solid #e5e7eb;border-radius:8px;background:#fff;display:flex;flex-direction:column}
 .panel h3{margin:0;padding:8px 10px;font-size:13px;background:#f9fafb;border-bottom:1px solid #e5e7eb}
 .panel h3 .cap{font-weight:normal;color:#6b7280;font-size:11px;display:block}
 .view{padding:8px}.view svg{width:100%;height:auto;max-height:60vh}
 .fb{padding:8px;border-top:1px solid #f1f5f9;background:#fcfcfd}
 .rate{display:flex;gap:6px;margin-bottom:6px}
 .rate button{border:1px solid #e5e7eb;background:#fff;border-radius:6px;cursor:pointer;padding:3px 9px;font-size:14px}
 .rate button.on[data-r=good]{background:#dcfce7;border-color:#22c55e}
 .rate button.on[data-r=ok]{background:#fef9c3;border-color:#eab308}
 .rate button.on[data-r=bad]{background:#fee2e2;border-color:#ef4444}
 textarea{width:100%;box-sizing:border-box;border:1px solid #e5e7eb;border-radius:6px;padding:6px;
   font:12px system-ui;resize:vertical;min-height:46px}
 .overall{margin-top:12px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px}
 .overall label{font-weight:600;font-size:12px;display:block;margin-bottom:4px}
 .store{display:none}
</style></head><body>
<header>
 <h1>AnimaGeo — авторасположение надписей · фидбек, раунд %ROUND%</h1>
 <div class="tools">
   <span id="counter"></span>
   <button class="primary" onclick="exportJSON()">⬇ Экспорт JSON</button>
   <button onclick="exportMD()">⬇ Экспорт MD</button>
   <button onclick="clearAll()">Очистить</button>
 </div>
</header>
<div class="hint">Раунд %ROUND% — <b>чистка у окружностей и пунктиров</b>: надпись, налезшая на сплошную окружность, спасается в ближайшее чистое место (scene18 L); пунктирные линии/окружности теперь препятствия — надписи не садятся на пунктир, когда есть свободное место (10-4_ A/B/D). Близость у пересечений (scene19) и симметрия у окружностей (scene18 O) сохранены. Под каждым — оценка (👍/🟡/👎) и комментарий:
 <b>стало ли лучше, что ещё мешает и почему, как должно быть в идеале</b>. Автосохранение (localStorage);
 «Экспорт JSON» выгрузит <code>label_placement_feedback_round%ROUND%.json</code> — пришлите его мне.</div>
<div class="wrap">
 <div class="side">%BUTTONS%</div>
 <div class="main">
   <div class="panels">
     <div class="panel"><h3 id="t-orig">Original</h3><div class="view" id="v-orig"></div>
       <div class="fb"><div class="rate rate-orig">
         <button data-r="good" onclick="rate('orig','good')">👍</button>
         <button data-r="ok" onclick="rate('orig','ok')">🟡</button>
         <button data-r="bad" onclick="rate('orig','bad')">👎</button></div>
         <textarea id="cm-orig" oninput="cm('orig')" placeholder="Комментарий…"></textarea></div></div>
     <div class="panel"><h3 id="t-auto">Auto</h3><div class="view" id="v-auto"></div>
       <div class="fb"><div class="rate rate-auto">
         <button data-r="good" onclick="rate('auto','good')">👍</button>
         <button data-r="ok" onclick="rate('auto','ok')">🟡</button>
         <button data-r="bad" onclick="rate('auto','bad')">👎</button></div>
         <textarea id="cm-auto" oninput="cm('auto')" placeholder="Комментарий…"></textarea></div></div>
     <div class="panel"><h3 id="t-p0">Auto + P0</h3><div class="view" id="v-p0"></div>
       <div class="fb"><div class="rate rate-p0">
         <button data-r="good" onclick="rate('p0','good')">👍</button>
         <button data-r="ok" onclick="rate('p0','ok')">🟡</button>
         <button data-r="bad" onclick="rate('p0','bad')">👎</button></div>
         <textarea id="cm-p0" oninput="cm('p0')" placeholder="Комментарий…"></textarea></div></div>
   </div>
   <div class="overall">
     <label>Общий вывод по примеру / как должно быть в идеале (для выработки принципов):</label>
     <textarea id="overall" oninput="ov()" placeholder="Принцип, а не частный случай…"></textarea>
   </div>
 </div>
</div>
<div id="store">%STORE%</div>
<script>
const LABELS=%LABELS_JSON%, VTITLE=%VTITLE_JSON%, VARS=['orig','auto','p0'];
const KEY='animageo_label_feedback_v%ROUND%';
let FB={}; try{FB=JSON.parse(localStorage.getItem(KEY))||{}}catch(e){FB={}}
let CUR='%FIRST%';
function ensure(k){ if(!FB[k]) FB[k]={label:LABELS[k]||k,variants:{orig:{},auto:{},p0:{}},overall:''}; return FB[k]; }
function persist(){ localStorage.setItem(KEY,JSON.stringify(FB)); refreshDots(); counter(); }
function hasFB(e){ return e && (e.overall || VARS.some(v=>e.variants[v] && (e.variants[v].comment||e.variants[v].rating))); }
function setRate(v,r){ document.querySelectorAll('.rate-'+v+' button').forEach(b=>b.classList.toggle('on',b.dataset.r===r)); }
function show(k){
  CUR=k;
  document.querySelectorAll('.exbtn').forEach(b=>b.classList.toggle('on',b.dataset.k===k));
  for(const v of VARS){
    const el=document.querySelector('.store[data-k="'+k+'"][data-v="'+v+'"]');
    document.getElementById('v-'+v).innerHTML=el?el.innerHTML:'<i>—</i>';
    document.getElementById('t-'+v).innerHTML=VTITLE[v];
    const fv=(FB[k]&&FB[k].variants[v])||{};
    document.getElementById('cm-'+v).value=fv.comment||''; setRate(v,fv.rating||'');
  }
  document.getElementById('overall').value=(FB[k]&&FB[k].overall)||'';
}
function cm(v){ ensure(CUR).variants[v].comment=document.getElementById('cm-'+v).value; persist(); }
function rate(v,r){ const e=ensure(CUR); e.variants[v].rating=(e.variants[v].rating===r?'':r); setRate(v,e.variants[v].rating); persist(); }
function ov(){ ensure(CUR).overall=document.getElementById('overall').value; persist(); }
function counter(){ const n=Object.values(FB).filter(hasFB).length; document.getElementById('counter').textContent=n+' / '+Object.keys(LABELS).length+' с фидбеком'; }
function refreshDots(){ for(const k of Object.keys(LABELS)){ const b=document.getElementById('b-'+k); if(b) b.classList.toggle('has',hasFB(FB[k])); } }
function dl(blob,name){ const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; a.click(); }
function exportJSON(){ const out={generated_by:'animageo label feedback tool',variants:VTITLE,feedback:FB};
  dl(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}),'label_placement_feedback_round%ROUND%.json'); }
function exportMD(){ let md='# AnimaGeo label-placement feedback\n\n';
  for(const k of Object.keys(FB)){ const e=FB[k]; if(!hasFB(e)) continue; md+='## '+e.label+'\n\n';
    for(const v of VARS){ const x=e.variants[v]||{}; if(x.comment||x.rating) md+='- **'+VTITLE[v]+'** ['+(x.rating||'—')+']: '+(x.comment||'').replace(/\n/g,' ')+'\n'; }
    if(e.overall) md+='\n_Итог:_ '+e.overall.replace(/\n/g,' ')+'\n'; md+='\n'; }
  dl(new Blob([md],{type:'text/markdown'}),'label_placement_feedback_round%ROUND%.md'); }
function clearAll(){ if(confirm('Очистить весь фидбек?')){ FB={}; localStorage.removeItem(KEY); show(CUR); refreshDots(); counter(); } }
refreshDots(); counter(); show(CUR);
</script></body></html>"""


if __name__ == "__main__":
    main()
