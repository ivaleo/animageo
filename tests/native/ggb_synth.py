"""Small synthetic ``.ggb`` files for the L5 import tests.

``ggb_bytes(body)`` packs a ``<construction>`` body into a zip with the
``geogebra.xml`` and the default ``geogebra_javascript.js`` of every GGB file;
``point``, ``element``, ``command``, ``expression`` write the XML nodes the
way GeoGebra 5 writes them.
"""
from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import quoteattr

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
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('geogebra.xml', xml if xml is not None else ggb_xml(body, app=app))
        zf.writestr('geogebra_javascript.js', js)
        if macro is not None:
            zf.writestr('geogebra_macro.xml', macro)
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


def triangle(extra: str = '') -> str:
    """A, B, C and the triangle ``t1`` with its sides — the base of most cases."""
    return (point('A', 0.0, 0.0) + point('B', 4.0, 0.0) + point('C', 1.0, 3.0)
            + command('Polygon', ['A', 'B', 'C'], ['t1', 'c', 'a', 'b'])
            + element('polygon', 't1', alpha=0.1) + element('segment', 'c', extra=line_style())
            + element('segment', 'a', extra=line_style()) + element('segment', 'b', extra=line_style())
            + extra)
