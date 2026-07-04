"""Tests for the CLI entry point (animageo.__main__).

Regression: the pre-1.1 CLI built the manim driver script with f-string
concatenation of user-supplied arguments and ran it via ``os.system`` — a
classic shell/Python injection vector. The rewrite embeds every user
string via ``repr()`` and invokes manim through ``subprocess.run`` with
an argv list. These tests lock in the new contract.
"""
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from animageo import __main__ as cli


DRIVER_KWARGS = dict(
    reference=None,
    content={'source': 'source_view'},
    export={'size': {'width': 640, 'height': 480}},
    # The CLI builds the export call with the output path repr-embedded; the
    # template inserts it verbatim. Mirror that here.
    export_call="self.exportSVG({!r})".format("out.svg"),
)


class TestDriverTemplate:
    """The generated driver must embed user strings via repr(), so that
    filenames containing quotes/newlines cannot break out of the literal."""

    def _ast_calls(self, code):
        """Return the set of dotted call-names appearing as ``Call(func=...)`` nodes."""
        import ast
        tree = ast.parse(code)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                parts = []
                while isinstance(func, ast.Attribute):
                    parts.insert(0, func.attr)
                    func = func.value
                if isinstance(func, ast.Name):
                    parts.insert(0, func.id)
                if parts:
                    names.add('.'.join(parts))
        return names

    def test_filename_with_single_quote_compiles(self):
        code = cli._DRIVER_TEMPLATE.format(
            ggbfile="a'b.ggb",
            style='',
            debug=False,
            output="out.svg",
            **DRIVER_KWARGS,
        )
        compile(code, 'driver.py', 'exec')

    def test_injection_payload_stays_inside_string_literal(self):
        """Adversarial filename must not introduce any new code paths."""
        code_baseline = cli._DRIVER_TEMPLATE.format(
            ggbfile="safe.ggb",
            style='', debug=False, output="o.svg",
            **DRIVER_KWARGS,
        )
        code_attack = cli._DRIVER_TEMPLATE.format(
            ggbfile="x.ggb'); __import__('os').system('rm -rf /'); ('",
            style='', debug=False, output="o.svg",
            **DRIVER_KWARGS,
        )
        # Both compile, and the call sites in the attack-payload variant
        # are identical to the baseline — the payload lives inside a string.
        compile(code_baseline, 'driver.py', 'exec')
        compile(code_attack, 'driver.py', 'exec')
        assert self._ast_calls(code_baseline) == self._ast_calls(code_attack)

    def test_template_uses_repr_for_every_placeholder(self):
        """All format placeholders must use !r so they're always repr'd."""
        placeholders = [
            '{ggbfile}', '{style}', '{reference}', '{content}', '{export}',
            '{debug}',
        ]
        for p in placeholders:
            assert p not in cli._DRIVER_TEMPLATE, (
                f"unquoted placeholder {p} — must be !r-quoted"
            )


class TestParsePx:
    def test_default(self):
        assert cli._parse_size(None) is None

    def test_numeric(self):
        assert cli._parse_size(['800', '600']) == [800, 600]

    def test_auto(self):
        assert cli._parse_size(['auto', 'auto']) == ['auto', 'auto']

    def test_optional_size(self):
        assert cli._parse_size(None) is None
        assert cli._parse_size(['1920', '1080']) == [1920, 1080]

    def test_float_pair(self):
        assert cli._parse_float_pair(['1.5', '-2']) == [1.5, -2.0]


class TestFormatResolution:
    def _args(self, fmt=None, output=None):
        return SimpleNamespace(format=fmt, output=output)

    def test_explicit_format_overrides_extension(self):
        assert cli._resolve_format(self._args(fmt='pdf', output='x.svg')) == 'pdf'

    def test_infer_from_extension(self):
        assert cli._resolve_format(self._args(output='out.pdf')) == 'pdf'
        assert cli._resolve_format(self._args(output='out.eps')) == 'eps'
        assert cli._resolve_format(self._args(output='out.tex')) == 'tikz'
        assert cli._resolve_format(self._args(output='out.svg')) == 'svg'
        assert cli._resolve_format(self._args(output='board.html')) == 'jsxgraph'
        assert cli._resolve_format(self._args(output='anim.gif')) == 'gif'
        assert cli._resolve_format(self._args(output='clip.mp4')) == 'mp4'
        assert cli._resolve_format(self._args(output='clip.webm')) == 'webm'

    def test_default_is_svg(self):
        assert cli._resolve_format(self._args()) == 'svg'
        assert cli._resolve_format(self._args(output='noext')) == 'svg'

    def test_format_maps_are_consistent(self):
        for fmt, ext in cli.EXT_BY_FORMAT.items():
            assert cli.FORMAT_BY_EXT[ext] == fmt
        assert set(cli.ALL_FORMATS) == set(cli.EXT_BY_FORMAT)
        assert set(cli.ALL_FORMATS) == set(cli.STATIC_FORMATS) | set(cli.RENDER_FORMATS)


class TestRenderDriverTemplate:
    """The render driver, like the static one, must embed user strings via
    repr() so a hostile filename cannot break out of the literal."""

    def test_compiles_with_keyframes(self):
        play = ("with open('kf.json') as _kf:\n"
                "            self.play_keyframes(json.load(_kf))")
        code = cli._RENDER_DRIVER_TEMPLATE.format(
            ggbfile="x.ggb", style='', reference=None,
            content={'source': 'source_view'},
            export={'size': {'width': 640, 'height': 480}},
            debug=False, play_call=play,
        )
        compile(code, 'render_driver.py', 'exec')

    def test_adversarial_ggbfile_stays_in_literal(self):
        code = cli._RENDER_DRIVER_TEMPLATE.format(
            ggbfile="x.ggb'); __import__('os').system('boom'); ('",
            style='', reference=None, content={}, export={},
            debug=False, play_call="pass",
        )
        compile(code, 'render_driver.py', 'exec')

    def test_template_reprs_user_strings(self):
        for p in ['{ggbfile}', '{style}', '{reference}', '{content}',
                  '{export}', '{debug}']:
            assert p not in cli._RENDER_DRIVER_TEMPLATE, (
                f"unquoted placeholder {p} — must be !r-quoted"
            )


class TestCliNoManim:
    """End-to-end: invoking the CLI with a bad path must exit cleanly
    *without* spawning manim (so injection via filename is prevented upfront)."""

    def test_missing_file_returns_2(self):
        result = subprocess.run(
            [sys.executable, '-m', 'animageo', '/tmp/definitely-not-a-real-file.ggb'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2
        assert 'not found' in (result.stdout + result.stderr).lower()

    def test_missing_style_returns_2(self, tmp_path):
        real_ggb = tmp_path / 'dummy.ggb'
        real_ggb.write_text('not-really-a-ggb')
        result = subprocess.run(
            [sys.executable, '-m', 'animageo', str(real_ggb),
             '--style', '/tmp/nonexistent-style.json'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2


class TestAiGuideFlag:
    def test_ai_guide_prints_packaged_guide(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['animageo', '--ai-guide'])
        cli.main()
        out = capsys.readouterr().out
        assert out.startswith('# AnimaGeo')
        assert 'putCode' in out

    def test_missing_ggbfile_still_errors(self, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['animageo'])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 2
