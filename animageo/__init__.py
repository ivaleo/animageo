"""AnimaGeo: geometric constructions to SVG/PNG/PDF/EPS/TeX/HTML and video.

``import animageo`` is light. ``animageo.native`` (the construction
document kernel) needs neither manim nor the classic modules. The classic,
manim backed API (``AnimaGeoScene``, ``GeoStyle``, … and the manim names of
``from animageo import *``) loads on the first access to one of its names
(PEP 562 ``__getattr__``) and then binds exactly the names the eager
``from .animageo import *`` of 1.10 bound (``tests/snapshots/star_import.json``).
Submodules (``animageo.native``, ``animageo.style``, …) import on their own.
"""

__version__ = "1.11.0rc1"

import importlib
import importlib.util
import os  # noqa: F401  (``os`` is a name of ``from animageo import *``, snapshot)
import sys

_classic_state = 'idle'  # 'idle' → 'loading' → 'loaded'


def _is_submodule(name: str) -> bool:
    """A module or subpackage of ``animageo`` (``native``, ``style``, ``dsl``…).

    ``from animageo import native`` asks ``hasattr(animageo, 'native')``
    first; answering it must not load the classic API.
    """
    if f'{__name__}.{name}' in sys.modules:
        return True
    try:
        return importlib.util.find_spec(f'{__name__}.{name}') is not None
    except (ImportError, ValueError):
        return False


def _manim_importable() -> bool:
    """True when ``manim`` can be found.

    Without manim the classic import fails anyway; checking first keeps the
    classic modules (``animageo.geo``, ``animageo.style``) from being half
    imported on the way to that failure.
    """
    try:
        return importlib.util.find_spec('manim') is not None
    except (ImportError, ValueError):
        return False


def _load_classic() -> None:
    """Import ``animageo.animageo`` and bind its public names in this package,
    as ``from .animageo import *`` did at import time up to 1.10."""
    global _classic_state
    if _classic_state != 'idle':
        return
    if not _manim_importable():
        raise ModuleNotFoundError("No module named 'manim'", name='manim')
    _classic_state = 'loading'
    try:
        classic = importlib.import_module('.animageo', __name__)
    except BaseException:
        _classic_state = 'idle'
        raise
    names = getattr(classic, '__all__', None)
    if names is None:
        names = [name for name in vars(classic) if not name.startswith('_')]
    package = globals()
    for name in names:
        package[name] = getattr(classic, name)
    _classic_state = 'loaded'


def _no_attribute(name: str, hint: str = '') -> AttributeError:
    return AttributeError(f"module {__name__!r} has no attribute {name!r}{hint}")


def __getattr__(name: str):
    if name == '__all__':
        # ``from animageo import *``: the names 1.10 gave, so load first
        try:
            _load_classic()
        except ModuleNotFoundError as exc:
            if exc.name != 'manim':
                raise
            raise _no_attribute(name) from exc
        return [key for key in globals() if not key.startswith('_')]
    if name.startswith('_') or _classic_state != 'idle' or _is_submodule(name):
        raise _no_attribute(name)
    try:
        _load_classic()
    except ModuleNotFoundError as exc:
        if exc.name != 'manim':
            raise
        raise _no_attribute(name, ' (the classic API needs manim)') from exc
    try:
        return globals()[name]
    except KeyError:
        raise _no_attribute(name) from None
