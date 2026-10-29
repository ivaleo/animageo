"""Anonymous, reproducible IMP-5 corpus, separate from external GGB files.

Regenerate with ``python -m tests.native.ggb_imp5``.
"""
from pathlib import Path

from tests.native.ggb_synth import command, element, ggb_bytes, line_style, point

DIRECTORY = Path(__file__).parent / 'import' / 'imp5'
PATTERNS = {0: [], 10: [7., 4.], 15: [11., 8.], 20: [3., 3.], 30: [11., 4., 3., 4.]}


def dash_body(kind):
    return (point('A', 0., 0., label_shown=False) + point('B', 4., 0., label_shown=False)
            + command('Segment', ['A', 'B'], ['s'])
            + element('segment', 's', label_shown=False, extra=line_style(6, kind, 128)))


def layers_body():
    return (point('A', 0., 0.) + point('B', 3., 0.)
            + command('Circle', ['A', 'B'], ['c'])
            + element('conic', 'c', alpha=.5, extra=line_style())
            .replace('<layer val="0"/>', '<layer val="2"/>')
            + point('C', 1., 0.).replace('<layer val="0"/>', '<layer val="1"/>'))


def labels_body():
    body = point('A', 0., 0.) + point('B', 4., 0.)
    for mode in range(4):
        name = f's{mode}'
        body += command('Segment', ['A', 'B'], [name]) + element('segment', name,
            extra=line_style() + '<caption val="base"/><labelOffset x="15" y="-10"/>').replace(
                '<labelMode val="0"/>', f'<labelMode val="{mode}"/>')
    return body + point('H', 1., 2., label_shown=False, show=False)


def slider_body(playing=True, speed='2.5'):
    return (element('numeric', 'n', extra='<value val="3"/><slider min="1" max="5"/>'
                    f'<animation step="0.25" speed="{speed}" type="0" playing="{str(playing).lower()}"/>')
            + point('A', 0., 0.) + command('Circle', ['A', 'n'], ['c'])
            + element('conic', 'c', extra=line_style()
                      + '<matrix A0="1" A1="1" A2="-9" A3="0" A4="0" A5="0"/>'))


def bodies():
    return {**{f'dash_{kind}': dash_body(kind) for kind in PATTERNS},
            'layers': layers_body(), 'labels': labels_body(),
            'slider_playing': slider_body(), 'slider_paused': slider_body(False, '1')}


def generate():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    for name, body in bodies().items():
        (DIRECTORY / f'{name}.ggb').write_bytes(ggb_bytes(body))


if __name__ == '__main__':
    generate()
