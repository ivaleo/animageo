"""``animageo.native`` — the construction document and the reference kernel.

A manim-free module: it reads ``animageo-construction/v1`` documents, checks
them against the semantic operation registry (``ops/v1``) and evaluates
values, states and reasons by element ID. The browser kernel of the web app
repeats the same contract; parity fixtures (``parity/v1``) keep the two in
step. See ``docs/native/kernel.md`` and ``docs/native/ops/``.

    from animageo import native

    doc = native.load("scene.json")          # NativeDocument (LoadError on a broken structure)
    native.validate(doc)                     # [Issue]: schema, references, slot types, cycles
    ev = native.evaluate(doc)                # Evaluated; ev.to_dict() is animageo-evaluated/v1
    native.check(doc).results                # {"<operationId>:<checkId>": "passed" | …}
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
from .kernel.checks import CheckReport, run_checks
from .kernel.evaluate import EVALUATED_FORMAT, Evaluated
from .kernel.evaluate import evaluate as _evaluate
from .registry import REGISTRY_VERSION, Registry, registry, signature_hash

__registry_version__ = REGISTRY_VERSION

__all__ = [
    'DOCUMENT_FORMAT',
    'EVALUATED_FORMAT',
    'CheckReport',
    'Evaluated',
    'Issue',
    'LoadError',
    'NativeDocument',
    'Registry',
    '__registry_version__',
    'canonical_json',
    'check',
    'closure',
    'content_hash',
    'dump',
    'dumps',
    'evaluate',
    'load',
    'registry',
    'run_checks',
    'signature_hash',
    'validate',
]


def evaluate(doc, *, inputs=None) -> Evaluated:
    """Values, states and reasons of every element of ``doc``.

    ``doc`` is a :class:`NativeDocument` or anything :func:`load` reads;
    ``inputs`` (``{elementId: {"kind": "point", "value": [x, y]}}``) overrides
    the document's input values of free elements.
    """
    return _evaluate(doc, inputs=inputs)


def check(doc, checks=None, *, inputs=None) -> CheckReport:
    """Mandatory checks of every operation whose outputs are defined.

    ``checks`` limits the report to ``"<operationId>:<checkId>"`` keys or bare
    check IDs. Each result is ``passed``, ``failed`` or ``inconclusive``.
    """
    return run_checks(_evaluate(doc, inputs=inputs), checks)
