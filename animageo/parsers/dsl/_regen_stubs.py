"""Generate the DSL stubs from the factories the namespace discovers.

The factories of the DSL are the commands of ``COMMAND_REGISTRY``
(:data:`animageo.parsers.dsl.namespace._DISCOVERED_COMMANDS`). Two stub files
follow them:

- ``parsers/dsl/namespace.pyi`` — typed signatures written by hand, plus a
  generated block (between the ``BEGIN``/``END GENERATED FACTORIES`` markers)
  with a plain signature for every factory that has no typed one. A typed
  signature of a factory that is gone is removed.
- ``animageo/dsl.pyi`` — generated as a whole: explicit re-exports of the
  proxy types, of every factory and of the helpers ``namespace.pyi``
  declares.

Usage::

    python -m animageo.parsers.dsl._regen_stubs            # show what differs
    python -m animageo.parsers.dsl._regen_stubs --write    # rewrite both files
    python -m animageo.parsers.dsl._regen_stubs --check    # exit 1 if stale (CI)

Run ``--write`` after adding a command to ``geo/lib_commands.py`` (and give
the new factory a typed signature by hand when it has a clear result type).
"""

from __future__ import annotations

import argparse
import ast
import difflib
import sys
from pathlib import Path

DSL_DIR = Path(__file__).resolve().parent
NAMESPACE_PYI = DSL_DIR / 'namespace.pyi'
DSL_PYI = DSL_DIR.parents[1] / 'dsl.pyi'

BEGIN = '# BEGIN GENERATED FACTORIES'
END = '# END GENERATED FACTORIES'
GENERATED_SIGNATURE = 'def {name}(*args: Any, name: Optional[str] = ...) -> ElementProxy: ...'

# Declarations of namespace.pyi that are no DSL vocabulary (``dsl.pyi`` skips them).
UTILITY = frozenset({'FactoryDict', 'build_namespace', 'SAFE_BUILTINS'})


def discovered() -> frozenset[str]:
    """The factories of the DSL: CamelCase names of ``COMMAND_REGISTRY``."""
    from .namespace import _DISCOVERED_COMMANDS
    return frozenset(_DISCOVERED_COMMANDS)


def _is_factory_name(name: str) -> bool:
    return name[:1].isupper() and name not in UTILITY


