"""LaTeX of labels runs without shell escape (1.11.0rc1).

manim compiles a ``Tex`` with ``latex -interaction=batchmode …`` and no
shell-escape flag, so the default of the TeX distribution applies — TeX
Live's restricted ``\\write18`` (``shell_escape = p``) still runs a list of
programs. A label is text of a document (a ``.ggb``, a DSL scene, a
construction document): it runs nothing. :func:`install` makes manim's
compilation command carry ``-no-shell-escape``; ``animageo.ui`` (imported
by every classic render path and by :func:`animageo.native.render`) calls
it once. Idempotent; a command that already has the flag is left alone.

The flag covers ``\\write18`` only. Reading files (``\\input``) is limited by
kpathsea's ``openin_any`` — set ``openin_any=p`` in the environment of
the process that renders untrusted labels (the web does).
"""
from __future__ import annotations

import functools

NO_SHELL_ESCAPE = '-no-shell-escape'
_MARK = '_animageo_no_shell_escape'
# flags that already decide \write18 (TeX Live; MiKTeX spellings)
_SHELL_FLAGS = frozenset({'shell-escape', 'no-shell-escape', 'shell-restricted',
                          'enable-write18', 'disable-write18', 'restrict-write18'})


def no_shell_escape(command):
    """``command`` (an argv list: compiler first) with ``-no-shell-escape``
    right after the compiler; unchanged when a shell-escape flag is there."""
    command = list(command)
    if not command or any(arg.startswith('-') and arg.lstrip('-') in _SHELL_FLAGS for arg in command[1:]):
        return command
    return [command[0], NO_SHELL_ESCAPE, *command[1:]]


def install() -> bool:
    """Wrap ``manim.utils.tex_file_writing.make_tex_compilation_command``;
    ``True`` when this call installed the wrapper."""
    import manim.utils.tex_file_writing as tex_file_writing

    current = tex_file_writing.make_tex_compilation_command
    if getattr(current, _MARK, False):
        return False

    @functools.wraps(current)
    def make_tex_compilation_command(*args, **kwargs):
        return no_shell_escape(current(*args, **kwargs))

    setattr(make_tex_compilation_command, _MARK, True)
    tex_file_writing.make_tex_compilation_command = make_tex_compilation_command
    return True


def installed() -> bool:
    import manim.utils.tex_file_writing as tex_file_writing
    return bool(getattr(tex_file_writing.make_tex_compilation_command, _MARK, False))
