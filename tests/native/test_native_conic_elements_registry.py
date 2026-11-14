"""The additive conic-elements catalog and its frozen predecessors."""
import hashlib
import json

from animageo import native
from animageo.native.kernel.ops import IMPLEMENTATIONS
from animageo.native.registry import registry, registry_problems, signature_hash, _MODULE_GROUPS
from tests.native.conftest import REPO_ROOT

NAMES = {'conic.from_circle', 'conic.directrices', 'conic.asymptotes',
         'line.polar_conic', 'line.conjugate_diameter'}


def test_catalog_and_import_capability_are_complete():
    reg = registry()
    assert reg.version == native.__registry_version__ == '1.13'
    assert len(reg.ops) == 132
    assert native.has('conic_elements')
    assert set(reg.groups['conic_elements']) == NAMES
    assert {k for k, v in _MODULE_GROUPS.items() if v == 'conic_elements'} == NAMES
    assert set(IMPLEMENTATIONS) == set(reg.ops)
    assert registry_problems() == []
    for name in NAMES:
        r = reg.get(name)
        assert r['since'] == '1.13' and r['status'] == 'beta'
        assert r['free'] is None and r['pathParam'] is None
        assert signature_hash(r) == r['signatureHash']
        assert (REPO_ROOT / r['math']).is_file()
    adapter = reg.get('conic.from_circle')
    assert adapter['outputs'] == [{'slot': 'conic', 'type': 'conic'}]
    assert adapter['helper'] == {'ownership': 'owned', 'role': 'aux'}


def _content_digest(path):
    """File digest that ignores the release stamp of parity fixtures."""
    data = path.read_bytes()
    if path.suffix == '.json':
        doc = json.loads(data)
        if isinstance(doc, dict):
            doc.pop('generatedBy', None)
        data = json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    return hashlib.sha256(data).hexdigest()


def test_all_operations_through_1_12_and_old_conic_fixtures_stay_frozen():
    frozen = json.loads((REPO_ROOT / 'tests/native/registry_frozen_1_12.json').read_text())
    assert len(frozen['ops']) == 127
    old = {k: v for k, v in registry().ops.items() if k not in NAMES}
    assert set(old) == set(frozen['ops'])
    for name, r in old.items():
        assert {'signatureHash': signature_hash(r), 'since': r['since']} == frozen['ops'][name]
    for name, digest in frozen['unchangedFiles'].items():
        assert _content_digest(REPO_ROOT / name) == digest, name


def test_repeated_slot_policies_and_reasons():
    for name, base in [('conic.directrices', 'directrix'), ('conic.asymptotes', 'asymptote')]:
        r = registry().get(name)
        assert r['outputs'] == [{'slot': base, 'type': 'line', 'repeat': 'count'}]
        assert r['params'][0]['default'] == 2
        assert r['branch']['policy'] in registry().policies
    for reason in ('no_directrix', 'no_asymptote', 'no_finite_line'):
        assert registry().reasons[reason]['state'] == 'undefined'
