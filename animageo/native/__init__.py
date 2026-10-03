"""``animageo.native`` — the construction document and the reference kernel.

A manim-free module: it reads ``animageo-construction/v1`` documents and
checks them against the semantic operation registry (``ops/v1``). See
``docs/native/kernel.md``.

    from animageo import native

    doc = native.load("scene.json")          # NativeDocument (LoadError on a broken structure)
    native.validate(doc)                     # [Issue]: schema, references, slot types, cycles
    native.dumps(doc), native.content_hash(doc)

No module of this package imports manim, ``animageo.animageo`` or
``animageo.geo``.
"""
from __future__ import annotations

from .canonical import canonical_json
from .document import (
    DOCUMENT_FORMAT,
    Issue,
    LoadError,
    NativeDocument,
    closure,
    content_hash,
    dump,
    dumps,
    load,
    validate,
)
from .registry import REGISTRY_VERSION, Registry, registry, signature_hash

__registry_version__ = REGISTRY_VERSION

__all__ = [
    'DOCUMENT_FORMAT',
    'Issue',
    'LoadError',
    'NativeDocument',
    'Registry',
    '__registry_version__',
    'canonical_json',
    'closure',
    'content_hash',
    'dump',
    'dumps',
    'load',
    'registry',
    'signature_hash',
    'validate',
]
