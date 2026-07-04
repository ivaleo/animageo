import json

import numpy as np

from animageo.exporters.construction_summary import (
    SCHEMA_ID,
    construction_to_ai_summary,
    write_ai_summary,
)
from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Angle, Element, Point, Segment


def _sample_construction():
    c = Construction()
    c.add(Element("A", Point([0, 0])))
    c.add(Element("B", Point([3, 0])))
    c.add(Element("C", Point([0, 4])))
    c.add(Command("Segment", ["A", "B"], ["AB"]))
    c.rebuild(full=True)
    c.add(Element("alpha", Angle(np.array([0, 0]), np.array([3, 0]), np.array([0, 4]))))

    c.element("A").ggb_style.update({
        "size_px": 10,
        "fill": "#1565c0",
        "label_visible": True,
    })
    c.element("AB").ggb_style.update({
        "stroke": "#1565c0",
        "stroke_width_px": 2.5,
    })
    c.element("AB").ggb_raw.update({
        "elem_type": "segment",
        "line_thickness": 5,
        "line_opacity": 204,
    })
    return c


def test_construction_to_ai_summary_shape():
    c = _sample_construction()

    summary = construction_to_ai_summary(
        c,
        source={"kind": "test", "name": "unit"},
        viewport={"size": [800, 600], "ptUnit_ggb": 50},
    )

    assert summary["schema"] == SCHEMA_ID
    assert summary["source"]["kind"] == "test"
    assert summary["viewport"]["size"] == [800, 600]
    assert summary["stats"]["point"] == 3
    assert summary["stats"]["segment"] == 1
    assert "xAxis" not in summary["groups"].get("lines", [])

    by_name = {item["name"]: item for item in summary["elements"]}
    assert by_name["A"]["type"] == "point"
    assert by_name["A"]["geometry"]["coords"] == [0.0, 0.0]
    assert by_name["A"]["ggb_style"]["size_px"] == 10

    assert by_name["AB"]["type"] == "segment"
    assert by_name["AB"]["construction"]["command"] == "Segment"
    assert by_name["AB"]["construction"]["inputs"] == ["A", "B"]
    assert by_name["AB"]["geometry"]["length"] == 3.0
    assert by_name["AB"]["ggb_raw_summary"]["line_thickness"] == 5

    assert by_name["alpha"]["type"] == "angle"
    assert by_name["alpha"]["geometry"]["size_deg"] == 90.0


def test_write_ai_summary_roundtrip(tmp_path):
    c = _sample_construction()
    path = tmp_path / "summary.json"

    written = write_ai_summary(c, path, include_geometry=False, max_elements=2)
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded == written
    assert loaded["schema"] == SCHEMA_ID
    assert loaded["truncated"]["omitted_count"] > 0
    assert all("geometry" not in item for item in loaded["elements"])
