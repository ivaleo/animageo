# Contributing to AnimaGeo

Thanks for your interest in improving AnimaGeo! Bug reports, fixes, new
features, documentation, and example constructions are all welcome.

## Development setup

AnimaGeo targets **Python 3.10+**.

```bash
git clone https://github.com/ivaleo/animageo.git
cd animageo
python -m pip install -e ".[dev]"
```

The core dependencies (`numpy`, `manim`, `pycairo`, `sympy`, `scipy`) install
automatically. Rendering MP4/GIF additionally needs a working manim toolchain
(ffmpeg, and a LaTeX install for text labels); see the
[manim installation guide](https://docs.manim.community/en/stable/installation.html).

## Running the tests

```bash
python -m pytest tests/ -q
```

Please add or update tests for any behavioural change. Tests that need the
optional manim render dependency are marked `@pytest.mark.manim`.

## Coding conventions

- Match the style of the surrounding code — naming, structure, comment density.
- Library code uses the stdlib `logging` (`logging.getLogger(__name__)`); do not
  `print` from within the package.
- Keep public API changes reflected in the docs under `docs/` and in the type
  stubs (`*.pyi`) where relevant.

## Submitting changes

1. Fork the repository and create a topic branch.
2. Make your change with tests, and run the full test suite.
3. Open a pull request describing the motivation and the change.

## License of contributions

AnimaGeo is licensed under the [Apache License 2.0](LICENSE). By submitting a
contribution you agree that it is provided under the same terms (inbound =
outbound), per section 5 of the license.
