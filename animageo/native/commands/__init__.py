"""«Команды»: the text form of a construction document (commands.md).

The lexicon ``animageo-lexicon/v1``, the lexer, the grammar subset, overload
resolution, default names and number printing.

Pure Python: no module here imports manim or the classic package.
"""
from __future__ import annotations

from .issues import ERROR_CODES, WARNING_CODES, CommandIssue
from .lexicon import LEXICON_FORMAT, Lexicon, LexiconError, default_lexicon, lexicon_hash, lexicon_problems
from .naming import next_name, polygon_side_names
from .numbers import format_number

__all__ = [
    'CommandIssue',
    'ERROR_CODES',
    'LEXICON_FORMAT',
    'Lexicon',
    'LexiconError',
    'WARNING_CODES',
    'default_lexicon',
    'format_number',
    'lexicon_hash',
    'lexicon_problems',
    'next_name',
    'polygon_side_names',
]
