"""Label TeX set without TeX: the ``metrics`` measurer of ``native.layout_labels``.

A label of the classic renderer is ``Tex(correctedLabel(text),
tex_template=RusTex)`` measured by manim: the bounding box of the points of
its glyph outlines. This module sets the same TeX with the metrics of the
template's fonts (``metrics.v1.json``, built by
``scripts/native/build_label_metrics.py``) and returns that box. It covers
the subset labels use:

- text mode: the T2A text font (Latin, digits, Cyrillic, punctuation),
  ligatures and kerns of its TFM, interword spaces, ``~``, ``\\,``, ``\\%``…;
- math mode (``$…$``, text style): letters (math italic with the italic
  correction), digits, operators and relations with TeX's spacing table
  (``\\medmuskip = \\thickmuskip = 4mu`` of the template), Greek, the symbols of
  ``cmsy``/``msam``/``msbm``, groups, sub- and superscripts by the rules of
  Appendix G of the TeXbook (18a–f) in script and scriptscript sizes, primes,
  ``\\text``, ``\\mbox``, ``\\mathrm``, explicit math spaces, and composite
  symbols measured whole (``\\angle``, ``\\triangle``, ``\\neq``, …).

Anything else (``\\frac``, ``\\sqrt``, accents, unknown commands, characters
without a glyph) raises :class:`Unsupported`; the caller then estimates the
size the way the classic renderer does when LaTeX fails.

Units: TeX points while setting; :func:`measure` returns manim units at a
manim ``font_size``.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

__all__ = ['Unsupported', 'ink_box', 'measure', 'metrics']

METRICS_PATH = Path(__file__).with_name('metrics.v1.json')

_lock = threading.Lock()
_metrics = None


class Unsupported(ValueError):
    """The label uses TeX outside the subset of this module."""


def metrics() -> dict:
    """The parsed ``metrics.v1.json`` (loaded once)."""
    global _metrics
    if _metrics is None:
        with _lock:
            if _metrics is None:
                with open(METRICS_PATH, encoding='utf-8') as fh:
                    raw = json.load(fh)
                fonts = {}
                for name, f in raw['fonts'].items():
                    fonts[name] = {
                        'params': f['params'],
                        'chars': {int(c): v for c, v in f.get('chars', {}).items()},
                        'ligkern': {int(c): p for c, p in f.get('ligkern', {}).items()},
                    }
                raw['fonts'] = fonts
                _metrics = raw
    return _metrics


# ── fonts and math characters ───────────────────────────────────────────

SIZE_INDEX = {0: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 2, 7: 2}   # style → text/script/scriptscript
FAMILIES = {
    'mi': ('cmmi10', 'cmmi7', 'cmmi5'),
    'rm': ('cmr10', 'cmr7', 'cmr5'),
    'sy': ('cmsy10', 'cmsy7', 'cmsy5'),
    'am': ('msam10', 'msam7', 'msam5'),
    'bm': ('msbm10', 'msbm7', 'msbm5'),
    'tx': ('larm1000', 'larm0700', 'larm0500'),
}
TEXT_STYLE, SCRIPT_STYLE = 2, 4
ORD, OP, BIN, REL, OPEN, CLOSE, PUNCT, INNER = range(8)
CLASSES = {'ord': ORD, 'op': OP, 'bin': BIN, 'rel': REL, 'open': OPEN, 'close': CLOSE,
           'punct': PUNCT, 'inner': INNER}
# TeX's math_spacing (rows: left class, columns: right class)
SPACING = ('02340001', '22*40001', '33**3**3', '44*04004',
           '00*00000', '02340001', '11*11111', '12341011')
THIN_MU, MED_MU, THICK_MU = 3.0, 4.0, 4.0    # RusTex: \medmuskip 4mu, \thickmuskip 4mu

MATH_CHARS = {}
for _c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ':
    MATH_CHARS[_c] = (ORD, 'mi', ord(_c), True)        # True: a letter (\mathrm switches it)
for _c in '0123456789':
    MATH_CHARS[_c] = (ORD, 'rm', ord(_c), False)
MATH_CHARS.update({
    '+': (BIN, 'rm', 0x2B, False), '=': (REL, 'rm', 0x3D, False),
    '(': (OPEN, 'rm', 0x28, False), ')': (CLOSE, 'rm', 0x29, False),
    '[': (OPEN, 'rm', 0x5B, False), ']': (CLOSE, 'rm', 0x5D, False),
    ':': (REL, 'rm', 0x3A, False), ';': (PUNCT, 'rm', 0x3B, False),
    '!': (CLOSE, 'rm', 0x21, False), '?': (CLOSE, 'rm', 0x3F, False),
    '-': (BIN, 'sy', 0x00, False), '*': (BIN, 'sy', 0x03, False), '|': (ORD, 'sy', 0x6A, False),
    '/': (ORD, 'mi', 0x3D, False), '.': (ORD, 'mi', 0x3A, False), ',': (PUNCT, 'mi', 0x3B, False),
    '<': (REL, 'mi', 0x3C, False), '>': (REL, 'mi', 0x3E, False),
})

_GREEK = ('alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi rho '
          'sigma tau upsilon phi chi psi omega varepsilon vartheta varpi varrho varsigma varphi')
MATH_SYMBOLS = {name: (ORD, 'mi', 0x0B + i) for i, name in enumerate(_GREEK.split())}
MATH_SYMBOLS.update({name: (ORD, 'rm', i) for i, name in enumerate(
    'Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega'.split())})
MATH_SYMBOLS.update({
    'partial': (ORD, 'mi', 0x40), 'ell': (ORD, 'mi', 0x60), 'ldotp': (PUNCT, 'mi', 0x3A),
    'colon': (PUNCT, 'rm', 0x3A), '%': (ORD, 'rm', 0x25), '&': (ORD, 'rm', 0x26),
    '#': (ORD, 'rm', 0x23),
    'circ': (BIN, 'sy', 0x0E), 'cdot': (BIN, 'sy', 0x01), 'times': (BIN, 'sy', 0x02),
    'ast': (BIN, 'sy', 0x03), 'div': (BIN, 'sy', 0x04), 'pm': (BIN, 'sy', 0x06),
    'mp': (BIN, 'sy', 0x07), 'bullet': (BIN, 'sy', 0x0F), 'cap': (BIN, 'sy', 0x5C),
    'cup': (BIN, 'sy', 0x5B), 'wedge': (BIN, 'sy', 0x5E), 'land': (BIN, 'sy', 0x5E),
    'vee': (BIN, 'sy', 0x5F), 'lor': (BIN, 'sy', 0x5F), 'setminus': (BIN, 'sy', 0x6E),
    'perp': (REL, 'sy', 0x3F), 'parallel': (REL, 'sy', 0x6B), 'mid': (REL, 'sy', 0x6A),
    'in': (REL, 'sy', 0x32), 'ni': (REL, 'sy', 0x33), 'subset': (REL, 'sy', 0x1A),
    'supset': (REL, 'sy', 0x1B), 'subseteq': (REL, 'sy', 0x12), 'supseteq': (REL, 'sy', 0x13),
    'sim': (REL, 'sy', 0x18), 'approx': (REL, 'sy', 0x19), 'simeq': (REL, 'sy', 0x27),
    'equiv': (REL, 'sy', 0x11), 'le': (REL, 'sy', 0x14), 'leq': (REL, 'sy', 0x14),
    'ge': (REL, 'sy', 0x15), 'geq': (REL, 'sy', 0x15), 'll': (REL, 'sy', 0x1C),
    'gg': (REL, 'sy', 0x1D), 'to': (REL, 'sy', 0x21), 'rightarrow': (REL, 'sy', 0x21),
    'gets': (REL, 'sy', 0x20), 'leftarrow': (REL, 'sy', 0x20),
    'leftrightarrow': (REL, 'sy', 0x24), 'Rightarrow': (REL, 'sy', 0x29),
    'Leftarrow': (REL, 'sy', 0x28), 'Leftrightarrow': (REL, 'sy', 0x2C),
    'propto': (REL, 'sy', 0x2F), 'not': (REL, 'sy', 0x36),
    'infty': (ORD, 'sy', 0x31), 'forall': (ORD, 'sy', 0x38), 'exists': (ORD, 'sy', 0x39),
    'neg': (ORD, 'sy', 0x3A), 'lnot': (ORD, 'sy', 0x3A), 'emptyset': (ORD, 'sy', 0x3B),
    'nabla': (ORD, 'sy', 0x72), 'prime': (ORD, 'sy', 0x30), 'backslash': (ORD, 'sy', 0x6E),
    'vert': (ORD, 'sy', 0x6A), 'Vert': (ORD, 'sy', 0x6B), '|': (ORD, 'sy', 0x6B),
    '{': (OPEN, 'sy', 0x66), 'lbrace': (OPEN, 'sy', 0x66),
    '}': (CLOSE, 'sy', 0x67), 'rbrace': (CLOSE, 'sy', 0x67),
    'langle': (OPEN, 'sy', 0x68), 'rangle': (CLOSE, 'sy', 0x69),
    'leqslant': (REL, 'am', 0x36), 'geqslant': (REL, 'am', 0x3E),
    'square': (ORD, 'am', 0x03), 'measuredangle': (ORD, 'am', 0x5D),
    'sphericalangle': (ORD, 'am', 0x5E), 'therefore': (REL, 'am', 0x29),
    'because': (REL, 'am', 0x2A),
    'varnothing': (ORD, 'bm', 0x3F), 'nparallel': (REL, 'bm', 0x2C), 'nmid': (REL, 'bm', 0x2D),
})
# Math spaces in mu (negative: \!) and in em of the text font ('em', n).
MATH_SPACES = {',': THIN_MU, ':': MED_MU, '>': MED_MU, ';': THICK_MU, '!': -THIN_MU,
               'thinspace': THIN_MU, 'medspace': MED_MU, 'thickspace': THICK_MU,
               'negthinspace': -THIN_MU,
               'quad': ('em', 1.0), 'qquad': ('em', 2.0), ' ': ('space', 1.0)}

# Text mode: T2A codes of characters that are not ASCII.
TEXT_CODES = {ch: 0xC0 + i for i, ch in enumerate('АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ')}
TEXT_CODES.update({ch: 0xE0 + i for i, ch in enumerate('абвгдежзийклмнопрстуфхцчшщъыьэюя')})
TEXT_CODES.update({'Ё': 0x9C, 'ё': 0xBC, '«': 0xBE, '»': 0xBF, '–': 0x15, '—': 0x16, '№': 0x9D})
TEXT_ASCII = frozenset(chr(c) for c in range(0x21, 0x7F)) - set('\\{}$&#^_%~"')
TEXT_SYMBOLS = {'%': 0x25, '&': 0x26, '#': 0x23, '$': 0x24, '_': 0x5F, '{': 0x7B, '}': 0x7D}
TEXT_SPACES = {',': ('em', 1 / 6), ' ': ('space', 1.0), 'quad': ('em', 1.0),
               'qquad': ('em', 2.0), 'enspace': ('em', 0.5)}


# ── boxes ───────────────────────────────────────────────────────────────

class Box:
    """A box: ``width``, ``height``, ``depth`` (points) and the ink rectangles
    ``(x0, y0, x1, y1)`` of its glyphs in box coordinates (origin at the
    reference point, y up). ``char`` marks a box that is one character
    (possibly with its italic correction), for rule 18a."""

    __slots__ = ('width', 'height', 'depth', 'inks', 'char')

    def __init__(self, width=0.0, height=0.0, depth=0.0, inks=(), char=False):
        self.width = width
        self.height = height
        self.depth = depth
        self.inks = list(inks)
        self.char = char


def hpack(items) -> Box:
    """Pack ``[(Box | float, shift)]`` side by side; a float is glue or kern;
    ``shift`` raises the box."""
    x = h = d = 0.0
    inks = []
    for item, shift in items:
        if isinstance(item, Box):
            for x0, y0, x1, y1 in item.inks:
                inks.append((x + x0, y0 + shift, x + x1, y1 + shift))
            h = max(h, item.height + shift)
            d = max(d, item.depth - shift)
            x += item.width
        else:
            x += item
    return Box(x, h, d, inks)


def char_box(font: str, code: int) -> Box:
    f = metrics()['fonts'][font]
    info = f['chars'].get(code)
    if info is None:
        raise Unsupported(f'no character {code} in {font}')
    w, h, d = info[0], info[1], info[2]
    return Box(w, h, d, [tuple(info[4:8])] if len(info) == 8 else [], char=True)


def italic(font: str, code: int) -> float:
    return metrics()['fonts'][font]['chars'][code][3]


def param(font: str, n: int) -> float:
    p = metrics()['fonts'][font]['params']
    return p[n - 1] if n <= len(p) else 0.0


def lig_kern(font: str, left: int, right: int):
    """``("k", kern)``, ``("l", op, char)`` or ``None`` for the pair."""
    for nxt, kind, value in metrics()['fonts'][font]['ligkern'].get(left, ()):
        if nxt == right:
            if kind == 'k':
                return ('k', value)
            return ('l', int(kind[1:]), int(value))
    return None


# ── tokens ──────────────────────────────────────────────────────────────

def tokenize(src: str) -> list:
    """TeX tokens: ``("cs", name)``, ``("ch", c)``, ``("sp", " ")``; a ``%``
    comments out the rest of its line."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == '\\':
            j = i + 1
            if j < n and src[j].isascii() and src[j].isalpha():
                while j < n and src[j].isascii() and src[j].isalpha():
                    j += 1
                out.append(('cs', src[i + 1:j]))
                while j < n and src[j] in ' \t\n':       # spaces after a control word
                    j += 1
                i = j
                continue
            if j >= n:
                raise Unsupported('a lone backslash')
            out.append(('cs', src[j]))
            i = j + 1
            continue
        if c == '%':
            while i < n and src[i] != '\n':
                i += 1
            continue
        if c in ' \t\n':
            while i < n and src[i] in ' \t\n':
                i += 1
            out.append(('sp', ' '))
            continue
        out.append(('ch', c))
        i += 1
    return out