class Declarations:
    """What a ``namespace.pyi`` text declares at its top level."""

    def __init__(self, text: str):
        tree = ast.parse(text)
        self.proxy_types: list[str] = []      # re-exported from ``.proxy``
        self.functions: dict[str, ast.AST] = {}
        self.variables: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == 'proxy' and node.level == 1:
                self.proxy_types.extend(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                self.variables.append(node.target.id)

    @property
    def factory_functions(self) -> set[str]:
        """CamelCase functions — each one must be a factory."""
        return {n for n in self.functions if _is_factory_name(n)}

    @property
    def factories(self) -> set[str]:
        """Names a factory may be declared by: the CamelCase functions and the
        proxy types (``Point`` is a type and a factory; ``Measure`` only a type)."""
        return self.factory_functions | set(self.proxy_types)

    @property
    def helpers(self) -> list[str]:
        """Lowercase functions and annotated names (``style``, ``sqrt``, ``pi``…)."""
        names = [n for n in self.functions if not n[:1].isupper() and not n.startswith('_')]
        names += self.variables
        return sorted(n for n in set(names) if n not in UTILITY)


def _split_generated(text: str) -> tuple[str, str]:
    """``(before BEGIN incl., after END incl.)``; the markers must be there."""
    try:
        head, rest = text.split(BEGIN + '\n', 1)
        _, tail = rest.split(END + '\n', 1)
    except ValueError:
        raise SystemExit(f'{NAMESPACE_PYI}: the markers {BEGIN!r} / {END!r} are missing') from None
    return head + BEGIN + '\n', END + '\n' + tail


def _drop_lines(text: str, nodes: list[ast.AST]) -> str:
    lines = text.splitlines(keepends=True)
    drop = set()
    for node in nodes:
        first = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
        drop.update(range(first - 1, node.end_lineno))
    return ''.join(line for i, line in enumerate(lines) if i not in drop)


def namespace_pyi(current: str, factories: frozenset[str]) -> tuple[str, list[str]]:
    """The expected ``namespace.pyi`` and the stale factories it drops."""
    head, tail = _split_generated(current)
    hand = Declarations(head + tail)
    stale = sorted(hand.factory_functions - factories)
    if stale:
        # the markers are comments, so dropping the stale defs keeps them
        head, tail = _split_generated(_drop_lines(head + tail, [hand.functions[n] for n in stale]))
        hand = Declarations(head + tail)
    missing = sorted(factories - hand.factories)
    block = ''.join(GENERATED_SIGNATURE.format(name=n) + '\n' for n in missing)
    return head + block + tail, stale


DSL_HEADER = '''"""Type stubs for the ``animageo.dsl`` super-module.

Generated by ``python -m animageo.parsers.dsl._regen_stubs --write`` from
``parsers/dsl/namespace.pyi`` — do not edit. Explicit re-exports (no
``from X import *``) so Pylance/mypy can resolve every name reliably.
"""
'''


def _block(comment: str, module: str, names) -> str:
    rows = ''.join(f'    {n} as {n},\n' for n in names)
    return f'\n# {comment}\nfrom {module} import (\n{rows})\n'


def dsl_pyi(namespace_text: str) -> str:
    """The expected ``dsl.pyi`` for a ``namespace.pyi`` text."""
    decl = Declarations(namespace_text)
    proxies = sorted(set(decl.proxy_types))
    factories = sorted(decl.factory_functions - set(proxies))
    return (DSL_HEADER
            + _block('Proxy types — the ``A: Point`` declarations; the constructible ones are factories too.',
                     '.parsers.dsl.proxy', proxies)
            + _block('Command factories (one per command of ``COMMAND_REGISTRY``).',
                     '.parsers.dsl.namespace', factories)
            + _block('Helpers and math.', '.parsers.dsl.namespace', decl.helpers)
            + '\n# StyleProxy for ``A.style.stroke = ...`` patterns.\n'
            + 'from .style.proxy import StyleProxy as StyleProxy\n')


def expected() -> dict[Path, tuple[str, str]]:
    """``{path: (current text, expected text)}`` and prints nothing."""
    factories = discovered()
    current_ns = NAMESPACE_PYI.read_text(encoding='utf-8')
    new_ns, _ = namespace_pyi(current_ns, factories)
    current_dsl = DSL_PYI.read_text(encoding='utf-8') if DSL_PYI.exists() else ''
    return {NAMESPACE_PYI: (current_ns, new_ns), DSL_PYI: (current_dsl, dsl_pyi(new_ns))}


def problems() -> list[str]:
    """What is stale: the factories each file misses or has in excess."""
    out = []
    factories = discovered()
    ns = Declarations(NAMESPACE_PYI.read_text(encoding='utf-8'))
    for name in sorted(factories - ns.factories):
        out.append(f'namespace.pyi: no stub for the factory {name}')
    for name in sorted(ns.factory_functions - factories):
        out.append(f'namespace.pyi: stub of {name}, which is no factory')
    for path, (current, new) in expected().items():
        if current != new:
            out.append(f'{path.relative_to(DSL_DIR.parents[2])}: differs from the generated stubs')
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--write', action='store_true', help='rewrite namespace.pyi and dsl.pyi')
    group.add_argument('--check', action='store_true', help='exit 1 when the stubs are stale')
    args = parser.parse_args(argv)
    files = expected()
    if args.write:
        for path, (current, new) in files.items():
            if current != new:
                path.write_text(new, encoding='utf-8')
                print(f'wrote {path}')
        return 0
    found = problems()
    for line in found:
        print(line)
    if not args.check:
        for path, (current, new) in files.items():
            sys.stdout.writelines(difflib.unified_diff(
                current.splitlines(keepends=True), new.splitlines(keepends=True),
                fromfile=f'{path.name} (now)', tofile=f'{path.name} (generated)'))
    print(f'{len(discovered())} factories; ' + ('stubs up to date' if not found else f'{len(found)} problems'))
    return 1 if found else 0


if __name__ == '__main__':
    raise SystemExit(main())
