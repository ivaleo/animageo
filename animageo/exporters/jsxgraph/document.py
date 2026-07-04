"""Assemble the JSXGraph board into HTML / JS / JSON output."""
from __future__ import annotations

import json
from typing import Dict

from .builder import BoardModel
from .options import JSXGraphOptions
from .spec import board_to_spec


def _cdn(opt: JSXGraphOptions) -> Dict[str, str]:
    v = opt.jsxgraph_version
    base = f"https://cdn.jsdelivr.net/npm/jsxgraph@{v}/distrib"
    return {
        "css": f"{base}/jsxgraph.css",
        "core": f"{base}/jsxgraphcore.js",
        "mathjax": "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js",
    }


def board_script(model: BoardModel, opt: JSXGraphOptions, indent: str = "  ",
                 *, board_id_js: Optional[str] = None, expose: bool = True) -> str:
    """The self-invoking board script (shared by html/js/moodle output).

    ``board_id_js`` is the JS expression passed to ``initBoard`` — a quoted div
    id for html/js, or the bare ``BOARDID`` the Moodle filter provides.
    """
    if board_id_js is None:
        board_id_js = json.dumps(opt.div_id)
    l, t, r, b = model.boundingbox
    chrome = model.chrome
    init = (
        "{{boundingbox: [{l}, {t}, {r}, {b}], keepaspectratio: {kar}, "
        "axis: {ax}, grid: {gr}, showNavigation: {nav}, showCopyright: false, "
        "pan: {{enabled: true}}, zoom: {{enabled: true}}}}"
    ).format(
        l=_n(l), t=_n(t), r=_n(r), b=_n(b),
        kar=_b(chrome.keep_aspect), ax=_b(chrome.axis), gr=_b(chrome.grid),
        nav=_b(opt.shownavigation),
    )
    lines = [
        "(function () {",
        f"{indent}var board = JXG.JSXGraph.initBoard({board_id_js}, {init});",
        f"{indent}var S = {{}};",
    ]
    lines += [f"{indent}{s}" for s in _chrome_statements(chrome)]
    lines += [f"{indent}{s}" for s in model.statements]
    if expose:
        # Expose board + element map for debugging / programmatic access.
        lines += [f"{indent}window.agboard = board;", f"{indent}window.agS = S;"]
    lines += ["})();"]
    return "\n".join(lines)


def render(model: BoardModel, opt: JSXGraphOptions, *, width: int, height: int) -> str:
    if opt.output == "spec":
        # Declarative, eval-free board spec (animageo-board/v1) for the
        # framework-agnostic JS runtime / Web Component.
        return json.dumps(
            board_to_spec(model, opt, width=width, height=height),
            ensure_ascii=False, indent=2,
        ) + "\n"
    if opt.output == "js":
        return board_script(model, opt) + "\n"
    if opt.output == "moodle":
        # Moodle filter_jsxgraph: the filter provides a `BOARDID`; the board is
        # built inside a <jsxgraph> tag. Best-effort (untested against a live
        # Moodle instance).
        script = board_script(model, opt, board_id_js="BOARDID", expose=False)
        return (
            f'<jsxgraph width="{int(width)}" height="{int(height)}">\n'
            f"{script}\n</jsxgraph>\n"
        )
    if opt.output == "json":
        chrome = model.chrome
        return json.dumps({
            "format": "animageo-jsxgraph/v1",
            "jsxgraph_version": opt.jsxgraph_version,
            "boundingbox": list(model.boundingbox),
            "div_id": opt.div_id,
            "chrome": {
                "axis": chrome.axis,
                "grid": chrome.grid,
                "background": chrome.background,
                "axesColor": chrome.axes_color,
                "gridColor": chrome.grid_color,
                "showXAxis": chrome.show_x_axis,
                "showYAxis": chrome.show_y_axis,
                "keepAspectRatio": chrome.keep_aspect,
                "gridBold": chrome.grid_bold,
                "gridStep": list(chrome.grid_step) if chrome.grid_step else None,
                "xShowNumbers": chrome.x_show_numbers,
                "yShowNumbers": chrome.y_show_numbers,
                "xTickDistance": chrome.x_tick_distance,
                "yTickDistance": chrome.y_tick_distance,
            },
            "statements": model.statements,
            "coverage": [
                {"name": n, "kind": k, "detail": d} for n, k, d in model.coverage
            ],
        }, ensure_ascii=False, indent=2) + "\n"
    return _html(model, opt, width=width, height=height)


