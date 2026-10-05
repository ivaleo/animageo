"""Fuzzing of ``native.from_ggb`` (plan L5 §7, stage 3).

A ``.ggb`` is untrusted input. Whatever it is — a broken or nested archive, a
zip bomb, a DTD, huge numbers, long labels, markup in captions, cycles in the
construction — the import ends in a consistent report (the schema, the
rules of :func:`report_problems`, a valid document) or in
:class:`ImportRefused` with a known code: never another exception, never a
hang (every case runs under a deadline).

There is no hypothesis here: the random cases come from
``random.Random(seed)``, a failure names its seed and is reproduced by it.
The deliberate cases run with the quick suite; the random series are also
``slow`` (``-m "slow or fuzz"`` runs them): 10³ cases per run, from
``ANIMAGEO_FUZZ_SEED`` (default 0; CI passes its run number).
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import random
import signal
import time
import uuid
import zipfile
from xml.etree import ElementTree

import pytest

from animageo.native.convert import LIMITS, ImportRefused, from_ggb
from tests.native.conftest import REPO_ROOT
from tests.native.ggb_synth import command, element, expression, ggb_bytes, ggb_xml, line_style, point, triangle
from tests.native.test_native_l5_ggb import CIRCLE_R3, NS, _by_name, _check

pytestmark = pytest.mark.fuzz

REFUSALS = {'import_too_large', 'import_not_ggb', 'import_too_many_objects', 'ggb_invalid'}
CASE_SECONDS = 20          # one import; longer is a hang


class Hang(BaseException):
    """Not an ``Exception``: the classic parser catches those and goes on."""


@contextlib.contextmanager
def deadline(seconds: float):
    """:class:`Hang` when the block runs longer than ``seconds`` (SIGALRM)."""
    def expired(signum, frame):
        raise Hang(f'the import ran longer than {seconds} s')
    old = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def outcome(data, what: str = '', **kw):
    """``('report', doc, rep)`` or ``('refused', code, detail)``; anything else fails."""
    try:
        with deadline(CASE_SECONDS):
            doc, rep = from_ggb(data, id_namespace=NS, name='fuzz.ggb', **kw)
    except ImportRefused as exc:
        assert exc.code in REFUSALS, (what, exc.code)
        assert len(exc.detail) <= 500
        return 'refused', exc.code, exc.detail
    except (Exception, Hang) as exc:  # noqa: BLE001 — the point of the test
        raise AssertionError(f'{what}: {type(exc).__name__}: {exc}') from exc
    try:
        _check(doc, rep)
    except AssertionError as exc:
        raise AssertionError(f'{what}: an inconsistent report: {exc}') from exc
    return 'report', doc, rep


def refused(data, code=None, what=''):
    result = outcome(data, what)
    assert result[0] == 'refused', (what, result[0])
    if code is not None:
        assert result[1] == code, (what, result[1], result[2])
    return result


def imported(data, what=''):
    result = outcome(data, what)
    assert result[0] == 'report', (what, result[1:])
    return result[1], result[2]


def _zip(entries: dict, method=zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', method) as zf:
        for name, data in entries.items():
            zf.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), data, compress_type=method)
    return buf.getvalue()


def _set_u16(data: bytearray, offset: int, value: int) -> None:
    data[offset:offset + 2] = value.to_bytes(2, 'little')


def _headers(data: bytes, signature: bytes):
    pos = data.find(signature)
    while pos >= 0:
        yield pos
        pos = data.find(signature, pos + 4)


def rich_body() -> str:
    """A construction with most kinds of objects the import meets."""
    return (triangle()
            + command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.0, 0.0)
            + command('Circle', ['C', 'M'], ['k']) + element('conic', 'k', extra=CIRCLE_R3)
            + command('Line', ['A', 'C'], ['g']) + element('line', 'g', extra='<coords x="-3" y="1" z="0"/>')
            + command('Intersect', ['g', 'k'], ['E', 'F']) + point('E', 0.5, 1.5) + point('F', 1.5, 4.5)
            + command('Angle', ['B', 'A', 'C'], ['α']) + element('angle', 'α', extra='<value val="1.249"/>')
            + element('numeric', 'n', extra='<value val="2"/><slider min="0" max="5" width="200" x="10" y="10"'
                                            ' fixed="true" horizontal="true" showAlgebra="true"/>')
            + command('Circle', ['A', 'n'], ['c2']) + element('conic', 'c2', extra='<matrix A0="1" A1="1" A2="-4"'
                                                                                   ' A3="0" A4="0" A5="0"/>')
            + expression('d', 'Distance(A, B) + 2 n') + element('numeric', 'd', extra='<value val="8"/>')
            + command('Ellipse', ['A', 'B', 'C'], ['e'])
            + element('conic', 'e', extra='<matrix A0="1" A1="2" A2="-9" A3="0" A4="0" A5="0"/>')
            + command('Point', ['e'], ['P']) + point('P', 3.0, 0.0)
            + expression('f', 'x^2') + element('function', 'f')
            + expression('text1', '"AB = " + Distance(A, B)') + element(
                'text', 'text1', extra='<startPoint x="1" y="1"/><isLaTeX val="false"/>')
            + element('button', 'b1', extra='<javascript val="alert(1)"/>')
            + point('Q', 1.0, 1.0, extra='<caption val="&lt;b&gt;Q&lt;/b&gt;"/><breakpoint val="true"/>'))


# ── broken archives ─────────────────────────────────────────────────────

def test_a_valid_base_imports():
    doc, rep = imported(ggb_bytes(rich_body()), 'base')
    e = _by_name(rep)
    assert e['M']['category'] == 'editable' and e['e']['category'] == 'unsupported'
    assert e['P']['category'] == 'closure'


@pytest.mark.parametrize('case', ['empty', 'magic_only', 'half', 'no_central_directory', 'no_local_header',
                                  'garbage_tail', 'garbage_head'])
def test_truncated_and_padded_archives(case):
    data = ggb_bytes(triangle())
    cd = data.find(b'PK\x01\x02')
    variants = {
        'empty': b'',
        'magic_only': b'PK\x03\x04',
        'half': data[:len(data) // 2],
        'no_central_directory': data[:cd],
        'no_local_header': data[30:],
        'garbage_tail': data + b'\0' * 1000,
        'garbage_head': b'#!/bin/sh\n' * 50 + data,
    }
    outcome(variants[case], case)


@pytest.mark.parametrize('case', ['method_99', 'method_bzip2', 'method_lzma', 'encrypted', 'crc', 'deflate',
                                  'stored_size', 'name_length'])
def test_damaged_entries_are_refused(case):
    """The entry of ``geogebra.xml`` itself is damaged: refused as ``import_not_ggb`` (or too large)."""
    data = bytearray(ggb_bytes(triangle()))
    local = next(_headers(bytes(data), b'PK\x03\x04'))
    central = next(_headers(bytes(data), b'PK\x01\x02'))
    if case.startswith('method'):
        method = {'method_99': 99, 'method_bzip2': 12, 'method_lzma': 14}[case]
        _set_u16(data, local + 8, method)
        _set_u16(data, central + 10, method)
    elif case == 'encrypted':
        _set_u16(data, local + 6, 1)
        _set_u16(data, central + 8, 1)
    elif case == 'crc':
        data[central + 16] ^= 0xFF
        data[local + 14] ^= 0xFF
    elif case == 'deflate':
        start = local + 30 + int.from_bytes(data[local + 26:local + 28], 'little')
        for i in range(start + 5, start + 60, 7):
            data[i] ^= 0x5A
    elif case == 'stored_size':
        data[central + 20:central + 24] = (3).to_bytes(4, 'little')
    elif case == 'name_length':
        _set_u16(data, local + 26, 200)
    result = refused(bytes(data), what=case)
    assert result[1] in ('import_not_ggb', 'import_too_large')


# ── nested archives ─────────────────────────────────────────────────────

def test_nested_archives_are_not_opened():
    inner = ggb_bytes(triangle())
    # a .ggb inside a .ggb: only the outer geogebra.xml is read
    doc, rep = imported(ggb_bytes(point('Z', 0.0, 0.0), extra={'inner.ggb': inner}), 'inner ggb')
    assert [e['ggb_name'] for e in rep['elements']] == ['Z']
    # the inner archive is the only construction: not a .ggb
    refused(_zip({'inner.ggb': inner}), 'import_not_ggb', 'only inner')
    refused(_zip({'sub/geogebra.xml': ggb_xml(triangle())}), 'import_not_ggb', 'subfolder')
    # geogebra.xml that is itself an archive
    refused(_zip({'geogebra.xml': inner}), 'ggb_invalid', 'xml is a zip')
    # a bomb inside an inner archive is never inflated: its outer entry is small
    bomb = _zip({'geogebra.xml': b'\0' * (LIMITS['unpacked_bytes'] * 2)})
    assert len(bomb) < 200_000
    start = time.perf_counter()
    imported(ggb_bytes(triangle(), extra={'bomb.zip': _zip({'b.zip': bomb})}), 'nested bomb')
    assert time.perf_counter() - start < 5


# ── zip bombs ───────────────────────────────────────────────────────────

def test_a_bomb_with_true_sizes_is_refused_before_inflating():
    start = time.perf_counter()
    bomb = _zip({'geogebra.xml': ggb_xml(triangle()), 'a.bin': b'\0' * (LIMITS['unpacked_bytes'] + 1)})
    refused(bomb, 'import_too_large', 'true sizes')
    # an XML larger than its limit (it compresses to almost nothing)
    padded = ggb_xml(triangle()).replace(b'<construction', b' ' * (LIMITS['xml_bytes'] + 1) + b'<construction')
    refused(_zip({'geogebra.xml': padded}), 'import_too_large', 'xml size')
    assert time.perf_counter() - start < 10


def test_a_bomb_with_lying_sizes_stops_at_the_limit():
    """The central directory claims a small XML; reading stops one byte past the limit."""
    huge = ggb_xml(triangle()).replace(b'<construction', b' ' * (LIMITS['xml_bytes'] * 4) + b'<construction')
    data = bytearray(_zip({'geogebra.xml': huge}))
    assert len(data) < 200_000
    for pos in _headers(bytes(data), b'PK\x01\x02'):
        data[pos + 24:pos + 28] = (1000).to_bytes(4, 'little')
    for pos in _headers(bytes(data), b'PK\x03\x04'):
        data[pos + 22:pos + 26] = (1000).to_bytes(4, 'little')
    start = time.perf_counter()
    result = refused(bytes(data), what='lying sizes')
    assert result[1] in ('import_too_large', 'import_not_ggb')
    assert time.perf_counter() - start < 10


def test_overlapping_entries_count_their_declared_sizes():
    """Many central-directory entries pointing to one compressed blob (the
    "overlapping files" bomb): their declared sizes add up."""
    blob = _zip({'geogebra.xml': ggb_xml(triangle()), 'z.bin': b'\0' * 5_000_000})
    data = bytearray(blob)
    cd = data.find(b'PK\x01\x02')
    second = data.find(b'PK\x01\x02', cd + 4)
    eocd = data.find(b'PK\x05\x06')
    record = bytes(data[second:eocd])
    copies = 12
    body = bytes(data[:eocd]) + record * (copies - 1)
    end = bytearray(data[eocd:])
    total = 1 + copies
    _set_u16(end, 8, total)
    _set_u16(end, 10, total)
    end[12:16] = (len(body) - cd).to_bytes(4, 'little')
    result = outcome(body + bytes(end), 'overlapping')
    assert result[0] == 'refused' and result[1] in ('import_too_large', 'import_not_ggb')


def test_too_many_entries_and_objects():
    refused(ggb_bytes(point('A', 0.0, 0.0), extra={f'f{i}': b'' for i in range(LIMITS['entries'])}),
            'import_too_large', 'entries')
    body = ''.join(point(f'P{i}', float(i), 0.0) for i in range(LIMITS['objects'] + 1))
    refused(ggb_bytes(body), 'import_too_many_objects', 'objects')


# ── DTD, entities and other XML tricks ─────────────────────────────────

ENTITY_BODY = ('<!DOCTYPE g [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
               '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'
               '<geogebra><construction><element type="point" label="&c;"/></construction></geogebra>')


@pytest.mark.parametrize('case', ['laughs', 'lower', 'spaced', 'system', 'public', 'parameter', 'utf16', 'utf16be',
                                  'utf16_no_bom', 'utf32', 'macro', 'external_in_attr'])
def test_dtd_and_entities_are_refused(case):
    decl = '<?xml version="1.0" encoding="{}"?>'
    xml = {
        'laughs': (decl.format('utf-8') + ENTITY_BODY).encode(),
        'lower': (decl.format('utf-8') + ENTITY_BODY.replace('DOCTYPE', 'doctype')).encode(),
        'spaced': (decl.format('utf-8') + ENTITY_BODY.replace('<!DOCTYPE', '<!  DOCTYPE')).encode(),
        'system': b'<?xml version="1.0"?><!DOCTYPE g SYSTEM "file:///etc/passwd"><geogebra/>',
        'public': b'<?xml version="1.0"?><!DOCTYPE g PUBLIC "-//x//y" "http://127.0.0.1:9/x.dtd"><geogebra/>',
        'parameter': (b'<?xml version="1.0"?><!DOCTYPE g [<!ENTITY % p SYSTEM "http://127.0.0.1:9/p">%p;]>'
                      b'<geogebra/>'),
        'utf16': (decl.format('UTF-16') + ENTITY_BODY).encode('utf-16'),
        'utf16be': (decl.format('UTF-16BE') + ENTITY_BODY).encode('utf-16-be'),
        'utf16_no_bom': (decl.format('UTF-16LE') + ENTITY_BODY).encode('utf-16-le'),
        'utf32': (decl.format('UTF-32') + ENTITY_BODY).encode('utf-32'),
        'macro': None,
        'external_in_attr': (b'<?xml version="1.0"?><!DOCTYPE g [<!ENTITY x SYSTEM "file:///etc/hostname">]>'
                             b'<geogebra><construction><element type="point" label="&x;"/></construction>'
                             b'</geogebra>'),
    }[case]
    if case == 'macro':
        data = ggb_bytes(triangle(), macro=(decl.format('UTF-16') + '<!DOCTYPE m [<!ENTITY q "q">]>'
                                            '<geogebra><macro cmdName="&q;"/></geogebra>').encode('utf-16'))
    else:
        data = ggb_bytes(xml=xml)
    result = refused(data, what=case)
    assert result[1] in ('ggb_invalid', 'import_not_ggb')


@pytest.mark.parametrize('case', ['xinclude', 'pi', 'comments', 'cdata', 'namespaces', 'bom', 'latin1'])
def test_other_xml_constructs_are_harmless(case, tmp_path):
    secret = tmp_path / 'secret.txt'
    secret.write_text('SECRET', encoding='utf-8')
    body = triangle()
    xml = {
        'xinclude': ggb_xml(body + f'<xi:include xmlns:xi="http://www.w3.org/2001/XInclude" href="{secret}" '
                                   'parse="text"/>'),
        'pi': ggb_xml(body, prolog='<?xml-stylesheet href="http://127.0.0.1:9/s.xsl"?>'),
        'comments': ggb_xml(body.replace('<element', '<!-- c --><element') + '<!-- ' + '-' * 0 + 'x' * 10_000 + ' -->'),
        'cdata': ggb_xml(body + '<element type="text" label="T"><![CDATA[<geogebra/>]]></element>'),
        'namespaces': ggb_xml(body.replace('<element type="point"', '<element xmlns="urn:x" type="point"', 1)),
        'bom': b'\xef\xbb\xbf' + ggb_xml(body),
        'latin1': ggb_xml(body).replace(b'encoding="utf-8"', b'encoding="iso-8859-1"'),
    }[case]
    result = outcome(ggb_bytes(xml=xml), case)
    if result[0] == 'report':
        import json
        assert 'SECRET' not in json.dumps(result[2], ensure_ascii=False)


# ── numbers ─────────────────────────────────────────────────────────────

WEIRD_NUMBERS = ['1e308', '-1e308', '1e309', '-1e309', 'inf', '-Infinity', 'nan', 'NaN', '1e-320', '-0', '0',
                 '9' * 400, '0.' + '0' * 400 + '1', '1e999999999', '0x10', '1_000', '', ' 1 ', '1,5', '١', 'true']


NUMBER_IDS = [f'n{i}' for i in range(len(WEIRD_NUMBERS))]


@pytest.mark.parametrize('value', WEIRD_NUMBERS, ids=NUMBER_IDS)
@pytest.mark.parametrize('where', ['x', 'y', 'z'])
def test_huge_and_odd_coordinates(where, value):
    xy = {'x': '1', 'y': '2', 'z': '1', where: value}
    a = element('point', 'A', extra=f'<coords x="{xy["x"]}" y="{xy["y"]}" z="{xy["z"]}"/>')
    body = (a + point('B', 4.0, 0.0) + command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.5, 1.0)
            + command('Circle', ['A', 'B'], ['k']) + element('conic', 'k', extra=CIRCLE_R3)
            + command('Segment', ['A', 'B'], ['s']) + element('segment', 's', extra=line_style()))
    imported(ggb_bytes(body), f'{where}={value!r}')


@pytest.mark.parametrize('value', WEIRD_NUMBERS, ids=NUMBER_IDS)
def test_huge_and_odd_values(value):
    slider = f'<slider min="{value}" max="{value}" step="{value}" width="{value}"/>'
    body = (element('numeric', 'n', extra=f'<value val="{value}"/>{slider}')
            + element('angle', 'w', extra=f'<value val="{value}"/>')
            + point('A', 0.0, 0.0) + command('Circle', ['A', 'n'], ['k'])
            + element('conic', 'k', extra=f'<matrix A0="{value}" A1="1" A2="-4" A3="0" A4="0" A5="{value}"/>')
            + element('line', 'g', extra=f'<coords x="{value}" y="1" z="{value}"/>')
            + element('segment', 's', extra=line_style(thickness=0).replace('thickness="0"', f'thickness="{value}"'))
            + point('P', 1.0, 1.0, extra=f'<pointSize val="{value}"/><layer val="{value}"/>')
            .replace('<objColor r="21"', f'<objColor r="{value}"'))
    imported(ggb_bytes(body), repr(value))


def test_a_huge_view_is_harmless():
    xml = ggb_xml(triangle()).replace(b'scale="50"', b'scale="1e-308"').replace(b'xZero="400"', b'xZero="1e308"')
    imported(ggb_bytes(xml=xml), 'view')
    xml = ggb_xml(triangle()).replace(b'<size width="800" height="600"/>', b'<size width="-1" height="nan"/>')
    imported(ggb_bytes(xml=xml), 'view size')


# ── labels and captions ─────────────────────────────────────────────────

ODD_LABELS = ['A' * 200, 'Ж' * 200, 'A_{' + '1' * 190 + '}', '__class__', 'import', 'Circle', 'x', 'y', 'e',
              'pi', 'π', 'A B', "A'", 'A"', '\u202eB', 'A\u0301', '1A', '$A$', '\\frac', '{', 'A]', 'a=b', ' ',
              '\u200b', 'A\tB']


@pytest.mark.parametrize('label', ODD_LABELS, ids=[f'label{i}' for i in range(len(ODD_LABELS))])
def test_odd_labels(label):
    body = (point(label, 0.0, 0.0) + point('B', 4.0, 0.0) + command('Midpoint', [label, 'B'], ['M'])
            + point('M', 2.0, 0.0) + command('Segment', [label, 'B'], ['s'])
            + element('segment', 's', extra=line_style()))
    doc, rep = imported(ggb_bytes(body), label[:20])
    assert [e['ggb_name'] for e in rep['elements']] == [label, 'B', 'M', 's']


@pytest.mark.parametrize('label', ['A' * 201, 'Ж' * 100_000, 'A_{' + '1' * 3000 + '}'], ids=['201', '100k', 'index'])
def test_a_label_longer_than_the_limit_refuses_the_file(label):
    """A label is ≤ 200 characters (the report schema); a longer one is not GeoGebra's."""
    result = refused(ggb_bytes(point('B', 4.0, 0.0) + point(label, 0.0, 0.0)), 'ggb_invalid', label[:20])
    assert len(result[2]) < 200
    assert LIMITS['label_chars'] == 200


