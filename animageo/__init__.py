__version__ = "1.9.0a1.dev2"

import importlib.util
import os
import sys


def _is_native_module(name: str) -> bool:
    return name == 'animageo.native' or name.startswith('animageo.native.')


def _dash_m_module():
    """The module of ``python -m <module>`` from ``sys.orig_argv``, else ``None``.

    While ``-m`` locates the module, ``sys.argv[0]`` is ``'-m'``, so the
    interpreter command line is read from ``sys.orig_argv``; interpreter
    options before ``-m`` are skipped, a script or ``-c`` ends the search.
    """
    orig = list(getattr(sys, 'orig_argv', None) or ())
    i = 1
    while i < len(orig):
        arg = orig[i]
        if arg == '-m':
            return orig[i + 1] if i + 1 < len(orig) else None
        if arg.startswith('-m'):
            return arg[2:]
        if arg in ('-X', '-W', '--check-hash-based-pycs'):
            i += 2
            continue
        if arg == '-' or not arg.startswith('-') or arg.startswith('-c'):
            return None
        i += 1
    return None


def _running_native_main() -> bool:
    """True when Python is bootstrapping ``python -m animageo.native``.

    Once the module runs, ``sys.argv[0]`` is the path of
    ``animageo/native/__main__.py``; before that the ``-m`` module is read
    from ``sys.orig_argv``.
    """
    argv0 = sys.argv[0] if sys.argv else ''
    if (
        os.path.basename(argv0) == '__main__.py'
        and os.path.basename(os.path.dirname(argv0)) == 'native'
    ):
        return True
    module = _dash_m_module()
    return module is not None and _is_native_module(module)


def _running_package_main() -> bool:
    """True when Python is bootstrapping ``python -m animageo``.

    In that path Python imports this package before executing
    ``animageo.__main__``. Importing the full Manim-backed API here can leave
    heavyweight runtime state around even when the CLI exits early on invalid
    arguments, so keep package-main startup light. ``python -m animageo`` is
    recognised from ``sys.orig_argv`` (whatever its arguments: a ``.ggb`` or
    a ``.json`` document), the ``animageo`` console script by its name, and
    a ``.ggb`` argument as before. ``python -m animageo.native`` never needs
    manim and is treated the same way.
    """
    argv0 = sys.argv[0] if sys.argv else ''
    base = os.path.basename(argv0)
    parent = os.path.basename(os.path.dirname(argv0))
    looks_like_cli_args = any(arg.endswith('.ggb') for arg in sys.argv[1:])
    return (
        (base == '__main__.py' and parent == 'animageo')
        or base == 'animageo'
        or looks_like_cli_args
        or _dash_m_module() in ('animageo', 'animageo.__main__')
        or _running_native_main()
    )


def _manim_importable() -> bool:
    """True when ``manim`` can be found.

    Without manim the classic import below fails anyway; checking first keeps
    ``import animageo.native`` from half-importing the classic modules
    (``animageo.geo``, ``animageo.style``) on the way to that failure.
    """
    try:
        return importlib.util.find_spec('manim') is not None
    except (ImportError, ValueError):
        return False


if not _running_package_main() and _manim_importable():
    try:
        from .animageo import *
    except ModuleNotFoundError as exc:
        if exc.name != 'manim':
            raise