def _html(model: BoardModel, opt: JSXGraphOptions, *, width: int, height: int) -> str:
    cdn = _cdn(opt)
    head = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8" />',
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
        "  <title>AnimaGeo · JSXGraph</title>",
        f'  <link rel="stylesheet" href="{cdn["css"]}" />',
    ]
    if opt.mathjax:
        head += [
            "  <script>window.MathJax = "
            "{ tex: { inlineMath: [['\\\\(', '\\\\)']] }, svg: { fontCache: 'global' } };"
            "</script>",
            f'  <script src="{cdn["mathjax"]}" id="MathJax-script" async></script>',
        ]
    bg = f" background: {model.chrome.background};" if model.chrome.background else ""
    head += [
        "  <style>",
        f"    #{opt.div_id} {{ width: {int(width)}px; height: {int(height)}px; "
        f"border: 1px solid #ddd;{bg} }}",
        "  </style>",
        "</head>",
        "<body>",
        f'  <div id="{opt.div_id}"></div>',
        f'  <script src="{cdn["core"]}"></script>',
        "  <script>",
        board_script(model, opt, indent="    "),
        "  </script>",
        "</body>",
        "</html>",
    ]
    return "\n".join(head + []) + "\n"


def _chrome_statements(chrome) -> list:
    """JS statements that apply scene background / axes / grid appearance after
    the board exists. Each DOM/board access is guarded so the script degrades
    gracefully on JSXGraph versions that lack ``defaultAxes`` / ``grids``."""
    out: list = []
    if chrome.background:
        out.append(
            "if (board.containerObj) board.containerObj.style.background = "
            f"{json.dumps(chrome.background)};"
        )
    if chrome.axis:
        per_axis = (
            ("x", chrome.show_x_axis, chrome.x_show_numbers, chrome.x_tick_distance),
            ("y", chrome.show_y_axis, chrome.y_show_numbers, chrome.y_tick_distance),
        )
        # Anything to set on either the axis line or its ticks?
        needs = chrome.axes_color or any(
            (not shown) or (not nums) or (dist is not None)
            for _k, shown, nums, dist in per_axis
        )
        if needs:
            parts = ["if (board.defaultAxes) {"]
            for key, shown, nums, dist in per_axis:
                axis_attrs = {}
                if not shown:
                    axis_attrs["visible"] = "false"
                if chrome.axes_color:
                    axis_attrs["strokeColor"] = json.dumps(chrome.axes_color)
                if axis_attrs:
                    body = ", ".join(f"{k}: {v}" for k, v in axis_attrs.items())
                    parts.append(f"  board.defaultAxes.{key}.setAttribute({{{body}}});")
                tick_attrs = {}
                if not nums:
                    tick_attrs["drawLabels"] = "false"
                if dist is not None:
                    tick_attrs["ticksDistance"] = _n(dist)
                    tick_attrs["insertTicks"] = "false"
                if tick_attrs:
                    body = ", ".join(f"{k}: {v}" for k, v in tick_attrs.items())
                    parts.append(
                        f"  if (board.defaultAxes.{key}.defaultTicks) "
                        f"board.defaultAxes.{key}.defaultTicks.setAttribute({{{body}}});"
                    )
            parts.append("}")
            out.append("\n".join(parts))
    if chrome.grid:
        grid_attrs = {}
        if chrome.grid_color:
            grid_attrs["strokeColor"] = json.dumps(chrome.grid_color)
        if chrome.grid_bold:
            # GeoGebra "bold grid": thicker lines (renderer uses 0.9 vs 0.65).
            grid_attrs["strokeWidth"] = "1.5"
        if chrome.grid_step:
            gx, gy = chrome.grid_step
            grid_attrs["majorStep"] = f"[{_n(gx)}, {_n(gy)}]"
        if grid_attrs:
            body = ", ".join(f"{k}: {v}" for k, v in grid_attrs.items())
            out.append(
                "if (board.grids) board.grids.forEach(function (g) { "
                f"g.setAttribute({{{body}}}); }});"
            )
    return out


def _n(v) -> str:
    s = f"{float(v):.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _b(v) -> str:
    return "true" if v else "false"
