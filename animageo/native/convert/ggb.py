"""``from_ggb``: a ``.ggb`` file → document + ``import_report.v1`` (plan L5 §3.5).

A ``.ggb`` is untrusted input (plan §7): the limits are checked before any
parsing (zip entries ≤ 50, unpacked ≤ 50 MB, ``geogebra.xml`` ≤ 10 MB and
read no further than that, objects ≤ 3000, XML depth ≤ 64), a ``<!DOCTYPE``
or ``<!ENTITY`` refuses the file (``ggb_invalid``, decision 10), nothing is
extracted to disk and GGB scripts (JavaScript, GGBScript) are only counted.
A refusal is :class:`ImportRefused` ``(code, detail)``.

The XML is scanned once: every ``<element>`` gives its label, type, the
command that produced it, style, value, layer and visibility; global
features go to ``dropped``. The construction is parsed by the classic
``ggb_parser.parse_constr`` on the scanned tree and translated by
:func:`~.construction.translate` with keys ``ggb:<label>``; every
``<element>`` of the XML is exactly one entry of the report.
"""
from __future__ import annotations

import hashlib
import io
import lzma
import math
import re
import zipfile
import zlib
from dataclasses import dataclass, field
from xml.etree import ElementTree

__all__ = ['ImportRefused', 'LIMITS', 'GgbFile', 'read_ggb', 'scan', 'DEFAULT_JS']

LIMITS = {
    'file_bytes': 20 * 1024 * 1024,
    'entries': 50,
    'unpacked_bytes': 50 * 1024 * 1024,
    'xml_bytes': 10 * 1024 * 1024,
    'objects': 3000,
    'depth': 64,
    'label_chars': 200,
}

# What a damaged archive raises while an entry is read: a bad header or
# CRC, an unknown or encrypted method, a broken deflate, bzip2 or lzma stream.
_ZIP_ERRORS = (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, OSError, RuntimeError, EOFError,
               NotImplementedError, zlib.error, lzma.LZMAError, OverflowError, KeyError, IndexError)

# What GeoGebra writes into geogebra_javascript.js when there is no script.
DEFAULT_JS = re.compile(rb'^\s*function\s+ggbOnInit\s*\(\s*\)\s*\{\s*\}\s*$')

TYPES_3D = frozenset({'point3d', 'vector3d', 'segment3d', 'line3d', 'ray3d', 'polygon3d', 'conic3d', 'plane3d',
                      'plane', 'quadric', 'quadricpart', 'quadriclimited', 'polyhedron', 'net', 'surfacecartesian',
                      'surfacecartesian3d', 'implicitsurface', 'curvecartesian3d', 'spacecurve', 'conicpart3d',
                      'polyline3d', 'axis3d'})
TYPES_UI = frozenset({'button', 'textfield', 'boolean', 'dropdown'})
TYPES_FORMULA = frozenset({'function', 'functionnvar', 'implicitpoly', 'curvecartesian', 'inequality',
                           'interval', 'implicitcurve'})
COMMANDS_3D = frozenset({'Sphere', 'Plane', 'Pyramid', 'Prism', 'Cube', 'Cone', 'Cylinder', 'Tetrahedron',
                         'Octahedron', 'Dodecahedron', 'Icosahedron', 'Net', 'Surface', 'PerpendicularPlane',
                         'PlaneBisector', 'Point3D'})
PLACEABLE = ('point', 'segment', 'polygon', 'text')


class ImportRefused(Exception):
    """The file is refused before parsing: ``code`` — ``import_too_large``,
    ``import_not_ggb``, ``import_too_many_objects`` or ``ggb_invalid``."""

    def __init__(self, code: str, detail: str = ''):
        super().__init__(f'{code}: {detail}' if detail else code)
        self.code = code
        self.detail = detail[:500]


@dataclass
class GgbFile:
    name: str
    size: int
    sha256: str
    xml: bytes
    macro_xml: bytes | None = None
    javascript: bytes | None = None
    entries: list = field(default_factory=list)


def _limits(limits):
    out = dict(LIMITS)
    out.update(limits or {})
    return out


def _bounded_read(zf, info, cap: int) -> bytes:
    with zf.open(info) as fh:
        data = fh.read(cap + 1)
    if len(data) > cap:
        raise ImportRefused('import_too_large', f'{info.filename} больше {cap} байт')
    return data


