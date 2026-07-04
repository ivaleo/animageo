"""Re-generate ``namespace.pyi`` from the currently discovered commands.

Run this after adding a new command to ``geo/lib_commands.py`` so
that ``from animageo.dsl import *`` exposes the new factory name to
IDEs.

Usage::

    python3 -m animageo.parsers.dsl._regen_stubs

Prints a diff of commands currently in lib_commands vs those declared
in ``namespace.pyi``. Does not modify the file automatically — edit
``namespace.pyi`` by hand if the diff isn't empty.
"""

from __future__ import annotations

import re
from pathlib import Path

from .namespace import _DISCOVERED_COMMANDS


def _declared_in_pyi() -> set[str]:
    """Return the set of factory names explicitly declared in namespace.pyi."""
    pyi = Path(__file__).parent / "namespace.pyi"
    if not pyi.exists():
        return set()
    # Match ``def Name(...)`` declarations at column 0 with a CamelCase
    # identifier. This is a heuristic — not a full Python parser.
    pattern = re.compile(r'^def\s+([A-Z][A-Za-z0-9_]*)\s*\(', re.MULTILINE)
    return set(pattern.findall(pyi.read_text()))


def main() -> int:
    declared = _declared_in_pyi()
    discovered = set(_DISCOVERED_COMMANDS)

    missing = discovered - declared
    extra = declared - discovered

    print(f"Discovered commands: {len(discovered)}")
    print(f"Declared in pyi:     {len(declared)}")

    if missing:
        print("\nMISSING from pyi (IDE won't autocomplete):")
        for name in sorted(missing):
            print(f"  {name}")
        print(
            "\nAdd a declaration like::\n"
            "    def <Name>(*args: Any, name: Optional[str] = ...,\n"
            "               _outputs: int = ...) -> ElementProxy: ...\n"
        )

    if extra:
        print("\nDeclared but NOT in lib_commands (stale stub):")
        for name in sorted(extra):
            print(f"  {name}")

    if not missing and not extra:
        print("\nAll discovered commands have stubs.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