def test_many_long_labels():
    body = ''.join(point(f'P{i}_' + 'x' * 190, float(i % 50), float(i // 50)) for i in range(1500))
    start = time.perf_counter()
    doc, rep = imported(ggb_bytes(body), 'many long labels')
    assert rep['summary']['editable'] == 1500
    assert time.perf_counter() - start < 60


def test_long_attributes_of_the_file():
    xml = ggb_xml(triangle()).replace(b'app="classic"', b'app="' + b'z' * 5000 + b'"')
    xml = xml.replace(b'version="5.4.927.1"', b'version="' + b'9' * 5000 + b'"')
    doc, rep = imported(ggb_bytes(xml=xml), 'attributes')
    assert len(rep['source']['app']) == 40 and len(rep['source']['ggb_version']) == 40
    body = triangle(command('Z' * 5000, ['A', 'B'], ['M']) + point('M', 2.0, 0.0))
    body = body.replace('<element type="polygon"', '<element type="' + 'q' * 5000 + '"')
    doc, rep = imported(ggb_bytes(body), 'command')
    assert len(_by_name(rep)['M']['command']) == 80 and len(_by_name(rep)['t1']['ggb_type']) == 40


CAPTIONS = ['<b>Q</b>', '<script>alert(1)</script>', '&amp;lt;', '$\\frac{a}{b}$', '\\input{/etc/passwd}', '%v',
            '%n %x %y', '"}]);', 'Ж' * 10_000, '\u202e', '<svg onload=alert(1)>', '{{7*7}}', '${7*7}']


@pytest.mark.parametrize('caption', CAPTIONS, ids=[f'caption{i}' for i in range(len(CAPTIONS))])
def test_markup_in_captions_and_texts(caption):
    cap = f'<caption val={_quote(caption)}/>'
    body = (point('Q', 1.0, 1.0, extra=cap).replace('<labelMode val="0"/>', '<labelMode val="3"/>')
            + expression('T', '"' + caption.replace('"', '') + '"')
            + element('text', 'T', extra=f'<startPoint x="0" y="0"/><isLaTeX val="true"/>{cap}'))
    doc, rep = imported(ggb_bytes(body), caption[:20])
    q = _by_name(rep)['Q']
    assert q['category'] == 'editable'
    assert q['label']['caption'] == caption[:500]
    assert _by_name(rep)['T']['category'] in ('picture', 'unsupported')
    if doc is not None:
        app = doc['appearance'][q['native_ids'][0]]
        assert app['label']['text'] == caption       # data: escaping is the renderer's business


def _quote(text: str) -> str:
    from xml.sax.saxutils import quoteattr
    return quoteattr(text)


# ── cycles and broken references ────────────────────────────────────────

CYCLES = {
    'self': command('Midpoint', ['A', 'A'], ['A']) + point('A', 0.0, 0.0),
    'two': (command('Midpoint', ['B', 'C'], ['A']) + point('A', 0.0, 0.0)
            + command('Midpoint', ['A', 'C'], ['B']) + point('B', 1.0, 0.0) + point('C', 2.0, 0.0)),
    'three': (command('Midpoint', ['C', 'Z'], ['A']) + point('A', 0.0, 0.0) + command('Midpoint', ['A', 'Z'], ['B'])
              + point('B', 1.0, 0.0) + command('Midpoint', ['B', 'Z'], ['C']) + point('C', 2.0, 0.0)
              + point('Z', 5.0, 5.0)),
    'expressions': (expression('a', 'b + 1') + element('numeric', 'a', extra='<value val="1"/>')
                    + expression('b', 'a + 1') + element('numeric', 'b', extra='<value val="2"/>')),
    'output_is_input': (point('A', 0.0, 0.0) + point('B', 2.0, 0.0) + command('Segment', ['A', 'B'], ['A'])
                        + element('segment', 'A', extra=line_style())),
    'forward': (command('Midpoint', ['A', 'B'], ['M']) + point('M', 1.0, 0.0) + point('A', 0.0, 0.0)
                + point('B', 2.0, 0.0)),
    'dangling': (command('Midpoint', ['A', 'Nope'], ['M']) + point('M', 1.0, 0.0) + point('A', 0.0, 0.0)),
    'duplicate_labels': (point('A', 0.0, 0.0) + point('A', 5.0, 5.0) + point('B', 2.0, 0.0)
                         + command('Midpoint', ['A', 'B'], ['M']) + command('Midpoint', ['B', 'A'], ['M'])
                         + point('M', 1.0, 0.0)),
    'circle_of_circles': (point('O', 0.0, 0.0) + command('Circle', ['O', 'k2'], ['k1'])
                          + element('conic', 'k1', extra=CIRCLE_R3) + command('Circle', ['O', 'k1'], ['k2'])
                          + element('conic', 'k2', extra=CIRCLE_R3)),
    'intersect_itself': (point('A', 0.0, 0.0) + point('B', 2.0, 1.0) + command('Line', ['A', 'B'], ['g'])
                         + element('line', 'g', extra='<coords x="1" y="-2" z="0"/>')
                         + command('Intersect', ['g', 'g'], ['E']) + point('E', 0.0, 0.0)),
    'polygon_of_itself': (point('A', 0.0, 0.0) + point('B', 2.0, 0.0)
                          + command('Polygon', ['A', 'B', 't'], ['t', 'a', 'b'])
                          + element('polygon', 't') + element('segment', 'a') + element('segment', 'b')),
}


@pytest.mark.parametrize('case', sorted(CYCLES))
def test_cycles_and_broken_references(case):
    doc, rep = imported(ggb_bytes(CYCLES[case]), case)
    names = {e['ggb_name'] for e in rep['elements']}
    assert names, case


def test_a_long_chain_does_not_overflow_the_stack():
    body = point('P0', 0.0, 0.0) + point('Z', 1.0, 0.0)
    for i in range(1, 1200):
        body += command('Midpoint', [f'P{i - 1}', 'Z'], [f'P{i}']) + point(f'P{i}', 1.0 - 0.5 ** i, 0.0)
    doc, rep = imported(ggb_bytes(body), 'chain')
    assert rep['source']['objects'] == 1201


def test_a_long_cycle_does_not_overflow_the_stack():
    n = 1200
    body = point('Z', 1.0, 0.0)
    for i in range(n):
        body += command('Midpoint', [f'P{(i - 1) % n}', 'Z'], [f'P{i}']) + point(f'P{i}', 0.5, 0.0)
    imported(ggb_bytes(body), 'long cycle')


# ── random series (slow) ────────────────────────────────────────────────

REAL = ['docs/guide/assets/ggb/sample_triangle.ggb', 'examples/ai_style_generation_scene10/scene10.ggb',
        'tests/fixtures/label_anchor_types.ggb', 'tests/fixtures/text_dynamic.ggb']
TYPES = ['point', 'segment', 'line', 'ray', 'vector', 'conic', 'conicpart', 'polygon', 'numeric', 'angle', 'text',
         'list', 'function', 'button', 'image', 'point3d', 'locus', 'boolean', 'implicitpoly', '', 'Point', 'zzz']
COMMANDS = ['Midpoint', 'Circle', 'Line', 'Segment', 'Polygon', 'Intersect', 'Angle', 'Ellipse', 'Point',
            'Rotate', 'Mirror', 'Dilate', 'Translate', 'Tangent', 'Locus', 'Sequence', 'If', 'RandomBetween',
            'Execute', 'Distance', 'Area', 'Vector', 'Ray', 'PerpendicularLine', 'AngleBisector', 'Semicircle',
            'CircleArc', 'CircularSector', 'Incircle', 'Centroid', 'Prove', '', 'Zzz', '__import__']
VALUES = WEIRD_NUMBERS + ['A', 'B', 'C', 'M', 'k', 'g', 't1', 'n', 'α', 'e', 'P', 'x', '(1, 2)', '(A + B) / 2',
                          'Segment(A, B)', '1/0', '0/0', 'sqrt(-1)', '2^1024', '10^400', 'A'*2000, '<b>', '%v',
                          '"', "'", '\\', '{1,2}', 'x^2 + y^2 = 4', "().__class__", 'Midpoint(A, A)']


def _base(rng: random.Random) -> bytes:
    if rng.random() < 0.6:
        return ggb_xml(rich_body())
    with zipfile.ZipFile(REPO_ROOT / rng.choice(REAL)) as zf:
        return zf.read('geogebra.xml')


def _mutate_tree(root, rng: random.Random) -> None:
    constr = root.find('construction')
    if constr is None:
        return
    nodes = list(constr)
    if not nodes:
        return
    op = rng.randrange(12)
    node = rng.choice(nodes)
    labels = [n.attrib.get('label') for n in nodes if n.tag == 'element' and n.attrib.get('label')]
    if op == 0:                                        # drop a node
        constr.remove(node)
    elif op == 1:                                      # move a node
        constr.remove(node)
        constr.insert(rng.randrange(len(constr) + 1), node)
    elif op == 2:                                      # duplicate a node
        constr.insert(rng.randrange(len(constr) + 1), ElementTree.fromstring(ElementTree.tostring(node)))
    elif op == 3 and labels:                           # rename a label in one place
        targets = [x for x in node.iter() if x.attrib]
        if targets:
            t = rng.choice(targets)
            key = rng.choice(list(t.attrib))
            t.attrib[key] = rng.choice(labels + ['Nope', ''])
    elif op == 4:                                      # an odd value of any attribute
        targets = [x for x in node.iter() if x.attrib]
        if targets:
            t = rng.choice(targets)
            t.attrib[rng.choice(list(t.attrib))] = rng.choice(VALUES)
    elif op == 5:                                      # another element type
        if node.tag == 'element':
            node.attrib['type'] = rng.choice(TYPES)
    elif op == 6:                                      # another command
        if node.tag == 'command':
            node.attrib['name'] = rng.choice(COMMANDS)
    elif op == 7 and labels:                           # a command of random inputs
        inputs = {f'a{i}': rng.choice(labels + VALUES) for i in range(rng.randrange(0, 5))}
        out = {f'a{i}': rng.choice(labels + ['N1', 'N2']) for i in range(rng.randrange(0, 3))}
        cmd = ElementTree.SubElement(constr, 'command', {'name': rng.choice(COMMANDS)})
        ElementTree.SubElement(cmd, 'input', inputs)
        ElementTree.SubElement(cmd, 'output', out)
        constr.remove(cmd)
        constr.insert(rng.randrange(len(constr) + 1), cmd)
    elif op == 8:                                      # an expression
        label = rng.choice(labels + ['N1']) if labels else 'N1'
        exp = ElementTree.Element('expression', {'label': label, 'exp': rng.choice(VALUES)})
        constr.insert(rng.randrange(len(constr) + 1), exp)
    elif op == 9:                                      # an odd child of an element
        if node.tag == 'element':
            tag = rng.choice(['coords', 'value', 'matrix', 'slider', 'startPoint', 'caption', 'javascript',
                              'ggbscript', 'condition', 'layer', 'lineStyle', 'pointSize', 'show', 'objColor',
                              'labelMode', 'breakpoint', 'animation', 'dynamicColor', 'isLaTeX', 'angleStyle'])
            attrs = {k: rng.choice(VALUES) for k in rng.sample(['x', 'y', 'z', 'w', 'val', 'exp', 'A0', 'A1', 'A2',
                                                                'r', 'g', 'b', 'object', 'label', 'min', 'max',
                                                                'thickness', 'type', 'playing'], 3)}
            ElementTree.SubElement(node, tag, attrs)
    elif op == 10:                                     # strip the children of a node
        for child in list(node):
            if rng.random() < 0.5:
                node.remove(child)
    elif op == 11 and labels:                          # a cycle: an output becomes an input of its producer
        if node.tag == 'command' and node.find('input') is not None and node.find('output') is not None:
            outs = list(node.find('output').attrib.values())
            if outs:
                node.find('input').attrib['a0'] = outs[0]


def _mutated_xml(seed: int) -> bytes:
    rng = random.Random(seed)
    root = ElementTree.fromstring(_base(rng))
    for _ in range(rng.randrange(1, 7)):
        _mutate_tree(root, rng)
    return ElementTree.tostring(root, encoding='utf-8')


def _mutated_bytes(seed: int) -> bytes:
    rng = random.Random(seed)
    data = bytearray(ggb_bytes(xml=_base(rng)))
    for _ in range(rng.randrange(1, 4)):
        op = rng.randrange(5)
        pos = rng.randrange(len(data))
        if op == 0:
            data[pos] ^= 1 << rng.randrange(8)
        elif op == 1:
            del data[pos:]
        elif op == 2:
            data[pos:pos] = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 64)))
        elif op == 3:
            n = rng.randrange(1, 32)
            data[pos:pos + n] = b'\0' * n
        else:
            data[pos:pos + 4] = rng.choice([b'\xff\xff\xff\xff', b'\0\0\0\x80', b'PK\x03\x04', b'PK\x01\x02'])
        if not data:
            break
    return bytes(data)


