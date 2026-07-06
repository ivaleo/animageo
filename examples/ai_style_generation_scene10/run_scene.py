from __future__ import annotations

import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(HERE))

from animageo import AnimaGeoScene


GGB_FILE = HERE / "scene10.ggb"
STYLE_FILE = HERE / "style.json"
AI_STYLE_DSL = HERE / "ai_style.dsl.py"
SUMMARY_FILE = HERE / "summary.json"
SVG_FILE = HERE / "scene10.svg"


class Scene10AIStyleTest(AnimaGeoScene):
    def construct(self):
        self.loadGGB(
            str(GGB_FILE),
            style=str(STYLE_FILE),
            export={"size": {"width": 150, "height": "auto"}},
            debug=False,
            generate_stubs=True,
        )

        self.exportStylePromptSummary(
            str(SUMMARY_FILE),
            include_geometry=True,
            include_ggb_style=True,
            include_style=False,
            include_resolved_style=False,
        )

        if AI_STYLE_DSL.exists():
            self.loadCode(str(AI_STYLE_DSL), debug=False)

        if self.style.rendering.get("label_placement", {}).get("enabled"):
            self.autoPlaceLabels(dynamic=False)

        self.updateAllGeometry()
        self.exportSVG(str(SVG_FILE))


if __name__ == "__main__":
    Scene10AIStyleTest().construct()
    print(f"summary: {os.path.relpath(SUMMARY_FILE, REPO_ROOT)}")
    print(f"svg:     {os.path.relpath(SVG_FILE, REPO_ROOT)}")
