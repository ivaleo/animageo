"""Modules removed from the package (CHANGELOG «Removed»); nothing in the
package may refer to them. 1.11.0rc1: ``animageo.parsers.ggb_generator``, the
dead and broken writer of ``.ggb`` (kernel spec §15; there is no ``.ggb``
writer in 1.x)."""
import importlib.util
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / 'animageo'

REMOVED = {
    'animageo.parsers.ggb_generator': '1.11.0rc1',
}


@pytest.mark.parametrize('module', sorted(REMOVED))
def test_module_is_gone(module):
    assert importlib.util.find_spec(module) is None
    assert not (PACKAGE.parent / (module.replace('.', '/') + '.py')).exists()


@pytest.mark.parametrize('module', sorted(REMOVED))
def test_nothing_in_the_package_refers_to_it(module):
    short = module.rsplit('.', 1)[1]
    offenders = []
    for path in sorted(PACKAGE.rglob('*')):
        if path.suffix not in ('.py', '.pyi', '.md', '.json', '.txt') or '__pycache__' in path.parts:
            continue
        if short in path.read_text(encoding='utf-8', errors='replace'):
            offenders.append(str(path.relative_to(PACKAGE.parent)))
    assert offenders == []
