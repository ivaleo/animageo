"""Local-only render server for the interactive AnimaGeo guide.

Run (from repo root):
    PYTHONPATH=. python3.13 docs/guide/server/serve.py

Exposes:
    GET  /                         → guide static files (docs/guide/, incl. assets)
    GET  /ggb/<name>.ggb           → downloadable GeoGebra source files
    POST /render                   → render one example, return SVG

SECURITY: binds 127.0.0.1 only. The /render endpoint executes arbitrary
Python via AnimaGeoScene.putCode(). Do not expose to the network.
"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from docs.guide.server.runner import ExampleSpec, render_example  # noqa: E402

GUIDE_ROOT = REPO / 'docs/guide'
GUIDE_EXAMPLES = GUIDE_ROOT / 'examples'   # style files live alongside the generator
STYLE_DIR = REPO / 'style'

app = FastAPI(title="AnimaGeo Guide Server", version="0.1")

# Local-only CORS (we serve the HTML from the same origin anyway, but the
# dev workflow of opening a file:// page and hitting the server is common;
# keep it permissive for 127.0.0.1).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Render endpoint ──────────────────────────────────────────────────

class RenderRequest(BaseModel):
    code: str
    w: int = 520
    h: int = 340
    scale: int = 46
    labels: list[str] = Field(default_factory=list)
    tex_labels: dict[str, str] = Field(default_factory=dict)
    hide: list[str] = Field(default_factory=list)
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    rendering_extra: dict[str, Any] = Field(default_factory=dict)
    overlay_extra: dict[str, Any] = Field(default_factory=dict)
    auto_place: bool = True
    style: str = "docs/guide/examples/guide_style.json"


def _resolve_style(rel: str) -> str:
    """Resolve a style file path against the repo root with an allow-list."""
    p = (REPO / rel).resolve()
    for allowed in (GUIDE_ROOT, STYLE_DIR):
        try:
            p.relative_to(allowed.resolve())
            if p.exists() and p.suffix == '.json':
                return str(p)
        except ValueError:
            continue
    raise HTTPException(400, f"style not allowed: {rel}")


# In-memory LRU on (code+spec) hash. Examples that don't change (e.g. user
# reloaded the page but hasn't edited yet) serve instantly.
_cache: dict[str, tuple[float, str]] = {}
_CACHE_MAX = 128


def _cache_key(req: RenderRequest) -> str:
    h = hashlib.sha256()
    payload = req.model_dump_json().encode()
    h.update(payload)
    return h.hexdigest()


@app.post("/render")
def render(req: RenderRequest):
    key = _cache_key(req)
    cached = _cache.get(key)
    if cached:
        t0, svg = cached
        _cache[key] = (time.time(), svg)  # touch
        return Response(content=svg, media_type="image/svg+xml",
                        headers={"X-Render-Time-Ms": "0", "X-Cache": "hit"})

    try:
        spec = ExampleSpec(
            code=req.code,
            w=req.w, h=req.h, scale=req.scale,
            labels=list(req.labels),
            tex_labels=dict(req.tex_labels),
            hide=list(req.hide),
            overrides=dict(req.overrides),
            rendering_extra=dict(req.rendering_extra),
            overlay_extra=dict(req.overlay_extra),
            auto_place=req.auto_place,
            style=_resolve_style(req.style),
        )
        t0 = time.time()
        svg = render_example(spec)
        elapsed_ms = int((time.time() - t0) * 1000)
    except HTTPException:
        raise
    except Exception as e:
        return Response(
            content=f'{{"error": "{type(e).__name__}: {str(e)[:500]}"}}',
            media_type="application/json", status_code=400,
        )

    # Evict oldest when over capacity
    if len(_cache) >= _CACHE_MAX:
        oldest = min(_cache.items(), key=lambda kv: kv[1][0])[0]
        _cache.pop(oldest, None)
    _cache[key] = (time.time(), svg)

    return Response(content=svg, media_type="image/svg+xml",
                    headers={"X-Render-Time-Ms": str(elapsed_ms),
                             "X-Cache": "miss"})


# ── Static content ───────────────────────────────────────────────────

# GGB source files that ship alongside examples. Individual pages add
# <a href="/ggb/<name>.ggb" download> when a picture derives from a
# GeoGebra construction the reader may want to open locally.
GGB_DIR = GUIDE_ROOT / 'assets' / 'ggb'
GGB_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/ggb",
    StaticFiles(directory=str(GGB_DIR)),
    name="ggb_assets",
)

# Everything (HTML pages, css/js, assets/) served from docs/guide/. The guide
# now owns its assets — the generated SVGs and diagrams live in
# docs/guide/assets/ (the guide owns its asset tree).
app.mount("/", StaticFiles(directory=str(GUIDE_ROOT), html=True), name="guide")


def main():
    import uvicorn
    port = 8765
    print(f"AnimaGeo guide → http://127.0.0.1:{port}/")
    print("  (local only; executes arbitrary Python via /render — do not expose)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
