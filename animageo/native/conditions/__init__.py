"""Conditions of a construction (plan L3 stage 2, docs/native/conditions.md):
statements, their checks in the general case, recipes, automatic marks."""
from .statements import (KINDS, mark_statement, mark_statements, measure_statement, relation, statement_checks,
                         statement_elements, statement_problems)

__all__ = ['KINDS', 'mark_statement', 'mark_statements', 'measure_statement', 'relation', 'statement_checks',
           'statement_elements', 'statement_problems']