class _Stream:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self):
        tok = self.peek()
        if tok is None:
            raise Unsupported('unexpected end of label')
        self.i += 1
        return tok

    def group(self):
        """The tokens of a ``{…}`` group (the opening brace already read)."""
        depth, out = 1, []
        while True:
            tok = self.next()
            if tok == ('ch', '{'):
                depth += 1
            elif tok == ('ch', '}'):
                depth -= 1
                if depth == 0:
                    return out
            out.append(tok)

    def argument(self):
        """A macro argument: a braced group or one token (spaces skipped)."""
        tok = self.next()
        while tok[0] == 'sp':
            tok = self.next()
        if tok == ('ch', '{'):
            return self.group()
        if tok == ('ch', '}'):
            raise Unsupported('missing argument')
        return [tok]


# ── text mode ───────────────────────────────────────────────────────────

def text_box(tokens, size: int) -> Box:
    """Set text-mode tokens in the T2A font of ``size`` (0, 1, 2); math
    (``$…$``) inside is set in text style."""
    font = FAMILIES['tx'][size]
    items = []                 # (Box | float, 0.0)
    codes = []                 # pending characters of the current word

    def flush():
        if codes:
            items.extend(_set_word(font, codes))
            codes.clear()

    def space(kind, amount):
        flush()
        if kind == 'space':
            items.append((param(font, 2) * amount, 0.0))
        else:
            items.append((param(font, 6) * amount, 0.0))

    s = _Stream(tokens)
    while s.peek() is not None:
        kind, v = s.next()
        if kind == 'sp':
            space('space', 1.0)
        elif kind == 'ch' and v == '$':
            flush()
            math, closed = [], False
            while s.peek() is not None:
                tok = s.next()
                if tok == ('ch', '$'):
                    closed = True
                    break
                math.append(tok)
            if not closed:
                raise Unsupported('unbalanced $')
            items.append((math_box(math, TEXT_STYLE), 0.0))
        elif kind == 'ch' and v in '{}':
            continue
        elif kind == 'ch' and v == '~':
            space('space', 1.0)
        elif kind == 'ch':
            code = TEXT_CODES.get(v)
            if code is None:
                if v not in TEXT_ASCII:
                    raise Unsupported(f'character {v!r} in text')
                code = ord(v)
            codes.append(code)
        elif v in TEXT_SPACES:
            space(*TEXT_SPACES[v])
        elif v in TEXT_SYMBOLS:
            codes.append(TEXT_SYMBOLS[v])
        elif v in ('text', 'textrm', 'textup', 'textnormal', 'mbox'):
            flush()
            items.append((text_box(s.argument(), size), 0.0))
        elif v == '(':
            flush()
            math = []
            while True:
                tok = s.next()
                if tok == ('cs', ')'):
                    break
                math.append(tok)
            items.append((math_box(math, TEXT_STYLE), 0.0))
        else:
            raise Unsupported(f'\\{v} in text')
    flush()
    return hpack(items)


