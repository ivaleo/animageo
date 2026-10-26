"""A TeX body that failed to compile is not compiled again in the process.

manim caches a ``Tex`` by its SVG: a body that compiled is read from
``tex_dir`` next time, but a failed one leaves no SVG, so LaTeX ran again on
every render — a drawing with a few labels that do not compile spent seconds
of LaTeX per render, warm process or not, and still drew no labels.
:func:`install` wraps manim's ``compile_tex``: the ``ValueError`` of a failed
compile is remembered by the TeX file (its name is the hash of the whole
document, template included) and raised again without running LaTeX.
``animageo.ui`` calls it once. Other errors (no LaTeX installed, a killed
process raising something else) are not remembered.
"""
from __future__ import annotations

import functools
import threading

MAX_ENTRIES = 4096
_MARK = '_animageo_failure_cache'

_lock = threading.Lock()
_failed: dict = {}


def clear() -> None:
    """Forget the remembered failures (after installing a font or a package)."""
    with _lock:
        _failed.clear()


def failures() -> int:
    """How many failed bodies are remembered."""
    with _lock:
        return len(_failed)


def install() -> bool:
    """Wrap ``manim.utils.tex_file_writing.compile_tex``; ``True`` when this
    call installed the wrapper. Idempotent."""
    import manim.utils.tex_file_writing as tex_file_writing
    current = tex_file_writing.compile_tex
    if getattr(current, _MARK, False):
        return False

    @functools.wraps(current)
    def compile_tex(tex_file, tex_compiler, output_format):
        key = (str(tex_file), tex_compiler, output_format)
        with _lock:
            message = _failed.get(key)
        if message is not None:
            raise ValueError(message)
        try:
            return current(tex_file, tex_compiler, output_format)
        except ValueError as e:
            with _lock:
                if len(_failed) >= MAX_ENTRIES:
                    _failed.clear()
                _failed[key] = str(e)
            raise

    setattr(compile_tex, _MARK, True)
    tex_file_writing.compile_tex = compile_tex
    return True


def installed() -> bool:
    import manim.utils.tex_file_writing as tex_file_writing
    return bool(getattr(tex_file_writing.compile_tex, _MARK, False))
