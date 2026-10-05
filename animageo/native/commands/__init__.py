"""«Команды»: the text form of a construction document (commands.md).

::

    from animageo.native import commands

    result = commands.parse_commands("A = (0, 0)\\nB = (4, 0)\\nM = Середина(A, B)")
    result.document, result.effects, result.lines, result.issues
    commands.print_commands(result.document).text      # the same three lines
    commands.parse_commands(edited_text, base=result.document)   # edit mode

Pure Python: no module here imports manim or the classic package.
"""
from __future__ import annotations

from .build import ParseResult, is_helper, pair_op, parse_commands, time_ordered_id
from .issues import ERROR_CODES, WARNING_CODES, CommandIssue
from .lexicon import LEXICON_FORMAT, Lexicon, LexiconError, default_lexicon, lexicon_hash, lexicon_problems
from .naming import next_name, polygon_side_names
from .numbers import format_number
from .printer import PrintResult, print_commands

__all__ = [
    'CommandIssue',
    'ERROR_CODES',
    'LEXICON_FORMAT',
    'Lexicon',
    'LexiconError',
    'ParseResult',
    'PrintResult',
    'WARNING_CODES',
    'default_lexicon',
    'format_number',
    'is_helper',
    'lexicon_hash',
    'lexicon_problems',
    'next_name',
    'pair_op',
    'parse_commands',
    'polygon_side_names',
    'print_commands',
    'time_ordered_id',
]