def _set_word(font: str, codes: list) -> list:
    """Characters of one word with the ligatures and kerns of the font."""
    codes = list(codes)
    out = []
    i = 0
    while i < len(codes):
        c = codes[i]
        if i + 1 < len(codes):
            lk = lig_kern(font, c, codes[i + 1])
            if lk is not None and lk[0] == 'l':
                op, lig = lk[1], lk[2]
                if op == 0:                    # =: — both become the ligature
                    codes[i:i + 2] = [lig]
                    continue
                if op in (1, 5):               # =:| — the left one becomes it
                    codes[i] = lig
                    continue
                if op in (2, 6):               # |=: — the right one becomes it
                    codes[i + 1] = lig
                    continue
                codes.insert(i + 1, lig)       # |=:| — inserted between
                continue
        out.append((char_box(font, c), 0.0))
        if i + 1 < len(codes):
            lk = lig_kern(font, c, codes[i + 1])
            if lk is not None and lk[0] == 'k':
                out.append((lk[1], 0.0))
        i += 1
    return out


# ── math mode ───────────────────────────────────────────────────────────

class Noad:
    """A math atom: class, nucleus and scripts. ``nucleus`` is ``None``
    (empty), ``("char", fam, code)``, ``("list", [items])`` or ``("box", style → Box)``."""

    __slots__ = ('cls', 'nucleus', 'sup', 'sub')

    def __init__(self, cls, nucleus):
        self.cls = cls
        self.nucleus = nucleus
        self.sup = None
        self.sub = None


