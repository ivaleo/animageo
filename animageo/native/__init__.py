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
    native.project(doc, "P", (x, y))         # path parameter of the nearest point of P's path
    native.dumps(doc), native.content_hash(doc)
    native.closure(doc, ["A"])               # dependents in topological order
    doc2, effects = native.delete(doc, ["A"])  # pure edits: delete, redefine, rename
    native.render(doc, fmt="svg", out="a.svg")  # needs manim: RenderResult(path, fmt, report)
    native.layout_labels(doc)                # {id: {anchor, box, offsetWorld, …}} without manim
    native.parse_commands(text)              # «Команды» → ParseResult(document, effects, lines, issues)
    native.print_commands(doc).text          # document → «Команды» (docs/native/commands.md)
    native.steps(doc), native.describe(doc)  # steps and their text (docs/native/steps.md)
    native.has("locus")                      # features by stage (native.FEATURES)

No module of this package imports manim, ``animageo.animageo`` or
``animageo.geo`` at import time; the bridge (``kernel/bridge.py``),
:func:`render` and :func:`layout_labels` load the classic code inside their
functions (:func:`layout_labels` never manim with ``backend="metrics"``).
"""
from __future__ import annotations

from .canonical import canonical_json
from .document import (
    DOCUMENT_FORMAT,
    Issue,
    LoadError,
    NativeDocument,
    content_hash,
    dump,
    dumps,
    load,
    validate,
)
from .kernel.checks import CheckReport, run_checks
from .kernel.relations import check_document as _check_document
from .document import as_document, bound_producer
from .edit import (
    EditError,
    EditResult,
    closure,
    delete,
    dependencies,
    free_inputs,
    redefine,
    rename,
)
from .kernel import paths as _paths
from .kernel.evaluate import EVALUATED_FORMAT, Evaluated, producer_values
from .kernel.evaluate import evaluate as _evaluate
from .registry import REGISTRY_VERSION, Registry, registry, signature_hash
from .labels import layout_labels
from .commands import parse_commands, print_commands
from .rendering import RenderResult, render, source_view
from .steps import Step, StepError, assign_seq, steps, steps_merge, steps_split
from .describe import describe
from .conditions import measure_statement, relation, statement_checks, statement_problems
from .sampling import check_general
from .conditions.apply import (ConditionResult, Refusal, apply_condition, condition_candidates, release_condition,
                               shape_conditions)

# Features of this library by stage of plan L3 (``has``): the web asks for a
# feature instead of comparing versions.
FEATURES = ('triangle', 'locus', 'steps', 'describe', 'render.eps', 'render.tikz', 'roles',
            'check.general', 'conditions', 'apply_condition')


def has(feature: str) -> bool:
    """Whether this library has ``feature`` (one of :data:`FEATURES`; stage 1 of L3:
    ``triangle``, ``locus``, ``steps``, ``describe``, ``render.eps``,
    ``render.tikz``, ``roles``)."""
    return feature in FEATURES

__registry_version__ = REGISTRY_VERSION

__all__ = [
    'DOCUMENT_FORMAT',
    'EVALUATED_FORMAT',
    'CheckReport',
    'EditError',
    'EditResult',
    'Evaluated',
    'FEATURES',
    'Issue',
    'LoadError',
    'NativeDocument',
    'Registry',
    'RenderResult',
    '__registry_version__',
    'canonical_json',
    'check',
    'closure',
    'content_hash',
    'delete',
    'dependencies',
    'dump',
    'dumps',
    'evaluate',
    'free_inputs',
    'layout_labels',
    'load',
    'parse_commands',
    'print_commands',
    'project',
    'redefine',
    'registry',
    'rename',
    'render',
    'run_checks',
    'signature_hash',
    'source_view',
    'Step',
    'StepError',
    'assign_seq',
    'describe',
    'has',
    'check_general',
    'ConditionResult',
    'Refusal',
    'apply_condition',
    'condition_candidates',
    'release_condition',
    'shape_conditions',
    'measure_statement',
    'relation',
    'statement_checks',
    'statement_problems',
    'steps',
    'steps_merge',
    'steps_split',
    'validate',
]


def evaluate(doc, *, inputs=None) -> Evaluated:
    """Values, states and reasons of every element of ``doc``.

    ``doc`` is a :class:`NativeDocument` or anything :func:`load` reads;
    ``inputs`` (``{elementId: {"kind": "point", "value": [x, y]}}`` or
    ``{"kind": "pathParameter", "value": t}``) overrides the document's input
    values of free elements.
    """
    return _evaluate(doc, inputs=inputs)


def check(doc, checks=None, *, inputs=None, relations=None, trials=0, seed=None) -> CheckReport:
    """Mandatory checks of every operation whose outputs are defined, and
    relations between elements.

    ``checks`` limits the op checks to ``"<operationId>:<checkId>"`` keys or
    bare check IDs. ``relations`` — ``[{"id", "predicate", "args":
    [elementId…]}]`` with the predicates ``incident``, ``parallel``,
    ``perpendicular``, ``equal_length``, ``equal_angle``, ``collinear``,
    ``concyclic``, ``concurrent``, ``tangent``; their keys are
    ``"relation:<id>"``. Each result is ``passed``, ``failed``,
    ``inconclusive`` or (a relation only) ``unsupported``; ``details`` says
    why. ``trials = N > 0`` runs ``general_position``: every check must also
    hold with the free inputs perturbed ``N`` times, the trials seeded by
    ``sha256(documentId or str(seed), check id)`` (``docs/native/checks.md``).
    """
    return _check_document(doc, checks, inputs=inputs, relations=relations, trials=trials, seed=seed)


def project(doc, element_id: str, xy, *, inputs=None) -> float | None:
    """The path parameter of the point of a path nearest to ``xy``.

    ``element_id`` is a path element (segment, ray, line, circle, polygon) or
    a ``point.on_path`` point (then its path). The parameter is in the frame
    ``point.on_path`` uses (``docs/native/ops/point.on_path.md``), so
    ``{"kind": "pathParameter", "value": project(…)}`` puts the point there.
    ``None`` when the path is not defined; ``ValueError`` when the element is
    not a path.
    """
    doc = as_document(doc)
    if element_id not in doc.elements:
        raise ValueError(f'unknown element {element_id!r}')
    path_id = element_id
    producer = bound_producer(doc, element_id)
    if producer is not None and doc.operations[producer]['op'] == 'point.on_path':
        arg = doc.operations[producer]['args'].get('path') or {}
        path_id = arg.get('elementId') if arg.get('kind') == 'ref' else None
        if path_id not in doc.elements:
            return None
    type_ = doc.elements[path_id]['type']
    if type_ not in registry().paths:
        raise ValueError(f'element {path_id!r} is a {type_}, not a path')
    x, y = (float(v) for v in xy)
    ev = _evaluate(doc, inputs=inputs)
    states = ev.elements
    if states[path_id]['state'] != 'defined':
        return None
    producer_op, values = producer_values(path_id, doc.elements, doc.operations, states)
    frame = _paths.frame(type_, states[path_id]['value'], producer_op, values)
    return _paths.project(frame, x, y, ev.tolerances.decide_length)
