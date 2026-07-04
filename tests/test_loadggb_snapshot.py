"""Snapshot baseline for ggb_parser.load() output.

Serializes elem.style and elem.ggb_style for every element of fixture .ggb files to JSON and
compares against checked-in snapshots in tests/snapshots/. If no snapshot
exists, one is created (first run). On subsequent runs, any drift is flagged.

Purpose: lock in both explicit/intrinsic element style and the normalized GGB
import layer so faithful-mode behavior can be verified byte-for-byte.

To regenerate after an intended behavior change, delete the corresponding
JSON file in tests/snapshots/ and re-run the suite once.
"""
import json
import os

import pytest

from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser


FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), '..', 'examples', '0_sample_scenes'
)
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), 'snapshots')
FIXTURES = ['scene.ggb', 'scene3.ggb']


def _json_safe(value):
    """Convert elem.style value to JSON-representable form."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return f'<non-json: {type(value).__name__}>'


def _serialize_construction(c):
    """Capture per-element style/import-style in a deterministic, diffable form."""
    result = {}
    for elem in c.elements:
        key = elem.name
        style_dict = {k: _json_safe(v) for k, v in sorted(elem.style.items())}
        ggb_style_dict = {k: _json_safe(v) for k, v in sorted(getattr(elem, 'ggb_style', {}).items())}
        result[key] = {
            'type': type(elem.data).__name__ if elem.data is not None else None,
            'style': style_dict,
            'ggb_style': ggb_style_dict,
        }
    return dict(sorted(result.items()))


def _parse(path):
    c = Construction()
    view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}
    ggb_parser.load(c, view, path, debug=False)
    return c


@pytest.mark.parametrize('fixture', FIXTURES)
def test_loadggb_snapshot(fixture):
    ggb_path = os.path.join(FIXTURES_DIR, fixture)
    if not os.path.isfile(ggb_path):
        pytest.skip(f'Fixture not found: {ggb_path}')

    c = _parse(ggb_path)
    actual = _serialize_construction(c)

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    snapshot_path = os.path.join(SNAPSHOT_DIR, fixture.replace('.ggb', '.json'))

    if not os.path.isfile(snapshot_path):
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(actual, f, indent=2, ensure_ascii=False, sort_keys=True)
        pytest.skip(f'Created new snapshot: {snapshot_path}. Re-run to verify.')

    with open(snapshot_path, 'r', encoding='utf-8') as f:
        expected = json.load(f)

    assert actual == expected, (
        f'Snapshot drift detected for {fixture}. '
        f'If this change is intentional, delete {snapshot_path} and re-run.'
    )