class Space:
    """Explicit space in a math list: mu, or ``(unit, amount)`` of the text font."""

    __slots__ = ('amount',)

    def __init__(self, amount):
        self.amount = amount


def parse_math(tokens, letters_fam='mi') -> list:
    """Tokens of a formula → a math list of :class:`Noad` and :class:`Space`."""
    s = _Stream(tokens)
    items = []

    def last_noad(create=True):
        if items and isinstance(items[-1], Noad):
            return items[-1]
        if not create:
            return None
        n = Noad(ORD, None)
        items.append(n)
        return n

    def script_list(arg):
        return parse_math(arg, letters_fam)

    while s.peek() is not None:
        kind, v = s.next()
        if kind == 'sp':
            continue
        if kind == 'ch' and v in '^_':
            n = last_noad()
            slot = 'sup' if v == '^' else 'sub'
            if getattr(n, slot) is not None:
                raise Unsupported('double script')
            setattr(n, slot, script_list(s.argument()))
            continue
        if kind == 'ch' and v == "'":
            n = last_noad()
            if n.sup is not None:
                raise Unsupported('double superscript')
            primes = [Noad(ORD, ('char', 'sy', 0x30))]
            while s.peek() == ('ch', "'"):
                s.next()
                primes.append(Noad(ORD, ('char', 'sy', 0x30)))
            if s.peek() == ('ch', '^'):
                s.next()
                primes.extend(script_list(s.argument()))
            n.sup = primes
            continue
        if kind == 'ch' and v == '{':
            items.append(_group_noad(parse_math(s.group(), letters_fam)))
            continue
        if kind == 'ch' and v == '}':
            raise Unsupported('unbalanced }')
        if kind == 'ch':
            spec = MATH_CHARS.get(v)
            if spec is None:
                raise Unsupported(f'character {v!r} in math')
            cls, fam, code, letter = spec
            if letter:
                fam = letters_fam
            items.append(Noad(cls, ('char', fam, code)))
            continue
        # control sequences
        if v in MATH_SPACES:
            items.append(Space(MATH_SPACES[v]))
        elif v in MATH_SYMBOLS:
            cls, fam, code = MATH_SYMBOLS[v]
            items.append(Noad(cls, ('char', fam, code)))
        elif '\\' + v in metrics()['macros']:
            macro = metrics()['macros']['\\' + v]
            items.append(Noad(CLASSES[macro['class']], ('box', _macro_box(macro))))
        elif v == 'mathrm':
            items.append(_group_noad(parse_math(s.argument(), 'rm')))
        elif v in ('text', 'textrm', 'textup', 'textnormal'):
            arg = s.argument()
            items.append(Noad(ORD, ('box', lambda style, arg=arg: text_box(arg, SIZE_INDEX[style]))))
        elif v == 'mbox':
            arg = s.argument()
            items.append(Noad(ORD, ('box', lambda style, arg=arg: text_box(arg, 0))))
        elif v in ('mathord', 'mathbin', 'mathrel', 'mathopen', 'mathclose', 'mathpunct',
                   'mathinner', 'mathop'):
            inner = _group_noad(parse_math(s.argument(), letters_fam))
            n = Noad(CLASSES[v[4:]] if v != 'mathop' else OP, inner.nucleus)
            if v == 'mathop':
                raise Unsupported('\\mathop')
            items.append(n)
        else:
            raise Unsupported(f'\\{v} in math')
    return items


