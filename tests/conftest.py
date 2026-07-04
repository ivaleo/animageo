import ast
import importlib.util
import inspect
import os
from pathlib import Path
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


_MANIM_AVAILABLE = importlib.util.find_spec('manim') is not None
_MANIM_SKIP = pytest.mark.skip(reason='requires optional dependency manim')


def _is_manim_import(node):
    if isinstance(node, ast.Import):
        return any(alias.name == 'manim' or alias.name.startswith('manim.') for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.module == 'manim' or node.module == 'animageo.animageo'
    return False


def _has_collection_time_manim_import(path):
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False

    for node in tree.body:
        if _is_manim_import(node):
            return True
        if isinstance(node, ast.ClassDef) and any(_is_manim_import(child) for child in node.body):
            return True
    return False


def pytest_ignore_collect(collection_path, config):
    if _MANIM_AVAILABLE:
        return False

    path = Path(str(collection_path))
    if path.suffix == '.py' and path.name.startswith('test_') and _has_collection_time_manim_import(path):
        return True
    return False


def _source_requires_manim(obj):
    try:
        source = inspect.getsource(obj)
    except (OSError, TypeError):
        return False
    return 'animageo.animageo' in source or 'from manim import' in source or 'import manim' in source


def pytest_collection_modifyitems(config, items):
    if _MANIM_AVAILABLE:
        return

    for item in items:
        if _source_requires_manim(getattr(item, 'cls', None)) or _source_requires_manim(item.obj):
            item.add_marker(_MANIM_SKIP)