def read_ggb(path_or_bytes, *, name: str | None = None, limits=None) -> GgbFile:
    """The parts of a ``.ggb`` the import reads, within the limits."""
    lim = _limits(limits)
    if isinstance(path_or_bytes, (bytes, bytearray, memoryview)):
        raw = bytes(path_or_bytes)
        if len(raw) > lim['file_bytes']:
            raise ImportRefused('import_too_large', f'файл больше {lim["file_bytes"]} байт')
        name = name or 'file.ggb'
    else:
        import os
        path = os.fspath(path_or_bytes)
        size = os.path.getsize(path)
        if size > lim['file_bytes']:
            raise ImportRefused('import_too_large', f'файл больше {lim["file_bytes"]} байт')
        with open(path, 'rb') as fh:
            raw = fh.read(lim['file_bytes'] + 1)
        name = name or os.path.basename(path)
    sha = hashlib.sha256(raw).hexdigest()
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        infos = zf.infolist()
    except _ZIP_ERRORS as exc:
        raise ImportRefused('import_not_ggb', f'не zip-архив: {exc}') from None
    if len(infos) > lim['entries']:
        raise ImportRefused('import_too_large', f'записей в архиве {len(infos)} > {lim["entries"]}')
    total = sum(max(0, int(i.file_size)) for i in infos)
    if total > lim['unpacked_bytes']:
        raise ImportRefused('import_too_large', f'распакованно {total} байт > {lim["unpacked_bytes"]}')
    by_name = {i.filename: i for i in infos}
    xml_info = by_name.get('geogebra.xml')
    if xml_info is None:
        raise ImportRefused('import_not_ggb', 'нет geogebra.xml')
    if xml_info.file_size > lim['xml_bytes']:
        raise ImportRefused('import_too_large', f'geogebra.xml больше {lim["xml_bytes"]} байт')
    try:
        xml = _bounded_read(zf, xml_info, lim['xml_bytes'])
        macro = by_name.get('geogebra_macro.xml')
        macro_xml = _bounded_read(zf, macro, lim['xml_bytes']) if macro is not None else None
        js = by_name.get('geogebra_javascript.js')
        javascript = _bounded_read(zf, js, lim['xml_bytes']) if js is not None else None
    except ImportRefused:
        raise
    except _ZIP_ERRORS as exc:
        raise ImportRefused('import_not_ggb', f'архив повреждён: {exc}') from None
    return GgbFile(name=name, size=len(raw), sha256=sha, xml=xml, macro_xml=macro_xml, javascript=javascript,
                   entries=[i.filename for i in infos])


_DTD = re.compile(rb'<!\s*(DOCTYPE|ENTITY)', re.IGNORECASE)


class _NoDoctype(ElementTree.TreeBuilder):
    """The tree builder of :func:`parse_xml`: a document type declaration
    stops the parser as soon as it starts — before its entities are declared
    or any external part is looked up, whatever the encoding (the byte check
    sees only an ASCII-compatible ``<!DOCTYPE``)."""

    def doctype(self, name, pubid, system):
        raise ImportRefused('ggb_invalid', 'XML с DOCTYPE или ENTITY')


def parse_xml(data: bytes, *, depth: int = 64):
    """The root of a GGB XML document; DTD and entities refuse it."""
    if _DTD.search(data):
        raise ImportRefused('ggb_invalid', 'XML с DOCTYPE или ENTITY')
    try:
        parser = ElementTree.XMLParser(target=_NoDoctype())
        parser.feed(data)
        root = parser.close()
    except ImportRefused:
        raise
    except (ElementTree.ParseError, ValueError, LookupError, UnicodeError) as exc:
        # ValueError: an encoding expat does not take ("multi-byte encodings are not supported")
        raise ImportRefused('ggb_invalid', f'XML не разбирается: {exc}') from None
    stack = [(root, 1)]
    while stack:
        node, d = stack.pop()
        if d > depth:
            raise ImportRefused('ggb_invalid', f'вложенность XML больше {depth}')
        stack.extend((child, d + 1) for child in node)
    return root


def _float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _bool(v):
    return None if v is None else v == 'true'