def _mutated_text(seed: int) -> bytes:
    """Byte edits of the XML itself (it may stop being XML), packed in a sound archive."""
    rng = random.Random(seed)
    xml = bytearray(_base(rng))
    for _ in range(rng.randrange(1, 6)):
        pos = rng.randrange(len(xml))
        op = rng.randrange(4)
        if op == 0:
            del xml[pos:pos + rng.randrange(1, 40)]
        elif op == 1:
            xml[pos:pos] = rng.choice([b'<', b'>', b'"', b'&', b'&amp;', b'<x>', b'</construction>', b'\0',
                                       b'\xff', b'\xc3', b'<!--', b']]>', b'<element type="point" label="A">',
                                       b'<command name="Midpoint"><input a0="A" a1="A"/><output a0="A"/></command>'])
        elif op == 2:
            a, b = sorted(rng.randrange(len(xml)) for _ in range(2))
            xml[pos:pos] = xml[a:b][:5000]
        else:
            xml[pos] = rng.randrange(32, 127)
    return ggb_bytes(xml=bytes(xml))


# 1.11.0rc1: 10³ random cases per run (three series of ``FUZZ_CASES / 3``
# seeds). CI starts the seeds at its run number (``ANIMAGEO_FUZZ_SEED``), so
# every run tries new cases; a failure names its seed, the variable
# reproduces it.
FUZZ_CASES = int(os.environ.get('ANIMAGEO_FUZZ_CASES', '1000'))
FUZZ_SEED = int(os.environ.get('ANIMAGEO_FUZZ_SEED', '0'))
SEEDS = range(FUZZ_SEED, FUZZ_SEED + math.ceil(FUZZ_CASES / 3))


