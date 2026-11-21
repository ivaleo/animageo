"""Bounded literal text-block documents and deterministic RusTex glyph layout.

No renderer or external font measurement is imported here. Coordinates are em
of the selected size, with a top-left origin and baselines increasing downward.
Glyphs use the bundled T2A font at its design size; explicit positions disable
TeX ligature substitution, so literal punctuation is never reinterpreted.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import regex

from .canonical import sha256_of
from .labels.tex import TEXT_CODES as _LABEL_CODES, metrics

MAX_CODEPOINTS = 20_000
MAX_PARAGRAPHS = 200
MAX_SCENE_CODEPOINTS = 32_000
MAX_SCENE_GLYPHS = 60_000
MAX_SCENE_BLOCKS = 200
MAX_SCENE_OUTLINE_POINTS = 8_500_000
# Conservative per-glyph control-point maxima for the fixed Latin/Cyrillic
# outlines and supported accent slots. The atlas checks these on load.
BASE_OUTLINE_POINTS = 312
ACCENT_OUTLINE_POINTS = 56
FONT = 'larm1000'
EM_PT = 10.0
LINE_HEIGHT = 1.32
# T2A's text symbols and extended Cyrillic alphabet (t2aenc.def). Keep the
# historical label mapper unchanged: blocks have a separate literal profile.
TEXT_CODES = dict(_LABEL_CODES, **{'“': 16, '”': 17, '„': 189, '‘': 96, '’': 39,
    '§': 159, '¤': 158, '‹': 14, '›': 15, 'ı': 25, 'ȷ': 26, 'І': 73, 'і': 105,
    'Ј': 74, 'ј': 106})
for _i, _upper in enumerate('ҐҒЂЋҺҖҘЉЇҚҠҜӔҢҤЅӨҪЎҮҰҲЏҸҶЄӘЊ'):
    TEXT_CODES[_upper] = 128 + _i
    TEXT_CODES[_upper.lower()] = 160 + _i
_INVALID = re.compile(r'[\x00\ud800-\udfff]')
_NON_LITERAL = re.compile(r'[\x00\r\n\t\ud800-\udfff]')
_GRAPHEMES = regex.compile(r'\X')
_ACCENTS = {'\u0300': 0, '\u0301': 1, '\u0302': 2, '\u0303': 3,
            '\u0308': 4, '\u030a': 6, '\u030c': 7, '\u0306': 8,
            '\u0304': 9, '\u0307': 10}


def _paragraphs(text):
    result = []
    for paragraph in text.split('\n\n'):
        runs = []
        for i, line in enumerate(paragraph.split('\n')):
            if i:
                runs.append({'kind': 'break'})
            if line:
                runs.append({'kind': 'text', 'text': line})
        result.append({'runs': runs})
    return result


def _record(value, keys, field):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f'{field}: expected fields {", ".join(keys)}')


def text_block_plain_text(content):
    """Serialize validated ``text-block/v1`` content, preserving every space/LF."""
    return '\n\n'.join(''.join(r['text'] if r['kind'] == 'text' else '\n'
                               for r in p['runs']) for p in content['paragraphs'])


def validate_text_block(content):
    """Validate canonical plain content, returning a detached canonical copy."""
    _record(content, ('version', 'paragraphs'), 'content')
    if content['version'] != 'text-block/v1':
        raise ValueError('content.version: text-block/v1 required')
    paragraphs = content['paragraphs']
    if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= MAX_PARAGRAPHS:
        raise ValueError('content.paragraphs: 1 to 200 required')
    count, runs_count = 2 * (len(paragraphs) - 1), 0
    for paragraph in paragraphs:
        _record(paragraph, ('runs',), 'content.paragraph')
        runs = paragraph['runs']
        if not isinstance(runs, list) or len(runs) > MAX_CODEPOINTS:
            raise ValueError('content.paragraph.runs: at most 20000 required')
        runs_count += len(runs)
        if runs_count > MAX_CODEPOINTS:
            raise ValueError('content.runs: at most 20000 required')
        for run in runs:
            if not isinstance(run, dict):
                raise ValueError('content.run: text or break required')
            if run.get('kind') == 'break':
                _record(run, ('kind',), 'content.break')
                count += 1
            elif run.get('kind') == 'text':
                _record(run, ('kind', 'text'), 'content.text')
                text = run['text']
                if not isinstance(text, str) or len(text) > MAX_CODEPOINTS or _NON_LITERAL.search(text):
                    raise ValueError('content.text: normalized Unicode text without NUL, CR, LF, tabs or surrogates required')
                count += len(text)
            else:
                raise ValueError('content.run.kind: text or break required')
            if count > MAX_CODEPOINTS:
                raise ValueError('content: at most 20000 Unicode code points')
    plain = text_block_plain_text(content)
    canonical = _paragraphs(plain)
    if paragraphs != canonical:
        raise ValueError('content.paragraphs: canonical plain structure required; normalize plain input')
    return {'version': 'text-block/v1', 'paragraphs': canonical}


def normalize_text_block(text):
    """Normalize plain input as the web draft does; never interpret templates/TeX."""
    if not isinstance(text, str):
        raise ValueError('text: string required')
    if len(text) > MAX_CODEPOINTS * 2 or _INVALID.search(text):
        raise ValueError('content: at most 20000 Unicode code points without NUL or surrogates')
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\t', '    ')
    if len(text) > MAX_CODEPOINTS:
        raise ValueError('content: at most 20000 Unicode code points')
    return validate_text_block({'version': 'text-block/v1', 'paragraphs': _paragraphs(text)})


def _dimension(value, lo, hi, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise ValueError(f'{field}: finite number from {lo} to {hi} required')
    return float(value)


def block_parameters(widthEm=30, size=1, align='left'):
    """Validate operation/layout parameters using one common set of bounds."""
    width = _dimension(widthEm, 4, 120, 'widthEm')
    size = _dimension(size, 0.5, 4, 'size')
    if not isinstance(align, str) or align not in ('left', 'center', 'right'):
        raise ValueError('align: left, center or right required')
    return width, size, align


@lru_cache(maxsize=1)
def _profile():
    data = metrics()
    font = data['fonts'][FONT]
    version = sha256_of({'font': FONT, 'metrics': {'chars': {str(c): v for c, v in font['chars'].items()},
                                    'params': font['params']}, 'template': data['template'],
                         'profile': 'literal-glyphs/v1', 'wrap': 'greedy-hanging-space/v1', 'lineHeight': LINE_HEIGHT,
                         'graphemes': regex.__version__, 'unicode': unicodedata.unidata_version, 'characters': TEXT_CODES})
    ascent = max(c[1] for c in font['chars'].values()) / EM_PT
    descent = max(c[2] for c in font['chars'].values()) / EM_PT
    return font, version, ascent, descent


def _glyph(code, x, y, chars):
    info = chars.get(code)
    if info is None:
        raise ValueError(f'content: unsupported glyph {code} in {FONT}')
    ink = [info[4] / EM_PT + x, -info[7] / EM_PT + y,
           info[6] / EM_PT + x, -info[5] / EM_PT + y] if len(info) == 8 else None
    return {'code': code, 'x': x, 'y': y, 'ink': ink}


def _glyph_chars(text):
    # NFC selects glyphs only; the artifact preserves the input spelling.
    for ch in unicodedata.normalize('NFC', text):
        yield from (ch if ch in TEXT_CODES or 0x21 <= ord(ch) <= 0x7e
                    else unicodedata.normalize('NFD', ch))


def check_render_budget(doc, block_ops):
    """Bound aggregate block work before constructing a scene or opening output."""
    if len(block_ops) > MAX_SCENE_BLOCKS:
        raise ValueError(f'text.block: scene render limit is {MAX_SCENE_BLOCKS} blocks')
    codepoints = glyphs = 0
    outline_points = 0
    for op_id in sorted(block_ops):
        content = doc.operations[op_id]['args']['content']['value']
        plain = text_block_plain_text(content)
        codepoints += len(plain)
        if codepoints > MAX_SCENE_CODEPOINTS:
            raise ValueError(f'text.block: scene render limit is {MAX_SCENE_CODEPOINTS} Unicode code points')
        for match in _GRAPHEMES.finditer(plain):
            raw = match.group()
            if raw not in (' ', '\u00a0', '\n'):
                for char in _glyph_chars(raw):
                    glyphs += 1
                    outline_points += ACCENT_OUTLINE_POINTS if char in _ACCENTS else BASE_OUTLINE_POINTS
                if glyphs > MAX_SCENE_GLYPHS:
                    raise ValueError(f'text.block: scene render limit is {MAX_SCENE_GLYPHS} glyphs')
                if outline_points > MAX_SCENE_OUTLINE_POINTS:
                    raise ValueError(f'text.block: scene render limit is {MAX_SCENE_OUTLINE_POINTS} outline points')


def _cluster(text, font):
    chars = font['chars']
    if text in (' ', '\u00a0'):
        return font['params'][1] / EM_PT, []
    glyphs, width = [], 0.0
    base_x = base_width = base_height = 0.0
    for ch in _glyph_chars(text):
        if ch in _ACCENTS:
            code = _ACCENTS[ch]
            accent = chars[code]
            x = base_x + (base_width - accent[0] / EM_PT) / 2
            y = -(base_height - font['params'][4] / EM_PT)
            glyphs.append(_glyph(code, x, y, chars))
            continue
        code = TEXT_CODES.get(ch, ord(ch) if 0x21 <= ord(ch) <= 0x7e else None)
        if code is None or code not in chars:
            raise ValueError(f'content: unsupported glyph U+{ord(ch):04X} in {FONT}')
        info = chars[code]
        base_x, base_width, base_height = width, info[0] / EM_PT, info[1] / EM_PT
        glyphs.append(_glyph(code, width, 0.0, chars))
        width += base_width
    return width, glyphs


def _wrap(text, width, font):
    """Bounded linear greedy wrapping; words are measured only once."""
    clusters = []
    for match in _GRAPHEMES.finditer(text):
        raw = match.group()
        advance, glyphs = _cluster(raw, font)
        if advance > width + 1e-9:
            raise ValueError('widthEm: a single grapheme exceeds block width')
        clusters.append((raw, advance, glyphs))
    if not clusters:
        return [[]]
    lines, current, used = [], [], 0.0
    # Split before each word; spaces remain literal and may themselves wrap.
    index = 0
    while index < len(clusters):
        end = index + 1
        whitespace = clusters[index][0] == ' '
        while end < len(clusters) and (clusters[end][0] == ' ') == whitespace:
            end += 1
        token = clusters[index:end]
        token_width = sum(c[1] for c in token)
        if not whitespace and current and used + token_width > width + 1e-9:
            lines.append(current)
            current, used = [], 0.0
        if whitespace:
            # A separator belongs to its preceding line, even when its blank
            # advance hangs past the edge. It must never create a new row.
            current.extend(token)
            used += token_width
            index = end
            continue
        for cluster in token:
            if current and used + cluster[1] > width + 1e-9:
                lines.append(current)
                current, used = [], 0.0
            current.append(cluster)
            used += cluster[1]
        index = end
    if current:
        lines.append(current)
    return lines


def block_font_size(value):
    return _dimension(value, 0.01, 10000, 'text_style.font_size_px')


def layout_text_block(content, widthEm=30, size=1, align='left', *, text_style=None):
    """Return canonical positioned lines/glyphs; see ``docs/native/ops/text.block.md``."""
    content = validate_text_block(content)
    width, size, align = block_parameters(widthEm, size, align)
    style = {} if text_style is None else text_style
    if not isinstance(style, dict) or set(style) - {'font_size_px'}:
        raise ValueError('text_style: only font_size_px is supported')
    font_size = block_font_size(style.get('font_size_px', 16))
    font, version, ascent, descent = _profile()
    lines = []
    for hard_line in text_block_plain_text(content).split('\n'):
        for clusters in _wrap(hard_line, width, font):
            advance = min(width, sum(c[1] for c in clusters))
            x = (width - advance) * {'left': 0, 'center': 0.5, 'right': 1}[align]
            baseline = ascent + LINE_HEIGHT * len(lines)
            glyphs, offset = [], 0.0
            for _raw, step, group in clusters:
                for glyph in group:
                    g = dict(glyph, x=glyph['x'] + offset)
                    if g['ink'] is not None:
                        a, b, c, d = g['ink']
                        g['ink'] = [a + offset, b, c + offset, d]
                    glyphs.append(g)
                offset += step
            lines.append({'text': ''.join(c[0] for c in clusters), 'x': x,
                          'baseline': baseline, 'width': advance, 'glyphs': glyphs})
    result = {'format': 'animageo-text-block-layout/v1', 'lines': lines, 'width': width,
              'height': ascent + descent + LINE_HEIGHT * (len(lines) - 1),
              'metricsVersion': version, 'size': size, 'fontSizePx': font_size}
    result['hash'] = sha256_of(result)
    return result


def drawing_glyphs(line):
    """Yield unique positioned outlines. Identical overprinted accents draw once."""
    seen = set()
    for glyph in line['glyphs']:
        key = glyph['code'], glyph['x'], glyph['y']
        if glyph['ink'] is not None and key not in seen:
            seen.add(key)
            yield glyph


def line_tex(line):
    """A zero-width line at 1 TeX point per em, with explicit glyph positions."""
    # A kern separates every pair of glyphs, preventing TeX ligatures. Using
    # relative kerns instead of an rlap box per glyph keeps the page node list
    # inside pdfTeX's default memory even with 60,000 visible glyphs.
    chars = _profile()[0]['chars']
    glyphs = []
    cursor = 0
    for glyph in drawing_glyphs(line):
        x = round(glyph['x'] * 65536)
        code = glyph['code']
        literal = rf'\char{code}\relax'
        dy = round(-glyph['y'] * 65536)
        if dy:
            literal = rf'\raise{dy}sp\hbox{{{literal}}}'
        glyphs.append(rf'\kern{x - cursor}sp{literal}')
        cursor = x + int(chars[code][0] / EM_PT * 65536)
    glyphs.append(rf'\kern{-cursor}sp')
    return rf'{{\font\tbfont={FONT} at 1pt\tbfont\hbox{{' + '%\n'.join(glyphs) + '}}'


def layout_ink(layout):
    """Union of positioned glyph ink boxes in layout coordinates, or None."""
    boxes = [[g['ink'][0] + l['x'], g['ink'][1] + l['baseline'],
              g['ink'][2] + l['x'], g['ink'][3] + l['baseline']]
             for l in layout['lines'] for g in l['glyphs'] if g['ink'] is not None]
    if not boxes:
        return None
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]
