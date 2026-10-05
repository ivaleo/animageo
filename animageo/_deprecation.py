"""Deprecations of animageo (1.11.0rc1).

A public name or form that is going away is deprecated first: it keeps
working and warns with ``DeprecationWarning``, saying since when, what to
use instead and the version that removes it. Removal is not before 2.0:
``remove_in`` defaults to ``"2.0"`` and may not be lower.

Every deprecation is a row of :data:`DEPRECATIONS` and of
``docs/native/deprecations.md`` (a test keeps them equal):

- a function or a class: ``@deprecated(since="1.11", alternative="native.load")``;
- a form of input (a JSON version, an argument value): :func:`register` once
  at import, :func:`warn` where the form is met.

This module imports nothing heavy; ``animageo.native`` may use it.
"""
from __future__ import annotations

import functools
import inspect
import warnings
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

_T = TypeVar('_T')

FIRST_REMOVAL = '2.0'


@dataclass(frozen=True)
class Deprecation:
    """One deprecated name or form."""

    name: str
    since: str
    remove_in: str = FIRST_REMOVAL
    alternative: Optional[str] = None
    detail: Optional[str] = None  # the message when there is more to say than the name

    def message(self) -> str:
        head = self.detail or f'{self.name} is deprecated'
        tail = f'Deprecated since {self.since}; removed in {self.remove_in}.'
        if self.alternative and not self.detail:
            tail += f' Use {self.alternative} instead.'
        head = head.rstrip()
        return f"{head}{'' if head.endswith('.') else '.'} {tail}"


DEPRECATIONS: dict[str, Deprecation] = {}


def _major(version: str) -> int:
    try:
        return int(str(version).split('.', 1)[0])
    except ValueError:
        raise ValueError(f'not a version: {version!r}') from None


def register(name: str, since: str, remove_in: str = FIRST_REMOVAL, alternative: Optional[str] = None,
             detail: Optional[str] = None) -> Deprecation:
    """Record a deprecation; the same row twice is fine, a different one is an error."""
    if _major(remove_in) < _major(FIRST_REMOVAL):
        raise ValueError(f'{name}: removal not before {FIRST_REMOVAL} (remove_in={remove_in!r})')
    _major(since)
    row = Deprecation(name, since, remove_in, alternative, detail)
    known = DEPRECATIONS.setdefault(name, row)
    if known != row:
        raise ValueError(f'{name}: deprecated twice differently ({known} / {row})')
    return row


def warn(name: str, *, stacklevel: int = 2) -> None:
    """Warn about the registered deprecation ``name``; ``stacklevel`` as for
    :func:`warnings.warn` from the caller's frame."""
    warnings.warn(DEPRECATIONS[name].message(), DeprecationWarning, stacklevel=stacklevel + 1)


def deprecated(since: str, remove_in: str = FIRST_REMOVAL, alternative: Optional[str] = None,
               *, name: Optional[str] = None) -> Callable[[_T], _T]:
    """Decorator: calling the function (or instantiating the class) warns.

    ``name`` defaults to ``module.qualname`` of the decorated object; the
    object gets ``__deprecated__`` (the message, as PEP 702 does).
    """
    if _major(remove_in) < _major(FIRST_REMOVAL):
        raise ValueError(f'removal not before {FIRST_REMOVAL} (remove_in={remove_in!r})')

    def decorate(obj):
        row = register(name or f'{obj.__module__}.{obj.__qualname__}', since, remove_in, alternative)
        message = row.message()
        if inspect.isclass(obj):
            init = obj.__init__

            @functools.wraps(init)
            def __init__(self, *args, **kwargs):
                warnings.warn(message, DeprecationWarning, stacklevel=2)
                init(self, *args, **kwargs)

            obj.__init__ = __init__
            obj.__deprecated__ = message
            return obj

        @functools.wraps(obj)
        def wrapper(*args, **kwargs):
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return obj(*args, **kwargs)

        wrapper.__deprecated__ = message
        return wrapper

    return decorate


# Forms deprecated before this module existed.
register(
    'keyframes JSON v1', since='1.6.0', alternative='"version": 2',
    detail=("keyframes JSON without '\"version\": 2' uses the deprecated v1 "
            "schema. Add '\"version\": 2' to opt into the v2 schema "
            "(per-keyframe 'styles'; future v2 visibility/timing semantics)."),
)