def scan(root) -> dict:
    """``{elements: [info], dropped: {kind: [labels]}, view, app, version,
    decimals, outputs: [labels], duplicates: [labels]}`` of the GGB XML root
    (``outputs`` — the labels commands and expressions define, with an
    ``<element>`` or not; ``duplicates`` — the labels defined twice: a second
    ``<element>``, expression or command output, the first one stands)."""
    constr = root.find('construction')
    if constr is None:
        raise ImportRefused('import_not_ggb', 'нет <construction>')
    elements = []
    producer: dict = {}         # label → (command name, input labels, kind)
    dropped: dict = {}
    seen_labels = set()
    duplicates: list = []

    def duplicate(label):
        if label not in duplicates:
            duplicates.append(label)

    def drop(kind, label=None):
        dropped.setdefault(kind, [])
        if label is not None and label not in dropped[kind]:
            dropped[kind].append(label)
        elif label is None:
            dropped[kind].append(None)

    for pos, node in enumerate(constr):
        tag = node.tag
        if tag == 'command':
            name = node.attrib.get('name', '')
            inp = node.find('input')
            out = node.find('output')
            inputs = list(inp.attrib.values()) if inp is not None else []
            for label in (out.attrib.values() if out is not None else ()):
                if label:
                    # a label defined twice (a damaged file): the first definition stands, as in the translator
                    if label in producer:
                        duplicate(label)
                    producer.setdefault(label, (name, inputs, 'command'))
        elif tag == 'expression':
            label = node.attrib.get('label')
            if label:
                if label in producer:
                    duplicate(label)
                producer.setdefault(label, ('Expression', [node.attrib.get('exp', '')], 'expression'))
        elif tag == 'cascell':
            drop('cas')
        elif tag == 'element':
            label = node.attrib.get('label')
            if label in seen_labels:
                duplicate(label)
            if not label or label in seen_labels:
                continue
            seen_labels.add(label)
            type_ = node.attrib.get('type', '')
            info = {'label': label, 'type': type_, 'order': pos}
            prod = producer.get(label)
            if prod is not None:
                info['command'] = prod[0]
                info['inputs'] = prod[1]
            show = node.find('show')
            if show is not None:
                info['show_object'] = _bool(show.attrib.get('object'))
                info['show_label'] = _bool(show.attrib.get('label'))
            lm = node.find('labelMode')
            if lm is not None and lm.attrib.get('val', '').lstrip('-').isdigit():
                info['label_mode'] = int(lm.attrib['val'])
            cap = node.find('caption')
            if cap is not None:
                info['caption'] = cap.attrib.get('val', '')
            col = node.find('objColor')
            if col is not None:
                try:
                    info['color'] = {'rgb': [int(col.attrib['r']), int(col.attrib['g']), int(col.attrib['b'])],
                                     'alpha': _float(col.attrib.get('alpha', '0')) or 0.0}
                except (KeyError, ValueError):
                    pass
            ls = node.find('lineStyle')
            if ls is not None:
                info['line_style'] = {'thickness': _float(ls.attrib.get('thickness')),
                                      'type': int(_float(ls.attrib.get('type')) or 0),
                                      'opacity': _float(ls.attrib.get('opacity'))}
            for key, tagname in (('point_size', 'pointSize'), ('point_style', 'pointStyle'),
                                 ('decoration', 'decoration'), ('angle_style', 'angleStyle')):
                sub = node.find(tagname)
                if sub is not None:
                    v = _float(sub.attrib.get('val', sub.attrib.get('type')))
                    if v is not None:
                        info[key] = int(v) if key != 'point_size' else v
            layer = node.find('layer')
            if layer is not None and _float(layer.attrib.get('val')) not in (None, 0):
                info['layer'] = int(_float(layer.attrib.get('val')))
                drop('layers', label)
            coords = node.find('coords')
            if coords is not None:
                c = {k: _float(v) for k, v in coords.attrib.items()}
                info['coords'] = c
                if 'w' in c:
                    info['is3d'] = True
            value = node.find('value')
            if value is not None:
                info['value'] = _float(value.attrib.get('val'))
            matrix = node.find('matrix')
            if matrix is not None:
                info['matrix'] = [_float(matrix.attrib.get(f'A{i}')) for i in range(6)]
            slider = node.find('slider')
            if slider is not None:
                info['slider'] = {k: _float(slider.attrib.get(k)) for k in ('min', 'max', 'step')
                                  if slider.attrib.get(k) is not None}
            sp = node.find('startPoint')
            if sp is not None:
                if 'exp' in sp.attrib:
                    info['start_ref'] = sp.attrib['exp']
                else:
                    info['start'] = [_float(sp.attrib.get('x')), _float(sp.attrib.get('y'))]
            screen = node.find('absoluteScreenLocation')
            if screen is not None:
                info['screen'] = [_float(screen.attrib.get('x')), _float(screen.attrib.get('y'))]
            latex = node.find('isLaTeX')
            info['latex'] = latex is not None and latex.attrib.get('val') == 'true'
            scripts = [s for s in node if s.tag in ('javascript', 'ggbscript')]
            if scripts:
                info['script'] = True
                drop('script', label)
            if node.find('condition') is not None:
                info['condition'] = True
                drop('conditional_visibility', label)
            if node.find('dynamicColor') is not None:
                drop('dynamic_color', label)
            anim = node.find('animation')
            if anim is not None and anim.attrib.get('playing') == 'true':
                drop('animation', label)
            bp = node.find('breakpoint')
            if bp is not None and bp.attrib.get('val') == 'true':
                info['breakpoint'] = True
            aux = node.find('auxiliary')
            if aux is not None and aux.attrib.get('val') == 'true':
                info['auxiliary'] = True
            if type_ == 'image':
                drop('image', label)
            if type_.lower() in TYPES_3D or info.get('is3d') or info.get('command') in COMMANDS_3D:
                drop('3d', label)
            elements.append(info)
    head = {k: root.attrib.get(k) for k in ('version', 'app', 'format')}
    if (head.get('app') or '').lower() == '3d':
        drop('3d')
    view = root.find('euclidianView')
    if view is None:
        view = root.find('euclideanView')
    kernel = root.find('kernel')
    decimals = None
    if kernel is not None and kernel.find('decimals') is not None:
        decimals = _float(kernel.find('decimals').attrib.get('val'))
    return {'elements': elements, 'dropped': dropped, 'view': view, 'app': head.get('app'),
            'version': head.get('version'), 'decimals': decimals, 'outputs': list(producer),
            'duplicates': duplicates}