def _group_noad(items) -> Noad:
    """``{…}`` in math: an ord atom; a lone ord character without scripts
    stands for itself (TeX §1186)."""
    if (len(items) == 1 and isinstance(items[0], Noad) and items[0].cls == ORD
            and items[0].sup is None and items[0].sub is None):
        return Noad(ORD, items[0].nucleus)
    return Noad(ORD, ('list', items))


def _macro_box(macro):
    def build(style):
        dims = macro[('T', 'S', 'SS')[SIZE_INDEX[style]]]
        inks = [tuple(dims[3:7])] if len(dims) == 7 else []
        return Box(dims[0], dims[1], dims[2], inks)
    return build


def _sy(style: int) -> str:
    return FAMILIES['sy'][SIZE_INDEX[style]]


def _mu(style: int) -> float:
    return param(_sy(style), 6) / 18.0


def math_box(tokens, style: int) -> Box:
    return hpack(mlist_to_hlist(parse_math(tokens), style))


def clean_box(items, style: int) -> Box:
    """TeX's clean_box for a script list (§720–721 of tex.web): the list
    packed. A lone character's italic correction stays in the width — TeX
    removes the kern node only after ``hpack`` has measured it."""
    hl = mlist_to_hlist(items, style)
    if len(hl) == 1 and isinstance(hl[0][0], Box) and hl[0][1] == 0.0:
        b = hl[0][0]
        return Box(b.width, b.height, b.depth, b.inks)
    return hpack(hl)


