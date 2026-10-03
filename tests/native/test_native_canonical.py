"""Canonical JSON: ECMAScript number formatting, sorted keys, JSON.stringify strings."""
import json
import math
import random
import shutil
import struct
import subprocess

import pytest

from animageo.native.canonical import canonical_bytes, canonical_json, format_number, sha256_of
from tests.native.conftest import NATIVE_DIR

CASES_PATH = NATIVE_DIR / 'parity' / 'v1' / 'canonical.json'


def _cases():
    with open(CASES_PATH, encoding='utf-8') as fh:
        return json.load(fh)


def test_shared_table_is_a_list_of_value_canonical_pairs():
    cases = _cases()
    assert isinstance(cases, list) and len(cases) >= 50
    for case in cases:
        assert set(case) == {'value', 'canonical'}
        assert isinstance(case['canonical'], str)


@pytest.mark.parametrize('case', _cases(), ids=lambda c: c['canonical'][:40])
def test_shared_table(case):
    assert canonical_json(case['value']) == case['canonical']


@pytest.mark.parametrize('value, text', [
    (0, '0'), (-0.0, '0'), (1.0, '1'), (100.0, '100'), (0.1, '0.1'), (-1.5, '-1.5'),
    (1e-7, '1e-7'), (1.5e-6, '0.0000015'), (1e-6, '0.000001'), (5e-7, '5e-7'),
    (123456789012345680000, '123456789012345680000'), (1e20, '100000000000000000000'),
    (1e21, '1e+21'), (1.5e21, '1.5e+21'), (10 ** 21, '1e+21'), (2 ** 53, '9007199254740992'),
    (2 ** 53 + 1, '9007199254740992'), (2 ** 53 + 2, '9007199254740994'), (5e-324, '5e-324'),
    (123456789.125, '123456789.125'), (1.7976931348623157e308, '1.7976931348623157e+308'),
    (0.30000000000000004, '0.30000000000000004'), (123e-20, '1.23e-18'),
])
def test_numbers(value, text):
    assert format_number(value) == text


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf, [1.0, math.nan], {'a': math.inf}])
def test_non_finite_numbers_are_refused(value):
    with pytest.raises(ValueError):
        canonical_json(value)


def test_huge_integer_is_refused():
    with pytest.raises(ValueError):
        canonical_json(10 ** 400)


def test_literals_and_containers():
    assert canonical_json([True, False, None, (1, 2)]) == '[true,false,null,[1,2]]'
    assert canonical_json({'b': 1, 'a': {'d': [], 'c': {}}}) == '{"a":{"c":{},"d":[]},"b":1}'


def test_keys_sort_by_utf16_code_units():
    # U+1F600 is D83D DE00 in UTF-16, before U+FF01; code point order says the opposite.
    assert canonical_json({'！': 1, '😀': 2, 'Б': 3, 'a': 4, 'A': 5}) == '{"A":5,"a":4,"Б":3,"😀":2,"！":1}'


def test_strings_escape_only_what_json_stringify_escapes():
    assert canonical_json('Ёж "q" \\ /   \x7f') == '"Ёж \\"q\\" \\\\ /   \x7f"'
    assert canonical_json('\x00\x01\b\t\n\x0b\f\r\x1f') == '"\\u0000\\u0001\\b\\t\\n\\u000b\\f\\r\\u001f"'
    assert canonical_json('\ud800') == '"\\ud800"'


def test_bad_types_are_refused():
    with pytest.raises(TypeError):
        canonical_json({1: 'a'})
    with pytest.raises(TypeError):
        canonical_json({'a': object()})


def test_bytes_and_hash():
    assert canonical_bytes({'я': 1}) == '{"я":1}'.encode('utf-8')
    assert sha256_of({}) == 'sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'


def _random_doubles(count, seed=1234):
    rng = random.Random(seed)
    out = []
    while len(out) < count:
        x = struct.unpack('<d', struct.pack('<Q', rng.getrandbits(64)))[0]
        if math.isfinite(x):
            out.append(x)
    out += [rng.uniform(-1e3, 1e3) for _ in range(count)]
    out += [rng.uniform(-1, 1) * 10 ** rng.randint(-30, 30) for _ in range(count)]
    return out


@pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')
def test_matches_javascript():
    """JSON.stringify (keys sorted) agrees on the shared table and on random doubles."""
    doubles = _random_doubles(2000)
    script = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
function canon(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']';
  return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}';
}
process.stdout.write(JSON.stringify({
  table: input.table.map(c => canon(c.value)),
  numbers: input.numbers.map(x => String(x)),
}));
"""
    payload = json.dumps({'table': _cases(), 'numbers': doubles}, ensure_ascii=True)
    proc = subprocess.run(['node', '-e', script], input=payload, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out['table'] == [c['canonical'] for c in _cases()]
    mismatches = [(x, js) for x, js in zip(doubles, out['numbers']) if format_number(x) != js]
    assert mismatches == []
