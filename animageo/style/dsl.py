"""Mini-DSL for ImportPolicy values written in JSON style files.

JSON cannot express Python callables, so string directives are parsed
into callables at load time:

  "const:3"                    → fixed value 3
  "scale:1.5"                  → multiply raw GGB value by 1.5
  "quantize:[1,2,4]"           → snap raw value to nearest list entry
  "remap:{'#FF0000':'#C02121'}" → dict lookup (fallback to raw on miss)
  "match_element"              → copy stroke color to label (sentinel)
  "auto"                       → placement algorithm decides (sentinel)

Non-string values in policy JSON are kept as-is (scalars, lists, dicts,
bools). Callables must be assigned via Python API, not through JSON.
"""
import ast
import re

# Public sentinels — these strings are passed through unchanged so the
# resolver can branch on them without parsing.
SENTINEL_MATCH_ELEMENT = 'match_element'
SENTINEL_AUTO = 'auto'

_PREFIX_RE = re.compile(r'^(const|scale|quantize|remap):(.+)$')


def _parse_literal(s: str):
    """Parse a Python literal (int, float, list, dict, str) from a string."""
    return ast.literal_eval(s)


def parse_directive(value):
    """Convert a JSON policy value into a callable, scalar, or sentinel.

    - Non-string inputs are returned unchanged (scalars, lists, dicts, bools).
    - Strings starting with a known prefix are converted to a callable that
      takes (ggb_value, defaults, elem) and returns the resolved value.
    - Sentinel strings (``match_element``, ``auto``) are returned as-is so
      the resolver can dispatch on them.
    - Other strings are returned as-is (e.g. hex colors "#FFFFFF").

    Raises:
        ValueError: directive prefix is known but the body fails to parse.
    """
    if not isinstance(value, str):
        return value
    if value in (SENTINEL_MATCH_ELEMENT, SENTINEL_AUTO):
        return value

    m = _PREFIX_RE.match(value)
    if not m:
        return value  # bare string, pass through (e.g. "#000000")

    kind, body = m.group(1), m.group(2).strip()

    if kind == 'const':
        try:
            return _parse_literal(body)
        except (ValueError, SyntaxError) as e:
            raise ValueError(f"const: body must be a Python literal, got {body!r}") from e

    if kind == 'scale':
        try:
            factor = float(body)
        except ValueError as e:
            raise ValueError(f"scale: body must be a number, got {body!r}") from e
        return lambda ggb, *_: None if ggb is None else ggb * factor

    if kind == 'quantize':
        try:
            buckets = _parse_literal(body)
        except (ValueError, SyntaxError) as e:
            raise ValueError(f"quantize: body must be a list literal, got {body!r}") from e
        if not isinstance(buckets, (list, tuple)) or not buckets:
            raise ValueError(f"quantize: body must be a non-empty list, got {body!r}")
        sorted_buckets = sorted(buckets)

        def _quantize(ggb, *_):
            if ggb is None:
                return None
            return min(sorted_buckets, key=lambda b: abs(b - ggb))
        return _quantize

    if kind == 'remap':
        try:
            mapping = _parse_literal(body)
        except (ValueError, SyntaxError) as e:
            raise ValueError(f"remap: body must be a dict literal, got {body!r}") from e
        if not isinstance(mapping, dict):
            raise ValueError(f"remap: body must be a dict, got {body!r}")

        def _remap(ggb, *_):
            return mapping.get(ggb, ggb)
        return _remap

    # Unreachable: _PREFIX_RE guards the kinds.
    return value