def mlist_to_hlist(items, style: int) -> list:
    """Appendix G of the TeXbook for this subset: ``[(Box | float, shift)]``."""
    # bin → ord where a binary operator cannot be one (rules 5 and 6)
    r_type, r = OP, None
    for q in items:
        if not isinstance(q, Noad):
            continue
        if q.cls == BIN and r_type in (BIN, OP, REL, OPEN, PUNCT):
            q.cls = ORD
        if q.cls in (REL, CLOSE, PUNCT) and r_type == BIN:
            r.cls = ORD
        r_type, r = q.cls, q
    if r_type == BIN:
        r.cls = ORD

    size = SIZE_INDEX[style]
    translated = []            # (noad | Space, [(item, shift)])
    for idx, q in enumerate(items):
        if isinstance(q, Space):
            translated.append((q, [(_space_width(q.amount, style), 0.0)]))
            continue
        nucleus_items, delta, is_char = _nucleus(q, items, idx, style, size)
        if q.sup is not None or q.sub is not None:
            nucleus_items = nucleus_items + _make_scripts(q, nucleus_items, delta, is_char, style)
        translated.append((q, nucleus_items))

    out = []
    r_type = None
    for q, hl in translated:
        if isinstance(q, Noad):
            if r_type is not None:
                code = SPACING[r_type][q.cls]
                gap = 0.0
                if code == '2' or (code == '1' and style < SCRIPT_STYLE):
                    gap = THIN_MU
                elif code == '3' and style < SCRIPT_STYLE:
                    gap = MED_MU
                elif code == '4' and style < SCRIPT_STYLE:
                    gap = THICK_MU
                if gap:
                    out.append((gap * _mu(style), 0.0))
            r_type = q.cls
        out.extend(hl)
    return out


def _space_width(amount, style: int) -> float:
    if isinstance(amount, tuple):
        unit, n = amount
        font = FAMILIES['tx'][0]
        return n * (param(font, 2) if unit == 'space' else param(font, 6))
    return amount * _mu(style)


