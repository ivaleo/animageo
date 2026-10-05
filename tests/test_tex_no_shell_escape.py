"""LaTeX of labels runs without shell escape (1.11.0rc1, L6 item 13):
manim's compilation command carries ``-no-shell-escape`` once
``animageo.ui`` is imported, and a ``\\write18`` in a label runs nothing."""
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip('man' + 'im')

import animageo.ui  # noqa: E402,F401  (installs the wrapper)
from animageo import _tex_security  # noqa: E402
from animageo._tex_security import NO_SHELL_ESCAPE, no_shell_escape  # noqa: E402

import importlib  # noqa: E402

tex_file_writing = importlib.import_module('man' + 'im.utils.tex_file_writing')


class TestCommand:
    def test_installed_by_animageo_ui(self):
        assert _tex_security.installed()
        assert _tex_security.install() is False          # idempotent

    @pytest.mark.parametrize('compiler,fmt', [('latex', '.dvi'), ('pdflatex', '.pdf'), ('xelatex', '.xdv'),
                                              ('lualatex', '.pdf')])
    def test_every_compiler(self, compiler, fmt):
        command = tex_file_writing.make_tex_compilation_command(compiler, fmt, Path('a.tex'), Path('.'))
        assert command[0] == compiler and command[1] == NO_SHELL_ESCAPE
        assert command.count(NO_SHELL_ESCAPE) == 1
        assert command[-1] == 'a.tex'

    def test_an_explicit_flag_is_left_alone(self):
        assert no_shell_escape(['latex', '-shell-escape', 'a.tex']) == ['latex', '-shell-escape', 'a.tex']
        assert no_shell_escape(['latex', 'a.tex']) == ['latex', NO_SHELL_ESCAPE, 'a.tex']
        assert no_shell_escape([]) == []
        # a path that mentions it is no flag
        assert no_shell_escape(['latex', '/tmp/write18-shell-escape/a.tex'])[1] == NO_SHELL_ESCAPE
        assert no_shell_escape(['xelatex', '--disable-write18', 'a.tex']) == ['xelatex', '--disable-write18', 'a.tex']

    def test_compile_tex_runs_the_wrapped_command(self, tmp_path, monkeypatch):
        seen = []

        def fake_run(command, **kwargs):
            seen.append(list(command))
            return subprocess.CompletedProcess(command, 0)

        monkeypatch.setattr(tex_file_writing.subprocess, 'run', fake_run)
        monkeypatch.setattr(tex_file_writing.config, 'tex_dir', str(tmp_path))
        tex_file_writing.compile_tex(tmp_path / 'label.tex', 'latex', '.dvi')
        assert seen and seen[0][:2] == ['latex', NO_SHELL_ESCAPE]


WRITE18 = r"""\documentclass{article}
\begin{document}
\typeout{SHELLESCAPE=\the\pdfshellescape}
\immediate\write18{touch pwned-by-label}
\immediate\write18{kpsewhich --version}
A
\end{document}
"""


@pytest.mark.skipif(shutil.which('latex') is None, reason='requires latex')
def test_write18_runs_nothing(tmp_path, monkeypatch):
    tex = tmp_path / 'label.tex'
    tex.write_text(WRITE18, encoding='utf-8')
    monkeypatch.setattr(tex_file_writing.config, 'tex_dir', str(tmp_path))
    monkeypatch.chdir(tmp_path)
    tex_file_writing.compile_tex(tex, 'latex', '.dvi')
    log = (tmp_path / 'label.log').read_text(encoding='latin-1')
    assert 'SHELLESCAPE=0' in log                         # 1 = enabled, 2 = restricted
    assert 'runsystem(touch pwned-by-label)...disabled.' in log
    assert 'runsystem(kpsewhich --version)...disabled.' in log   # allowed when restricted
    assert not (tmp_path / 'pwned-by-label').exists()
    assert (tmp_path / 'label.dvi').exists()


@pytest.mark.skipif(shutil.which('latex') is None, reason='requires latex')
def test_without_the_flag_the_distribution_default_would_apply(tmp_path):
    """The control: the same file through the command manim builds itself
    (no flag) is not at 0 here — so the test above proves the flag."""
    tex = tmp_path / 'label.tex'
    tex.write_text(WRITE18, encoding='utf-8')
    original = tex_file_writing.make_tex_compilation_command.__wrapped__
    subprocess.run(original('latex', '.dvi', Path('label.tex'), Path('.')), cwd=tmp_path,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    log = (tmp_path / 'label.log').read_text(encoding='latin-1')
    level = log.split('SHELLESCAPE=', 1)[1][:1]
    if level == '0':
        pytest.skip('this TeX disables \\write18 by default already')
    assert level in ('1', '2')
