__version__ = "1.7.10"

import os
import sys


def _running_package_main() -> bool:
    """True when Python is bootstrapping ``python -m animageo``.

    In that path Python imports this package before executing
    ``animageo.__main__``. Importing the full Manim-backed API here can leave
    heavyweight runtime state around even when the CLI exits early on invalid
    arguments, so keep package-main startup light.
    """
    argv0 = sys.argv[0] if sys.argv else ''
    base = os.path.basename(argv0)
    parent = os.path.basename(os.path.dirname(argv0))
    looks_like_cli_args = any(arg.endswith('.ggb') for arg in sys.argv[1:])
    return (
        (base == '__main__.py' and parent == 'animageo')
        or base == 'animageo'
        or looks_like_cli_args
    )


if not _running_package_main():
    try:
        from .animageo import *
    except ModuleNotFoundError as exc:
        if exc.name != 'manim':
            raise
