"""Re-export of :class:`animageo.style.proxy.StyleProxy` for the DSL layer.

The real implementation lives in :mod:`animageo.style.proxy` so the
geometry layer can depend on it without cross-importing from
``parsers``. This module is kept as a convenience entry point for
code that already imports from ``animageo.parsers.dsl``.
"""

from ...style.proxy import StyleProxy

__all__ = ["StyleProxy"]
