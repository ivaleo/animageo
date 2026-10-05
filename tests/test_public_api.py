"""The public API is a snapshot (1.11.0rc1, L6 item 5).

``tests/snapshots/public_api.json`` holds the names and the signatures of
``animageo.native.__all__`` (plus the names outside ``__all__`` the web
imports) and of the top level of ``animageo`` (the names of the classic API
that ``from animageo import *`` gives and that do not come from manim).
A change of the snapshot goes only together with a line of CHANGELOG; the
snapshot is rewritten by::

    python tests/test_public_api.py --write

A signature is written without annotations (they are strings or typing
objects whose text differs between Python versions); a default is its
``repr`` when that is a plain literal, else ``<type>``.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO_ROOT / 'tests' / 'snapshots' / 'public_api.json'
STAR_PATH = REPO_ROOT / 'tests' / 'snapshots' / 'star_import.json'

# Names of ``animageo.native`` outside ``__all__`` that the web imports
# (``from animageo.native import REGISTRY_VERSION, bound_producer``).
NATIVE_OUTSIDE_ALL = ('REGISTRY_VERSION', 'as_document', 'bound_producer')

# Experimental, outside the snapshot (plan L5 §4.3) — when it exists.
EXPERIMENTAL = frozenset({'run_scenario'})


class _Text:
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


def _default(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        text = repr(value)
    elif isinstance(value, tuple) and all(v is None or isinstance(v, (bool, int, float, str)) for v in value):
        text = repr(value)
    else:
        text = repr(value)
        if ' at 0x' in text or len(text) > 40 or not text.startswith('<'):
            text = f'<{type(value).__name__}>'
    return _Text(text)


def signature(obj) -> str | None:
    """``(a, b=None, *, c=1)`` of ``obj`` without annotations; ``None`` when
    Python has none (a builtin)."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return None
    params = []
    for p in sig.parameters.values():
        default = p.default if p.default is inspect.Parameter.empty else _default(p.default)
        params.append(p.replace(annotation=inspect.Parameter.empty, default=default))
    return str(sig.replace(parameters=params, return_annotation=inspect.Signature.empty))


def _own_class_members(cls) -> dict:
    """Public members defined by the ``animageo`` classes of ``cls``'s MRO."""
    out = {}
    for klass in reversed(cls.__mro__):
        if not (getattr(klass, '__module__', '') or '').startswith('animageo'):
            continue
        for name, value in vars(klass).items():
            if name.startswith('_'):
                continue
            if isinstance(value, (staticmethod, classmethod)):
                out[name] = signature(value.__func__)
            elif isinstance(value, property):
                out[name] = 'property'
            elif inspect.isfunction(value):
                out[name] = signature(value)
            else:
                out[name] = 'attribute'
    return dict(sorted(out.items()))


def describe(obj) -> dict:
    """The snapshot entry of a public name."""
    if inspect.ismodule(obj):
        return {'kind': 'module', 'module': obj.__name__}
    if inspect.isclass(obj):
        entry = {'kind': 'exception' if issubclass(obj, BaseException) else 'class'}
        own_init = any((getattr(k, '__module__', '') or '').startswith('animageo')
                       and ('__init__' in vars(k) or '__new__' in vars(k)
                            or '__dataclass_fields__' in vars(k))
                       for k in obj.__mro__)
        if own_init:
            entry['signature'] = signature(obj)
        members = _own_class_members(obj)
        if members:
            entry['members'] = members
        return entry
    if callable(obj):
        return {'kind': 'function', 'signature': signature(obj)}
    entry = {'kind': 'constant', 'type': type(obj).__name__}
    if isinstance(obj, (str, int, float, bool, tuple)):
        entry['value'] = list(obj) if isinstance(obj, tuple) else obj
    return entry


def native_api() -> dict:
    from animageo import native
    names = [n for n in native.__all__ if n not in EXPERIMENTAL]
    return {
        'all': sorted(names),
        'names': {n: describe(getattr(native, n)) for n in sorted(names)},
        'outside_all': {n: describe(getattr(native, n)) for n in NATIVE_OUTSIDE_ALL},
    }


def top_api() -> dict:
    """The own names of ``from animageo import *`` (``star_import.json``)."""
    import animageo
    own = json.loads(STAR_PATH.read_text(encoding='utf-8'))['own']
    return {n: describe(getattr(animageo, n)) for n in own}


def build() -> dict:
    return {
        'about': ('Public API of animageo: animageo.native.__all__ (+ the names outside __all__ the web '
                  'imports) and the own names of the top level. Changed only together with CHANGELOG; '
                  'rewritten by `python tests/test_public_api.py --write`.'),
        'since': '1.11.0rc1',
        'native': native_api(),
        'top': top_api(),
    }


def _manim_available():
    return importlib.util.find_spec('man' + 'im') is not None


@pytest.fixture(scope='module')
def snapshot():
    return json.loads(SNAPSHOT_PATH.read_text(encoding='utf-8'))


def _diff(expected: dict, actual: dict) -> list:
    out = []
    for name in sorted(set(expected) | set(actual)):
        if name not in actual:
            out.append(f'- {name}: gone')
        elif name not in expected:
            out.append(f'+ {name}: new')
        elif expected[name] != actual[name]:
            out.append(f'~ {name}: {expected[name]} → {actual[name]}')
    return out


class TestNative:
    def test_names(self, snapshot):
        assert native_api()['all'] == snapshot['native']['all']

    def test_signatures(self, snapshot):
        assert _diff(snapshot['native']['names'], native_api()['names']) == []

    def test_names_the_web_imports_outside_all(self, snapshot):
        assert _diff(snapshot['native']['outside_all'], native_api()['outside_all']) == []

    def test_all_is_importable(self):
        from animageo import native
        assert [n for n in native.__all__ if not hasattr(native, n)] == []
        assert len(native.__all__) == len(set(native.__all__))

    def test_experimental_is_outside(self, snapshot):
        assert not EXPERIMENTAL & set(snapshot['native']['names'])


@pytest.mark.skipif(not _manim_available(), reason='requires optional dependency manim')
class TestTopLevel:
    def test_own_names_and_signatures(self, snapshot):
        assert _diff(snapshot['top'], top_api()) == []

    def test_snapshot_covers_the_star_import(self, snapshot):
        own = json.loads(STAR_PATH.read_text(encoding='utf-8'))['own']
        assert sorted(snapshot['top']) == sorted(own)


def test_snapshot_is_written_by_this_module(snapshot):
    """The file is exactly what ``--write`` writes (no hand edits)."""
    assert snapshot['about'].startswith('Public API of animageo')
    assert set(snapshot) == {'about', 'since', 'native', 'top'}


def main(argv) -> int:
    if argv[1:] != ['--write']:
        print(__doc__)
        return 2
    SNAPSHOT_PATH.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'wrote {SNAPSHOT_PATH}')
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(REPO_ROOT))
    raise SystemExit(main(sys.argv))
