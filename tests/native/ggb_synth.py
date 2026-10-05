"""Small synthetic ``.ggb`` files for the L5 import tests.

``ggb_bytes(body)`` packs a ``<construction>`` body into a zip with the
``geogebra.xml`` and the default ``geogebra_javascript.js`` of every GGB file;
``point``, ``element``, ``command``, ``expression`` write the XML nodes the
way GeoGebra 5 writes them. The archive is reproducible: every entry has the
same date and attributes.

:data:`SYNTHETIC` — the deliberate files of ``tests/native/import/synthetic/``
(plan L5 §8: 3D, CAS, a spreadsheet, scripts, a list, a macro, a button,
breakpoints, a DTD, …), each with what it is for. The files are the output of
this module (``test_native_l5_corpus.py`` compares them); after a change::

    python -m tests.native.ggb_synth            # rewrites tests/native/import/synthetic/
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

SYNTHETIC_DIR = Path(__file__).resolve().parent / 'import' / 'synthetic'
_DATE = (2026, 10, 5, 0, 0, 0)

DEFAULT_JS = 'function ggbOnInit() {}'


def _attrs(d: dict) -> str:
    return ' '.join(f'{k}={quoteattr(str(v))}' for k, v in d.items())


def element(type_: str, label: str, *, show: bool = True, label_shown: bool = True, color=(21, 101, 192),
            alpha: float = 0.0, extra: str = '') -> str:
    r, g, b = color
    return (f'<element type="{type_}" label={quoteattr(label)}>'
            f'<show object="{str(show).lower()}" label="{str(label_shown).lower()}"/>'
            f'<objColor r="{r}" g="{g}" b="{b}" alpha="{alpha}"/><layer val="0"/><labelMode val="0"/>'
            f'{extra}</element>')


def point(label: str, x: float, y: float, **kw) -> str:
    extra = kw.pop('extra', '')
    return element('point', label, extra=f'<pointSize val="5"/><pointStyle val="0"/>'
                                         f'<coords x="{x!r}" y="{y!r}" z="1"/>{extra}', **kw)


def command(name: str, inputs, outputs) -> str:
    inp = _attrs({f'a{i}': v for i, v in enumerate(inputs)})
    out = _attrs({f'a{i}': v for i, v in enumerate(outputs)})
    return f'<command name={quoteattr(name)}><input {inp}/><output {out}/></command>'


def expression(label: str, exp: str, type_: str | None = None) -> str:
    t = f' type="{type_}"' if type_ else ''
    return f'<expression label={quoteattr(label)} exp={quoteattr(exp)}{t}/>'


def line_style(thickness: int = 5, type_: int = 0, opacity: int = 178) -> str:
    return f'<lineStyle thickness="{thickness}" type="{type_}" typeHidden="1" opacity="{opacity}"/>'


def ggb_xml(body: str, *, app: str = 'classic', prolog: str = '') -> bytes:
    return (f'<?xml version="1.0" encoding="utf-8"?>{prolog}'
            f'<geogebra format="5.0" version="5.4.927.1" app="{app}" platform="w">'
            '<euclidianView><size width="800" height="600"/>'
            '<coordSystem xZero="400" yZero="300" scale="50" yscale="50"/></euclidianView>'
            '<kernel><decimals val="2"/></kernel>'
            f'<construction title="" author="" date="">{body}</construction></geogebra>').encode('utf-8')


def ggb_bytes(body: str = '', *, js: str = DEFAULT_JS, app: str = 'classic', xml: bytes | None = None,
              macro: bytes | None = None, extra: dict | None = None) -> bytes:
    entries = {'geogebra.xml': xml if xml is not None else ggb_xml(body, app=app), 'geogebra_javascript.js': js}
    if macro is not None:
        entries['geogebra_macro.xml'] = macro
    entries.update(extra or {})
    return zip_bytes(entries)


def zip_bytes(entries: dict) -> bytes:
    """A deflated zip of ``{name: bytes | str}`` with fixed dates and attributes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    return buf.getvalue()