def test_a_run_has_a_thousand_random_cases():
    assert 3 * len(SEEDS) >= FUZZ_CASES
    assert FUZZ_CASES >= 1000 or 'ANIMAGEO_FUZZ_CASES' in os.environ


@pytest.mark.slow
@pytest.mark.parametrize('seed', SEEDS)
def test_random_trees(seed):
    outcome(ggb_bytes(xml=_mutated_xml(seed)), f'tree seed={seed}')


@pytest.mark.slow
@pytest.mark.parametrize('seed', SEEDS)
def test_random_bytes(seed):
    outcome(_mutated_bytes(seed), f'bytes seed={seed}')


@pytest.mark.slow
@pytest.mark.parametrize('seed', SEEDS)
def test_random_xml_text(seed):
    outcome(_mutated_text(seed), f'text seed={seed}')


def test_the_series_are_reproducible():
    assert _mutated_xml(7) == _mutated_xml(7) and _mutated_bytes(7) == _mutated_bytes(7)
    assert _mutated_text(7) == _mutated_text(7)
    assert len({_mutated_xml(s) for s in range(10)}) == 10


def test_a_quick_sample_of_every_series():
    """A few seeds of each series with the quick suite."""
    for seed in range(5):
        outcome(ggb_bytes(xml=_mutated_xml(seed)), f'tree seed={seed}')
        outcome(_mutated_bytes(seed), f'bytes seed={seed}')
        outcome(_mutated_text(seed), f'text seed={seed}')