def view_bounds(view):
    """``[xmin, ymin, xmax, ymax]`` of the saved graphics view (``None`` — no view)."""
    if view is None:
        return None
    size, cs = view.find('size'), view.find('coordSystem')
    if size is None or cs is None:
        return None
    w, h = _float(size.attrib.get('width')), _float(size.attrib.get('height'))
    x0, y0 = _float(cs.attrib.get('xZero')), _float(cs.attrib.get('yZero'))
    sx = _float(cs.attrib.get('scale'))
    sy = _float(cs.attrib.get('yscale')) or sx
    if None in (w, h, x0, y0, sx, sy) or sx <= 0 or sy <= 0 or w <= 0 or h <= 0:
        return None
    bounds = [-x0 / sx, -(h - y0) / sy, (w - x0) / sx, y0 / sy]
    if not all(math.isfinite(v) for v in bounds) or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        return None             # a degenerate or overflowing view: the document takes its default
    return bounds


def screen_to_world(view, x, y):
    """The drawing coordinates of the pixel ``(x, y)`` of the saved graphics
    view (``None`` — no view or no pixel)."""
    cs = view.find('coordSystem') if view is not None else None
    if cs is None or x is None or y is None:
        return None
    x0, y0 = _float(cs.attrib.get('xZero')), _float(cs.attrib.get('yZero'))
    sx = _float(cs.attrib.get('scale'))
    sy = _float(cs.attrib.get('yscale')) or sx
    if None in (x0, y0, sx, sy) or sx <= 0 or sy <= 0:
        return None
    out = [(x - x0) / sx, (y0 - y) / sy]
    return out if all(math.isfinite(v) for v in out) else None


# what GeoGebra prints for an object in a text, by its type (the classic ``format_object_value``)
TEXT_INSERTS = {'point': 'point', 'numeric': 'number', 'angle': 'angle', 'segment': 'length', 'polygon': 'area'}


def text_extras(info: dict, by_label: dict, point_of, view, decimals, classic_of=None) -> dict:
    """The anchor and the ``text.free`` template of a text (1.10.0a2,
    ``has("import_report.text_template")``), keys of its ``ggb_value``:

    - ``anchor`` for every text that has one: the start point; the saved
      position of the point it is attached to (``anchor_ref`` — that point);
      a text fixed on the screen — its pixel in drawing coordinates
      (``screen: true``);
    - ``template``, ``refs``, ``decimals`` of a text that is a ``+`` of
      literals and objects: the template of ``text.free`` (``{k}`` — item ``k``
      of ``refs``, literal braces doubled), ``refs`` — ``{ggb_name, as}``
      with ``as`` what GeoGebra prints: ``point``, ``number``, ``angle``
      (degrees), ``length`` (of a segment), ``area`` (of a polygon);
      ``shown`` — the text as the file shows it, from the saved values
      (the length of a side of a polygon from the classic object,
      ``classic_of(label)``)."""
    out = {}
    if info.get('start') is None:
        ref = (info.get('start_ref') or '').strip()
        if ref in by_label and by_label[ref].get('type') == 'point':
            out['anchor_ref'] = ref
            p = point_of(ref) if point_of is not None else None
            if p is not None:
                out['anchor'] = p
        elif info.get('screen') is not None:
            p = screen_to_world(view, *info['screen'])
            if p is not None:
                out['anchor'], out['screen'] = p, True
    if info.get('command') != 'Expression' or not info.get('inputs'):
        return out
    from ...parsers.ggb_parser import split_text_parts
    from ..expr.template import format_value, template_problems
    pieces, shown, refs, index = [], [], [], {}
    places = 2 if decimals is None or not 0 <= decimals <= 10 else int(decimals)
    for kind, piece in split_text_parts(info['inputs'][0]):
        if kind == 'str':
            pieces.append(piece.replace('{', '{{').replace('}', '}}'))
            if shown is not None:
                shown.append(piece)
            continue
        name = piece.strip()
        as_ = TEXT_INSERTS.get((by_label.get(name) or {}).get('type'))
        if as_ is None:
            return out
        if name not in index:
            index[name] = len(refs)
            refs.append({'ggb_name': name, 'as': as_})
        pieces.append('{%d}' % index[name])
        if shown is not None:
            value = _shown_value(by_label[name], as_, point_of, places, format_value, classic_of)
            shown = None if value is None else shown + [value]
    template = ''.join(pieces)
    if template_problems(template, len(refs)):
        return out
    out.update(template=template, refs=refs, decimals=places)
    if shown is not None:
        out['shown'] = ''.join(shown)
    return out