def triangle(extra: str = '') -> str:
    """A, B, C and the triangle ``t1`` with its sides — the base of most cases."""
    return (point('A', 0.0, 0.0) + point('B', 4.0, 0.0) + point('C', 1.0, 3.0)
            + command('Polygon', ['A', 'B', 'C'], ['t1', 'c', 'a', 'b'])
            + element('polygon', 't1', alpha=0.1) + element('segment', 'c', extra=line_style())
            + element('segment', 'a', extra=line_style()) + element('segment', 'b', extra=line_style())
            + extra)


# ── the deliberate files (tests/native/import/synthetic/) ─────────────────

CIRCLE_R3 = '<matrix A0="1" A1="1" A2="-9" A3="0" A4="0" A5="0"/>'
_SLIDER = ('<slider min="0" max="5" width="200" x="10" y="10" fixed="true" horizontal="true" '
           'showAlgebra="true"/>')


def _text(label: str, exp: str, start: str, *, latex: bool = False) -> str:
    return (expression(label, exp)
            + element('text', label, extra=f'{start}<isLaTeX val="{str(latex).lower()}"/>'))


def _macro_xml() -> bytes:
    """The user tool ``Mid3(A, B, C)``: the midpoint of the side ``AB`` of a triangle."""
    return ('<?xml version="1.0" encoding="utf-8"?><geogebra format="5.0">'
            '<macro cmdName="Mid3" toolName="Mid3" toolHelp="" iconFile="" showInToolBar="true">'
            '<macroInput a0="P" a1="Q" a2="R"/><macroOutput a0="S"/><construction>'
            + element('point', 'P') + element('point', 'Q') + element('point', 'R')
            + command('Midpoint', ['P', 'Q'], ['S']) + element('point', 'S')
            + '</construction></macro></geogebra>').encode('utf-8')