def _nucleus(q: Noad, items, idx: int, style: int, size: int):
    """``(hlist items, delta, is_char)`` of the nucleus (rules 14–17)."""
    nuc = q.nucleus
    if nuc is None:
        return [], 0.0, False
    if nuc[0] == 'box':
        return [(nuc[1](style), 0.0)], 0.0, False
    if nuc[0] == 'list':
        return [(hpack(mlist_to_hlist(nuc[1], style)), 0.0)], 0.0, False
    _kind, fam, code = nuc
    font = FAMILIES[fam][size]
    box = char_box(font, code)
    out = [(box, 0.0)]
    delta = italic(font, code)
    text_char = False
    if q.cls == ORD and q.sup is None and q.sub is None:
        nxt = items[idx + 1] if idx + 1 < len(items) else None
        if (isinstance(nxt, Noad) and nxt.nucleus is not None and nxt.nucleus[0] == 'char'
                and nxt.nucleus[1] == fam):
            text_char = True
            lk = lig_kern(font, code, nxt.nucleus[2])
            if lk is not None and lk[0] == 'k':
                kern = lk[1]
                if text_char and param(font, 2) != 0:
                    delta = 0.0
                if delta:
                    out.append((delta, 0.0))
                out.append((kern, 0.0))
                return out, 0.0, True
    if text_char and param(font, 2) != 0:
        delta = 0.0
    if q.sub is None and delta:
        out.append((delta, 0.0))
        delta = 0.0
    return out, delta, True


def _make_scripts(q: Noad, nucleus_items, delta: float, is_char: bool, style: int) -> list:
    """Rules 18a–f: the script boxes after the nucleus."""
    size = SIZE_INDEX[style]
    sy = FAMILIES['sy'][size]
    t = FAMILIES['sy'][1 if style < SCRIPT_STYLE else 2]
    if is_char:
        shift_up = shift_down = 0.0
    else:
        z = hpack(nucleus_items)
        shift_up = z.height - param(t, 18)
        shift_down = z.depth + param(t, 19)
    x_height = abs(param(sy, 5))
    script_space = metrics()['scriptSpace']
    sup_style = 2 * (style // 4) + 4 + (style % 2)
    sub_style = 2 * (style // 4) + 5
    if q.sup is None:                                  # 18b
        x = clean_box(q.sub, sub_style)
        x.width += script_space
        shift_down = max(shift_down, param(sy, 16), x.height - x_height * 4 / 5)
        return [(x, -shift_down)]
    x = clean_box(q.sup, sup_style)                    # 18c
    x.width += script_space
    if style % 2:
        clr = param(sy, 15)
    elif style < TEXT_STYLE:
        clr = param(sy, 13)
    else:
        clr = param(sy, 14)
    shift_up = max(shift_up, clr, x.depth + x_height / 4)
    if q.sub is None:                                  # 18d
        return [(x, shift_up)]
    y = clean_box(q.sub, sub_style)                    # 18e
    y.width += script_space
    shift_down = max(shift_down, param(sy, 17))
    theta = param('cmex10', 8)
    clr = 4 * theta - ((shift_up - x.depth) - (y.height - shift_down))
    if clr > 0:
        shift_down += clr
        clr = x_height * 4 / 5 - (shift_up - x.depth)  # 18f
        if clr > 0:
            shift_up += clr
            shift_down -= clr
    inks = [(x0 + delta, y0 + shift_up, x1 + delta, y1 + shift_up) for x0, y0, x1, y1 in x.inks]
    inks += [(x0, y0 - shift_down, x1, y1 - shift_down) for x0, y0, x1, y1 in y.inks]
    both = Box(max(x.width + delta, y.width), x.height + shift_up, y.depth + shift_down, inks)
    return [(both, 0.0)]


# ── entry points ────────────────────────────────────────────────────────

def ink_box(tex: str):
    """``(x0, y0, x1, y1)`` in points of the ink of ``tex`` (a corrected
    label string) set at 10 pt, or ``None`` when it has no ink."""
    box = text_box(tokenize(tex), 0)
    if not box.inks:
        return None
    return (min(b[0] for b in box.inks), min(b[1] for b in box.inks),
            max(b[2] for b in box.inks), max(b[3] for b in box.inks))


def measure(tex: str, font_size: float) -> tuple:
    """``(width, height)`` in manim units of ``Tex(tex)`` at manim
    ``font_size`` — ``tex`` already through ``correctedLabel``.
    :class:`Unsupported` outside the subset."""
    ink = ink_box(tex)
    if ink is None:
        return (0.0, 0.0)
    k = metrics()['muPerPtPerFontSize'] * float(font_size)
    return ((ink[2] - ink[0]) * k, (ink[3] - ink[1]) * k)