def test_the_deadline_catches_a_hang():
    with pytest.raises(Hang):
        with deadline(0.2):
            while True:
                try:
                    pass
                except Exception:      # noqa: BLE001 — as the classic parser does
                    pass


@pytest.mark.parametrize('n', ['1e9', '9' * 400, '1e308', 'inf', '10001', '101'])
def test_a_regular_polygon_of_too_many_vertices(n):
    """``Polygon(A, B, n)`` of a huge ``n`` built n points in the classic parser
    (the memory of the process); now it is undefined past 10000 vertices and
    not translated past 100 (``polygon.regular`` takes 3..100)."""
    def body(count):
        return (point('A', 0.0, 0.0) + point('B', 1.0, 0.0)
                + command('Polygon', ['A', 'B', count], ['poly1', 'f', 'g', 'h', 'i', 'C', 'D'])
                + element('polygon', 'poly1') + ''.join(element('segment', s) for s in 'fghi')
                + point('C', 1.0, 1.0) + point('D', 0.0, 1.0))
    start = time.perf_counter()
    doc, rep = imported(ggb_bytes(body(n)), n)
    assert time.perf_counter() - start < 5
    assert _by_name(rep)['poly1']['category'] not in ('editable', 'differs')
    doc, rep = imported(ggb_bytes(body('4')), '4')
    assert _by_name(rep)['poly1']['category'] in ('editable', 'differs')
    assert _by_name(rep)['D']['category'] == 'editable'