def _synthetic() -> dict:
    tri = triangle()
    return {
        'triangle_editable': (
            'a triangle, its midpoint, circumcircle and a slider: everything editable',
            lambda: ggb_bytes(tri + command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.0, 0.0)
                              + command('Circle', ['A', 'B', 'C'], ['k'])
                              + element('conic', 'k', extra='<matrix A0="1" A1="1" A2="0" A3="0" A4="-2" A5="-1"/>')
                              + element('numeric', 'n', extra=f'<value val="2"/>{_SLIDER}'))),
        'value_mismatch': (
            'a midpoint saved away from its value: differs with a delta',
            lambda: ggb_bytes(tri + command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.5, 0.0))),
        'intersections': (
            'a line and a circle: two intersection points matched by value, and the indexed form',
            lambda: ggb_bytes(point('A', -3.0, 0.0) + point('B', 3.0, 0.0) + command('Line', ['A', 'B'], ['g'])
                              + element('line', 'g', extra='<coords x="0" y="1" z="0"/>') + point('O', 0.0, 0.0)
                              + command('Circle', ['O', 'B'], ['k']) + element('conic', 'k', extra=CIRCLE_R3)
                              + command('Intersect', ['g', 'k'], ['F', 'E']) + point('F', -3.0, 0.0)
                              + point('E', 3.0, 0.0) + command('Intersect', ['g', 'k', '2'], ['G'])
                              + point('G', -3.0, 0.0))),
        'breakpoints': (
            'breakpoints of the construction protocol: steps',
            lambda: ggb_bytes(point('A', 0.0, 0.0, extra='<breakpoint val="true"/>') + point('B', 4.0, 0.0)
                              + command('Segment', ['A', 'B'], ['s'])
                              + element('segment', 's', extra='<coords x="0" y="1" z="0"/><breakpoint val="true"/>')
                              + command('Midpoint', ['s'], ['M']) + point('M', 2.0, 0.0))),
        'scripts_and_button': (
            'a button with a script, an object with a GGB script, a global ggbOnInit: dropped, never run',
            lambda: ggb_bytes(tri.replace('<labelMode val="0"/></element>',
                                          '<labelMode val="0"/><ggbscript val="SetValue[a,1]"/></element>', 1)
                              + element('button', 'b1', extra='<javascript val="alert(1)"/>'),
                              js='function ggbOnInit() { ggbApplet.evalCommand("B=(1,1)") }')),
        'list': (
            'lists of numbers and of points: unsupported',
            lambda: ggb_bytes(point('A', 0.0, 0.0) + point('B', 1.0, 1.0)
                              + expression('L', '{1, 2, 3}') + element('list', 'L')
                              + expression('L2', '{A, B}') + element('list', 'L2'))),
        'macro': (
            'a user tool (macro) used once: expanded, its output translates, the warning names the tool',
            lambda: ggb_bytes(tri + command('Mid3', ['A', 'B', 'C'], ['D']) + point('D', 2.0, 0.0),
                              macro=_macro_xml())),
        'three_d': (
            'a 3D point and a plane in a 3D file',
            lambda: ggb_bytes(point('A', 0.0, 0.0) + point('B', 1.0, 0.0) + point('C', 0.0, 1.0)
                              + element('point3d', 'P', extra='<coords x="1" y="2" z="3" w="1"/>')
                              + command('Plane', ['A', 'B', 'C'], ['p']) + element('plane3d', 'p'),
                              app='3d')),
        'cas': (
            'cells of the CAS view: dropped',
            lambda: ggb_bytes(point('A', 0.0, 0.0)
                              + '<cascell caslabel="$1"><inputCell><expression value="x+1"/></inputCell></cascell>'
                              + '<cascell><inputCell><expression value="Solve(x^2=4)"/></inputCell></cascell>')),
        'spreadsheet': (
            'objects of spreadsheet cells A1, B1 and a point by them (an implicit product the classic does not parse)',
            lambda: ggb_bytes(element('numeric', 'A1', extra='<value val="3"/>')
                              + expression('B1', '2 A1') + element('numeric', 'B1', extra='<value val="6"/>')
                              + expression('P', '(A1, B1)') + point('P', 3.0, 6.0))),
        'dtd': (
            'a DOCTYPE with an entity: refused before parsing',
            lambda: ggb_bytes(xml=('<?xml version="1.0" encoding="utf-8"?><!DOCTYPE geogebra '
                                   '[<!ENTITY x "x">]><geogebra format="5.0"><construction/></geogebra>')
                              .encode('utf-8'))),
        'not_a_ggb': (
            'a zip without geogebra.xml: refused',
            lambda: zip_bytes({'readme.txt': 'not a GeoGebra file'})),
        'pictures_only': (
            'texts, a LaTeX text and an image only: nothing editable, no document',
            lambda: ggb_bytes(_text('t1', '"Задача 1"', '<startPoint x="1" y="2" z="1"/>')
                              + _text('t2', '"$\\sqrt{2}$"', '<startPoint x="1" y="1" z="1"/>', latex=True)
                              + element('image', 'pic1'))),
        'texts': (
            'a fixed text, a text at a point, a text with values of objects',
            lambda: ggb_bytes(tri + _text('t1', '"Треугольник"', '<startPoint x="0" y="4" z="1"/>')
                              + _text('t2', '"вершина"', '<startPoint exp="A"/>')
                              + _text('t3', '"AB = " + c + ", A = " + A', '<startPoint x="2" y="-1" z="1"/>'))),
        'function_closure': (
            'a function, a point on it and their dependents: unsupported and closure',
            lambda: ggb_bytes(point('A', 0.0, 0.0) + expression('f', 'x^2') + element('function', 'f')
                              + command('Point', ['f'], ['P']) + point('P', 1.0, 1.0)
                              + command('Segment', ['A', 'P'], ['s'])
                              + element('segment', 's', extra='<coords x="1" y="-1" z="0"/>')
                              + command('Midpoint', ['s'], ['M']) + point('M', 0.5, 0.5))),
        'formula_argument': (
            'a rotation by an expression of a slider: a picture and its dependents',
            lambda: ggb_bytes(element('angle', 'α', extra='<value val="1.7"/>' + _SLIDER.replace('max="5"',
                                                                                              'max="6.28"'))
                              + point('I', 1.0, 0.0) + point('G', 0.0, 0.0)
                              + command('Rotate', ['I', '(4 * (α - 90°))', 'G'], ["I'"]) + point("I'", 0.0, 1.0)
                              + command('Midpoint', ["I'", 'G'], ['M']) + point('M', 0.0, 0.5))),
        'dropped_effects': (
            'conditional visibility, dynamic colour, animation and layers: dropped with warnings',
            lambda: ggb_bytes(tri + command('Midpoint', ['A', 'B'], ['M'])
                              + point('M', 2.0, 0.0, extra='<condition showObject="a&gt;1"/><dynamicColor val1="1" '
                                                           'val2="0" val3="0"/><animation step="0.1" speed="1" '
                                                           'type="0" playing="true"/>')
                              + point('Q', 1.0, 1.0).replace('<layer val="0"/>', '<layer val="2"/>'))),
        'random_point': (
            'a random point in a polygon: a picture',
            lambda: ggb_bytes(tri + command('RandomPointIn', ['t1'], ['R']) + point('R', 1.0, 1.0))),
        'style_labels': (
            'colours, thickness, dash, point size, a caption, a hidden object, a hidden label',
            lambda: ggb_bytes(point('A', 0.0, 0.0) + point('B', 4.0, 0.0, show=False)
                              + point('C', 1.0, 3.0, label_shown=False, color=(0, 128, 0))
                              + command('Segment', ['A', 'B'], ['s'])
                              + element('segment', 's', color=(255, 0, 0),
                                        extra=line_style(thickness=6, type_=15, opacity=255)
                                        + '<coords x="0" y="1" z="0"/>').replace(
                                  '<labelMode val="0"/>', '<labelMode val="3"/><caption val="основание"/>')
                              + command('Polygon', ['A', 'B', 'C'], ['t1', 'c', 'a', 'b'])
                              + element('polygon', 't1', color=(255, 200, 0), alpha=0.25)
                              + element('segment', 'c', extra=line_style(thickness=3))
                              + element('segment', 'a', extra=line_style(thickness=3, type_=10))
                              + element('segment', 'b', extra=line_style(thickness=3)))),
        'ui_objects': (
            'a text field, a check box and a slider: the slider is a number, the rest are user interface',
            lambda: ggb_bytes(element('textfield', 'tf') + element('boolean', 'cb', extra='<value val="true"/>')
                              + element('numeric', 'n', extra=f'<value val="1"/>{_SLIDER}'))),
        'regular_polygon': (
            'a regular pentagon on two points, and one of 200 vertices (more than the kernel takes)',
            lambda: ggb_bytes(point('A', 0.0, 0.0) + point('B', 1.0, 0.0)
                              + command('Polygon', ['A', 'B', '5'], ['poly1'])
                              + element('polygon', 'poly1')
                              + command('Polygon', ['B', 'A', '200'], ['poly2'])
                              + element('polygon', 'poly2'))),
    }


SYNTHETIC = _synthetic()


def write_synthetic(directory: Path = SYNTHETIC_DIR) -> list:
    """Write every file of :data:`SYNTHETIC` as ``<name>.ggb`` into ``directory``
    and drop the other ``*.ggb`` there; the written paths."""
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob('*.ggb'):
        if old.stem not in SYNTHETIC:
            old.unlink()
    out = []
    for name, (_purpose, build) in SYNTHETIC.items():
        path = directory / f'{name}.ggb'
        path.write_bytes(build())
        out.append(path)
    return out


if __name__ == '__main__':
    for p in write_synthetic(Path(sys.argv[1]) if len(sys.argv) > 1 else SYNTHETIC_DIR):
        print(p)
