"""Issues of «Команды»: :class:`CommandIssue` and the codes (commands.md §7)."""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ['CommandIssue', 'LineError', 'ERROR_CODES', 'WARNING_CODES', 'ambiguous_name']

# A line with an error is not applied; a warning does not stop anything.
ERROR_CODES = (
    'unknown_command',
    'unknown_name',
    'arity',
    'type_mismatch',
    'ambiguous_pair',
    'name_taken',
    'invalid_name',
    'forbidden',
    'syntax',
)
WARNING_CODES = (
    'comment_dropped',
    'ambiguous_name',
    'unprintable_pair',
    'unprintable_params',
    'unprintable_operation',
)


@dataclass(frozen=True)
class CommandIssue:
    """One problem of a line. ``line`` and ``column`` count from 1; the column
    is in code points of the text as typed (before the input replacements).
    ``severity`` is ``"error"`` or ``"warning"``; ``hint`` is a suggestion
    (a free name, the right command, ``не A``) or ``None``.

    Edit-mode refusals of :func:`animageo.native.redefine` keep their own
    codes (``type_mismatch``, ``cycle``, ``slot_conflict``, ``missing_input``…).
    """

    code: str
    line: int
    column: int
    message: str
    severity: str = 'error'
    hint: str | None = None

    def to_dict(self) -> dict:
        out = {'code': self.code, 'line': self.line, 'column': self.column,
               'message': self.message, 'severity': self.severity}
        if self.hint is not None:
            out['hint'] = self.hint
        return out


class LineError(Exception):
    """Raised inside the parser and the builder; becomes a :class:`CommandIssue`."""

    def __init__(self, code: str, column: int, message: str, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.column = column
        self.message = message
        self.hint = hint

    def issue(self, line: int) -> CommandIssue:
        return CommandIssue(self.code, line, self.column, self.message, 'error', self.hint)


def ambiguous_name(name: str, readings, line: int, column: int) -> CommandIssue:
    """The warning ``ambiguous_name`` (commands.md §3): the name of an
    element also reads as two point names; ``readings`` — from
    :func:`animageo.native.commands.naming.pair_readings`."""
    head, tail = readings[0]
    return CommandIssue('ambiguous_name', line, column,
                        f'{name} читается и как пара точек {head}, {tail}; '
                        f'в аргументах {name} означает этот объект, а не пару', 'warning')
