"""The deprecation policy (1.11.0rc1, L6 item 6): ``animageo/_deprecation.py``
and the list ``docs/native/deprecations.md``."""
import re
import warnings
from pathlib import Path

import pytest

from animageo import _deprecation
from animageo._deprecation import DEPRECATIONS, Deprecation, deprecated, register, warn

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / 'docs' / 'native' / 'deprecations.md'


@pytest.fixture
def clean_registry(monkeypatch):
    monkeypatch.setattr(_deprecation, 'DEPRECATIONS', dict(DEPRECATIONS))
    return _deprecation.DEPRECATIONS


class TestDecorator:
    def test_function_warns_and_works(self, clean_registry):
        @deprecated(since='1.11.0', alternative='native.load')
        def old(x, y=1):
            """Old."""
            return x + y

        with pytest.warns(DeprecationWarning, match=r'old is deprecated\. Deprecated since 1\.11\.0; '
                                                    r'removed in 2\.0\. Use native\.load instead\.'):
            assert old(1, y=2) == 3
        assert old.__doc__ == 'Old.' and old.__name__ == 'old'
        assert old.__deprecated__.startswith('tests.test_deprecation.')
        assert any(name.endswith('.old') for name in clean_registry)

    def test_the_warning_points_at_the_caller(self, clean_registry):
        @deprecated(since='1.11.0')
        def old():
            return 1

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            old()
        assert caught[0].filename == __file__

    def test_class(self, clean_registry):
        @deprecated(since='1.11.0', alternative='New')
        class Old:
            def __init__(self, a):
                self.a = a

        with pytest.warns(DeprecationWarning, match='Use New instead'):
            assert Old(5).a == 5
        assert 'Old' in Old.__deprecated__

    def test_removal_not_before_2_0(self, clean_registry):
        with pytest.raises(ValueError, match='not before 2.0'):
            deprecated(since='1.11.0', remove_in='1.99')
        with pytest.raises(ValueError, match='not before 2.0'):
            register('x', since='1.11.0', remove_in='1.12')
        assert register('y', since='1.11.0', remove_in='3.0').remove_in == '3.0'

    def test_the_same_row_twice(self, clean_registry):
        a = register('z', since='1.11.0')
        assert register('z', since='1.11.0') == a
        with pytest.raises(ValueError, match='differently'):
            register('z', since='1.12.0')


class TestForms:
    def test_keyframes_v1(self):
        from animageo.keyframes import KeyframeSequence
        data = {'keyframes': [{'t': 0, 'values': {}}, {'t': 1, 'values': {}}]}
        with pytest.warns(DeprecationWarning) as caught:
            try:
                KeyframeSequence.from_json(data, None)
            except Exception:  # the warning comes first; the data may be too thin to play
                pass
        text = str(caught[0].message)
        assert text.startswith("keyframes JSON without '\"version\": 2' uses the deprecated v1 schema.")
        assert text.endswith('Deprecated since 1.6.0; removed in 2.0.')

    def test_warn_unknown(self):
        with pytest.raises(KeyError):
            warn('no such deprecation')


def _doc_rows():
    rows = {}
    for line in DOC.read_text(encoding='utf-8').splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) == 4 and cells[0] not in ('Name', '---') and not set(cells[0]) <= {'-'}:
            rows[cells[0]] = (cells[1], cells[2], cells[3].strip('`') or None)
    return rows


def _package_rows():
    # every module that deprecates something registers it at import
    for path in sorted((REPO_ROOT / 'animageo').rglob('*.py')):
        text = path.read_text(encoding='utf-8')
        if path.name != '_deprecation.py' and re.search(r'\b_deprecation\b', text):
            module = '.'.join(path.relative_to(REPO_ROOT).with_suffix('').parts)
            __import__(module)
    return {name: (row.since, row.remove_in, row.alternative) for name, row in DEPRECATIONS.items()}


def test_doc_lists_every_deprecation():
    assert _doc_rows() == {name: (s, r, a.strip('`') if a else None) for name, (s, r, a) in _package_rows().items()}


def test_message_shape():
    assert Deprecation('f', since='1.11.0').message() == 'f is deprecated. Deprecated since 1.11.0; removed in 2.0.'
    assert Deprecation('f', since='1.11.0', alternative='g').message().endswith('removed in 2.0. Use g instead.')
