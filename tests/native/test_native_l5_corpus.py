"""The deliberate ``.ggb`` files (plan L5 §8, stage 3; 1.10.0a2)."""
import zipfile

import pytest

from animageo.native.convert import from_ggb
from tests.native.ggb_synth import SYNTHETIC, SYNTHETIC_DIR, ggb_bytes, triangle
from tests.native.test_native_l5_ggb import NS, _check

# what each deliberate file is for: {ggb_name: (category, reason)}, the dropped kinds, or the refusal
PURPOSE = {
    'triangle_editable': {'all': 'editable'},
    'value_mismatch': {'M': ('differs', 'value_mismatch')},
    'intersections': {'all': 'editable'},
    'breakpoints': {'all': 'editable', 'steps': 3},
    'scripts_and_button': {'t1': ('picture', 'script'), 'b1': ('unsupported', 'script'), 'dropped': {'script'}},
    'list': {'L': ('unsupported', 'list'), 'L2': ('unsupported', 'list')},
    'macro': {'D': ('editable', None), 'warnings': {'macros_expanded'}},
    'three_d': {'P': ('unsupported', '3d'), 'p': ('unsupported', '3d'), 'dropped': {'3d'}},
    'cas': {'dropped': {'cas'}},
    'spreadsheet': {'A1': ('editable', None), 'B1': ('unsupported', 'parse_error'),
                    'P': ('closure', 'depends_on_unsupported')},
    'dtd': {'refused': 'ggb_invalid'},
    'not_a_ggb': {'refused': 'import_not_ggb'},
    'pictures_only': {'t1': ('picture', 'fixed_text'), 't2': ('picture', 'latex_macros'),
                      'pic1': ('unsupported', 'image'), 'document': False},
    'texts': {'t1': ('editable', None), 't2': ('picture', 'fixed_text'), 't3': ('picture', 'fixed_text')},
    'function_closure': {'f': ('unsupported', 'formula_unsupported'), 'P': ('closure', 'depends_on_unsupported'),
                         'M': ('closure', 'depends_on_unsupported')},
    'formula_argument': {"I'": ('picture', 'formula_unsupported'), 'M': ('picture', 'depends_on_unsupported')},
    'dropped_effects': {'all': 'editable',
                        'dropped': {'conditional_visibility', 'dynamic_color', 'animation', 'layers'}},
    'random_point': {'R': ('picture', 'random_point')},
    'style_labels': {'all': 'editable'},
    'ui_objects': {'tf': ('unsupported', 'ui_object'), 'cb': ('unsupported', 'ui_object'), 'n': ('editable', None)},
    'regular_polygon': {'poly1': ('editable', None), 'poly2': ('unsupported', 'unsupported_signature')},
}


def test_the_files_are_the_output_of_the_generator():
    """``tests/native/import/synthetic/`` is ``python -m tests.native.ggb_synth``:
    the same entries in the same order, with the same bytes, dates and method
    (the deflated bytes themselves depend on the zlib of the machine)."""
    on_disk = sorted(p.stem for p in SYNTHETIC_DIR.glob('*.ggb'))
    assert on_disk == sorted(SYNTHETIC)
    assert len(SYNTHETIC) >= 15
    for name, (purpose, build) in SYNTHETIC.items():
        assert purpose, name
        with zipfile.ZipFile(SYNTHETIC_DIR / f'{name}.ggb') as disk, zipfile.ZipFile(_bytes_io(build())) as fresh:
            assert [_entry(disk, i) for i in disk.infolist()] == [_entry(fresh, i) for i in fresh.infolist()], name


def _bytes_io(data):
    import io
    return io.BytesIO(data)


def _entry(zf, info):
    return info.filename, info.date_time, info.compress_type, info.external_attr, zf.read(info)


def test_the_generator_is_reproducible():
    for _, build in SYNTHETIC.values():
        assert build() == build()
    assert ggb_bytes(triangle()) == ggb_bytes(triangle())


@pytest.mark.parametrize('name', sorted(PURPOSE))
def test_each_file_shows_what_it_is_for(name):
    data = (SYNTHETIC_DIR / f'{name}.ggb').read_bytes()
    want = PURPOSE[name]
    if 'refused' in want:
        from animageo.native.convert import ImportRefused
        with pytest.raises(ImportRefused) as exc:
            from_ggb(data, id_namespace=NS)
        assert exc.value.code == want['refused']
        return
    doc, rep = from_ggb(data, id_namespace=NS, name=f'{name}.ggb')
    _check(doc, rep)
    by_name = {e['ggb_name']: e for e in rep['elements']}
    if want.get('all'):
        assert {e['category'] for e in rep['elements']} == {want['all']}
    for label, (category, reason) in ((k, v) for k, v in want.items() if isinstance(v, tuple)):
        assert (by_name[label]['category'], by_name[label].get('reason')) == (category, reason), label
    if 'dropped' in want:
        assert {d['kind'] for d in rep['dropped']} == want['dropped']
    if 'warnings' in want:
        assert want['warnings'] <= {w['code'] for w in rep['warnings']}
    if 'document' in want:
        assert (doc is not None) == want['document']
    if 'steps' in want:
        assert len(doc['steps']) == want['steps']


def test_every_deliberate_file_has_a_purpose():
    assert set(PURPOSE) == set(SYNTHETIC)
