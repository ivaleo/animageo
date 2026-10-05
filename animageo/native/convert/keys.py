"""Keys and IDs of the translator (plan L5 §3.3).

``id = uuid5(namespace, key)``; the caller gives ``namespace``
(``id_namespace``, decision 6). Keys:

- an object of a ``.ggb`` — ``ggb:<label>`` (labels are unique in a file);
- a DSL variable — ``dsl:<name>``;
- a phantom ``_N`` — ``anon:<classic key>(<input keys joined by ,>)#<output number>``,
  a repeat of the same record ``~2``, ``~3`` in order: the key follows the
  inputs, not the counter, so a line inserted above renumbers nothing;
- an operation — ``op:`` + the key of its first output; an element — ``el:`` + key.

``documentId`` is ``uuid5(namespace, "document")``; the web replaces it with
its own (decision 7).
"""
from __future__ import annotations

import uuid

__all__ = ['KeyMaker', 'element_id', 'operation_id', 'document_id', 'make_id', 'namespace_of']


def make_id(namespace: uuid.UUID, key: str) -> str:
    return str(uuid.uuid5(namespace, key))


def element_id(namespace: uuid.UUID, key: str) -> str:
    return make_id(namespace, 'el:' + key)


def operation_id(namespace: uuid.UUID, key: str) -> str:
    return make_id(namespace, 'op:' + key)


def document_id(namespace: uuid.UUID) -> str:
    return make_id(namespace, 'document')


def namespace_of(value) -> uuid.UUID:
    """``id_namespace`` as a UUID (a ``uuid.UUID`` or its string)."""
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        return uuid.UUID(value)
    raise TypeError('id_namespace must be a uuid.UUID or its string')


class KeyMaker:
    """Keys of the classic names of one construction.

    ``prefix`` is ``ggb`` or ``dsl``; ``display`` maps a classic (normalized)
    name to the label or variable name shown to the user; a name starting
    with ``_`` followed by digits is a phantom and gets a structural key from
    :meth:`phantom`.
    """

    def __init__(self, prefix: str, display: dict | None = None):
        self.prefix = prefix
        self.display = dict(display or {})
        self.keys: dict = {}
        self._seen: dict = {}

    @staticmethod
    def is_phantom(name: str) -> bool:
        return isinstance(name, str) and name.startswith('_') and name[1:].isdigit()

    def named(self, name: str) -> str:
        key = self.keys.get(name)
        if key is None:
            key = f'{self.prefix}:{self.display.get(name, name)}'
            self.keys[name] = key
        return key

    def phantom(self, name: str, classic_key: str, input_keys, output_number: int) -> str:
        if name in self.keys:
            return self.keys[name]
        base = f'anon:{classic_key}({",".join(input_keys)})#{output_number}'
        count = self._seen.get(base, 0) + 1
        self._seen[base] = count
        key = base if count == 1 else f'{base}~{count}'
        self.keys[name] = key
        return key

    def key_of(self, name: str) -> str | None:
        return self.keys.get(name)