def _shown_value(info, as_, point_of, places, format_value, classic_of=None):
    """An insert as the file shows it (``None`` — no saved value)."""
    v = ggb_value(info, point_of)
    value = v.get('value') if v else None
    try:
        if as_ == 'length' and (v or {}).get('kind') != 'segment' and classic_of is not None:
            ends = getattr(classic_of(info['label']), 'endpoints', None)
            if ends is not None:
                v, value = {'kind': 'segment'}, [[float(c) for c in ends[0][:2]], [float(c) for c in ends[1][:2]]]
        if as_ == 'point' and value is not None:
            return f'({format_value(value[0], places)}, {format_value(value[1], places)})'
        if as_ == 'number' and value is not None:
            return format_value(value, places)
        if as_ == 'angle' and value is not None:
            return format_value(value * 180.0 / math.pi, places) + '°'
        if as_ == 'length' and v['kind'] == 'segment':
            (x1, y1), (x2, y2) = value
            return format_value(math.hypot(x2 - x1, y2 - y1), places)
        if as_ == 'area' and v['kind'] == 'polygon':
            area = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(value, value[1:] + value[:1])) / 2
            return format_value(abs(area), places)
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    return None


def ggb_value(info: dict, point_of=None):
    """The value of a scanned element in report form (``None`` — none)."""
    from .values import circle_from_matrix, line_coefficients
    type_ = info.get('type')
    c = info.get('coords')
    if type_ == 'point' and c is not None:
        x, y, z = c.get('x'), c.get('y'), c.get('z', 1.0)
        if None in (x, y, z):
            return {'kind': 'point', 'value': None}
        if z == 0:
            return {'kind': 'point', 'value': None}
        return {'kind': 'point', 'value': [x / z, y / z]}
    if type_ == 'segment' and point_of is not None and len(info.get('inputs') or ()) == 2:
        ends = [point_of(label) for label in info['inputs']]
        if all(p is not None for p in ends):
            return {'kind': 'segment', 'value': ends}
    if type_ in ('line', 'segment', 'ray') and c is not None:
        if None in (c.get('x'), c.get('y'), c.get('z')):
            return {'kind': 'line', 'value': None}
        return {'kind': 'line', 'value': line_coefficients(c['x'], c['y'], c['z'])}
    if type_ == 'numeric' and 'value' in info:
        return {'kind': 'number', 'value': info['value']}
    if type_ == 'angle' and 'value' in info:
        rng = {1: 'minor', 2: 'reflex'}.get(info.get('angle_style'))
        return {'kind': 'angle', 'value': info['value'], **({'range': rng} if rng else {})}
    if type_ in ('conic', 'conicpart') and info.get('matrix') and None not in info['matrix']:
        circle = circle_from_matrix(info['matrix'])
        if circle is not None:
            return {'kind': 'circle', 'value': circle}
        return {'kind': 'conic', 'value': list(info['matrix'])}
    if type_ == 'polygon' and point_of is not None and info.get('inputs'):
        pts = [point_of(label) for label in info['inputs']]
        if pts and all(p is not None for p in pts):
            return {'kind': 'polygon', 'value': pts}
    if type_ == 'text':
        return {'kind': 'text', 'text': info.get('text', ''), 'anchor': info.get('start')}
    return None
