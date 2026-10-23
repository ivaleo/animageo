"""Portable native text delimiter examples for library and client renderers."""
import json
from pathlib import Path

import pytest

from animageo import native
from animageo.geo.lib_elements import resolve_text_string, text_to_display_latex
from animageo.native.kernel.bridge import from_classic, to_classic
from tests.native.test_native_l2a5_text import text_doc


CONTRACT = json.loads(
    (Path(__file__).parent / 'fixtures' / 'text_free_delimiters.json').read_text(encoding='utf-8')
)


@pytest.mark.parametrize('case', CONTRACT['cases'], ids=lambda case: case['id'])
def test_native_delimiter_contract(case):
    """Keep literal delimiters through templates, JSON, kernel and display.

    The static fixture supplies independent expected scopes and LaTeX. A
    client can consume the same plain/math segments without importing Python.
    """
    raw = case['raw']
    segments = case['segments']
    assert raw == ''.join(
        part['text'] if part['kind'] == 'plain' else '$' + part['text'] + '$'
        for part in segments
    )
    template = raw.replace('{', '{{').replace('}', '}}')
    doc = text_doc(template).doc
    assert native.validate(doc) == []
    loaded = native.load(native.canonical_json(doc))
    value = native.evaluate(loaded).elements['t']['value']
    assert value['text'] == raw
    text = to_classic('text', value)
    assert resolve_text_string(None, text, 2) == raw
    assert from_classic('text', text) == value
    assert text_to_display_latex(None, text, 2) == case['display_latex']
