import logging
import itertools
import re
import numpy as np
from collections import deque

from .lib_vars import *
from .lib_elements import *
from .lib_commands import *
from .utils import is_number, is_angle_degrees, is_boolean, boolean

logger = logging.getLogger(__name__)

# Identifier pattern: pure name, no operators or whitespace.
# Anything else in a string input is treated as a literal (equations,
# DSL expressions) and passed through to the command unchanged.
_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# tparam_point constraint labels for non-degenerate conic types; degenerate
# conics keep 'unknown' (they are not sensible animation paths).
_CONIC_CONSTRAINTS = {
    ConicType.CIRCLE: 'circle',
    ConicType.ELLIPSE: 'ellipse',
    ConicType.HYPERBOLA: 'hyperbola',
    ConicType.PARABOLA: 'parabola',
}

"""Construction state management: elements, variables, commands, dependency tracking."""


class UnsupportedCommandError(RuntimeError):
    """Raised in strict mode when a command has no dispatch implementation."""

    def __init__(self, diagnostic):
        self.diagnostic = diagnostic
        super().__init__(
            "Unsupported command {command}({signature}) -> {outputs}: {reason}".format(
                command=diagnostic.get('command'),
                signature=', '.join(diagnostic.get('signature', [])),
                outputs=diagnostic.get('outputs', []),
                reason=diagnostic.get('reason'),
            )
        )

#--------------------------------------------------------------------------

def appendIfNew(elem, elemArray):
    for el in elemArray:
        if elem == el: return
    
    elemArray.append(elem)
    
def normalize_name(name):
    if not name:
        raise ValueError("Element name cannot be empty")
    # Заменяем HTML-сущности
    name = name.replace("&apos;", "_prime")
    # Заменяем нижние индексы в фигурных скобках
    name = re.sub(r'{(\w+)}', r'\1', name)
    # Заменяем любые другие недопустимые символы на подчеркивание
    name = re.sub(r'[\']', "_Prime", name)
    # GeoGebra permits labels that Python does not accept as identifiers
    # (for example ``K°``).  The parser executes normalized expressions as
    # Python DSL, so retain Unicode identifier characters and replace every
    # other character with an underscore.  Prefixing with ``A`` lets us test
    # continuation characters without rejecting digits or combining marks.
    name = ''.join(char if f'A{char}'.isidentifier() else '_' for char in name)
    # Убедимся, что имя не начинается с цифры
    if name[0].isdigit():
        name = 'var_' + name
    return name

def _seed_intrinsic_style(elem, data):
    """Give an element built late the defaults its data type carries.

    ``Element.__init__`` adopts ``data.style`` (z_index tier, label defaults)
    only when the element is created WITH data. One created undefined — GGB
    saved NaN coords for it — kept an empty style, so once a rebuild defined
    it, it rendered on the fill tier: a point under the segments through it.
    Missing keys only, so writes made meanwhile survive; set past the explicit
    tracking, so they stay intrinsic defaults exactly as in ``__init__``.
    """
    defaults = getattr(data, 'style', None)
    if not defaults:
        return
    for key, value in defaults.items():
        if key not in elem.style:
            dict.__setitem__(elem.style, key, value)


class Construction:
    """Manages geometric construction state: elements, variables, commands, and their dependencies.

    The construction maintains a dependency graph where each element has a level
    (0 = free input, N = depends on level N-1 elements). Commands are executed
    in dependency order. Supports incremental rebuild — only recomputes elements
    whose inputs have changed.

    Attributes:
        elements: List of Element objects (geometry: Points, Lines, Circles, etc.)
        vars: List of Var objects (numeric values: Measures, AngleSizes, Booleans)
        commands: List of Command objects defining how elements are computed
        state: Dict mapping element names to dependency info (level, inputs, outputs, built)
        name_mapping: Dict mapping GeoGebra names to normalized Python identifiers
        phantoms: Dict of temporary variables for complex subexpressions
    """

    def __init__(self):
        self.phantoms = {}
        self.vars = []
        self.elements = [
            Element("xAxis", Line((0, 1), 0), visible=False),
            # yAxis normal is (-1, 0) so its direction vector perp_rot(n) = (0, 1)
            # points +y, matching GeoGebra's yAxis orientation. This keeps the
            # Intersect(conic, yAxis, index) ordering aligned with GGB (index 1 =
            # lower y). Using (1, 0) flips the direction to (0, -1) and swaps the
            # intersection order (see intersect_Kl).
            Element("yAxis", Line((-1, 0), 0), visible=False)
        ]
        self.commands = []
        self.state = {}
        self.name_mapping = {}
        # Per-base-name counters used by the exec-DSL registrar
        # (dsl.registrar.__reg_loop__) to uniquify names inside loops /
        # defs as ``p, p_2, p_3, ...``. Persisted across ``dsl.run``
        # calls so repeated loops don't collide.
        self.naming_counters = {}
        self.command_diagnostics = []
        self._command_diagnostic_keys = set()
        self._unsupported_roots_by_output = {}
        self._unsupported_summary_logged = False
        self.strict_unsupported = False
        self.log_unsupported = True
        self._locus_sampling_suppressed_outputs = set()

    def __repr__(self):
        str_out = "--------------------------------\n[[construction]]:\n"

        str_out += "\n[{} phantoms]:".format(len(self.phantoms)) + '\n'
        for key in self.phantoms: str_out += str(key) + ': ' + str(self.phantoms[key]) + '\n'

        str_out += "\n[{} vars]:".format(len(self.vars)) + '\n'
        for var in self.vars: str_out += str(var) + '\n'
       
        str_out += "\n[{} elements]:".format(len(self.elements)) + '\n'
        for element in self.elements: str_out += str(element) + '\n'
        
        str_out += "\n[{} commands]:".format(len(self.commands)) + '\n'
        for command in self.commands: str_out += str(command) + '\n'

        str_out += "\n................................\n"
        str_out += "[[state]]:\n"

        state = []
        for name in self.state:
            level = self.state[name]['level']
            while level >= len(state): state.append([])
            state[level].append(name)

        for level in range(len(state)):
            str_out += f"\n[level {level}]:\n"
            for name in state[level]:
                str_out += name + ('' if self.state[name]['built'] else '*') + "\t"

        str_out += "\n--------------------------------\n"
        return str_out

    def new_repr(self):
        return "--------------------------------\n[[construction]]:\n" + \
            f"\n[{len(self.vars)} vars]:\n" + '\n'.join(map(str, self.vars)) + "\n" + \
                f"\n[{len(self.elements)} elements]:\n" + '\n'.join(map(str, self.elements)) + "\n" + \
                    f"\n[{len(self.commands)} commands]:\n" + '\n'.join(map(str, self.commands)) + "\n" + \
                        "--------------------------------\n"

    def add_new_phantom(self):
        num = 1
        while ('_' + str(num)) in self.phantoms: num += 1
        key = '_' + str(num)
        self.phantoms[key] = None
        return key

    def release_phantom(self, name):
        """Drop an unused phantom entry so the counter doesn't grow unbounded."""
        if name in self.phantoms:
            del self.phantoms[name]
    
    def get_normalized_name(self, name):
        normalized_name = normalize_name(name)
        self.name_mapping[name] = normalized_name
        return normalized_name

    def add(self, obj):
        if isinstance(obj, Var): 
            self.vars.append(obj)
            if obj.name not in self.state:
                self.state[obj.name] = { 'level': 0, 'inputs': [], 'outputs': [], 'input_commands': [], 'built': True }
        elif isinstance(obj, Element): 
            self.elements.append(obj)
            if obj.name not in self.state:
                self.state[obj.name] = { 'level': 0, 'inputs': [], 'outputs': [], 'input_commands': [], 'built': True }
        elif isinstance(obj, Command): 
            self.commands.append(obj)                    
            self.updateStateLevels(obj)

    def update(self, name, data, log = None):
        if isinstance(data, str):
            data_prepared = self.dataByStr(data)
            if data_prepared: data = data_prepared
        
        obj = self.objectByName(name)
        if obj is None:
            if name not in self.state:
                self.state[name] = { 'level': 0, 'inputs': [], 'outputs': [], 'input_commands': [], 'built': False }
            if isinstance(data, (Point, Line, Angle, Polygon, Circle, Vector, LocusCurve,
                                  Conic, Function, ImplicitCurve)):
                self.add(Element(name, data, visible = (name[0] != '_')))
                self.state[name]['built'] = True
                if log is not None: log[name] = True
            elif isinstance(data, (int, float, bool, Measure, AngleSize, Boolean)):
                self.add(Var(name, data))
                self.state[name]['built'] = True
                if log is not None: log[name] = True
            elif data is not None:
                logger.warning("Construction.update(%s): unsupported data type %s", name, type(data).__name__)
            else:
                self.add(Element(name, None, visible = (name[0] != '_')))
                self.state[name]['built'] = False
                if log is not None: log[name] = True
        else:
            if isinstance(obj, Var) or isinstance(obj, Element):
                for output in self.state[name]['outputs']:
                    self.state[output]['built'] = False
                # ?здесь нужно ли проверить, что объект не имеет предшедствующих зависимостей
                if not isinstance(obj.data, type(data)):
                    if isinstance(obj, Var):
                        if isinstance(obj.data, AngleSize) and isinstance(data, (int, float)):
                            data = AngleSize(data)
                        elif isinstance(obj.data, (int, float)) and isinstance(data, AngleSize):
                            data = data.value
                    elif data is not None and obj.data is not None:
                        logger.warning("Construction.update('%s'): incompatible types %s != %s", name, type(obj.data).__name__, type(data).__name__)
                if isinstance(obj, Element) and obj.data is None and data is not None:
                    _seed_intrinsic_style(obj, data)
                obj.data = data
                self.state[name]['built'] = True
                if log is not None: log[name] = True
            elif isinstance(obj, Command):
                logger.warning("Construction.update('%s'): command update not implemented", name)

    def rename(self, old_name, new_name):
        """Rename an element/var and all its references in commands + state.

        Used by the exec-DSL registrar to promote a phantom (``_3``) to
        the user's chosen name (``A``) without rebuilding. Idempotent
        when ``old_name == new_name``. Raises ``ValueError`` if
        ``new_name`` is already taken by a different object.
        """
        if old_name == new_name:
            return
        if self.objectByName(new_name) is not None:
            raise ValueError(
                f"rename: target name '{new_name}' already exists"
            )

        # Drop phantom bookkeeping — the name is a real binding now.
        if old_name in self.phantoms:
            del self.phantoms[old_name]

        # Rename on elements and vars (linear scan, same as element()).
        # When promoting a phantom (``_N``) to a real name, re-enable
        # visibility — the leading-underscore convention used by
        # :meth:`update` had defaulted it to False.
        was_phantom = old_name.startswith('_')
        is_phantom = new_name.startswith('_')
        for elem in self.elements:
            if elem.name == old_name:
                elem.name = new_name
                if was_phantom and not is_phantom:
                    elem.visible = True
        for var in self.vars:
            if var.name == old_name:
                var.name = new_name

        # Rewrite command inputs/outputs (stored as name strings).
        for cmd in self.commands:
            cmd.inputs = [new_name if x == old_name else x for x in cmd.inputs]
            cmd.outputs = [new_name if x == old_name else x for x in cmd.outputs]

        # Move state entry + rewrite cross-references.
        if old_name in self.state:
            self.state[new_name] = self.state.pop(old_name)
        for entry in self.state.values():
            entry['inputs'] = [new_name if x == old_name else x for x in entry['inputs']]
            entry['outputs'] = [new_name if x == old_name else x for x in entry['outputs']]

        # name_mapping: GGB-name → python-name indirection.
        for k, v in list(self.name_mapping.items()):
            if v == old_name:
                self.name_mapping[k] = new_name

        # Re-establish state cross-references for every command that uses
        # ``new_name``. A preceding ``_forget(new_name)`` (DSL overwrite
        # semantics) strips ``new_name`` from every state.inputs/outputs
        # list, but the commands themselves still reference the name —
        # so downstream elements would otherwise never mark themselves
        # dirty when the redefined element updates.
        for cmd in self.commands:
            if new_name in cmd.inputs or new_name in cmd.outputs:
                self.updateStateLevels(cmd)

    def add_and_build(self, cmd, debug=False):
        """Append a command and eagerly rebuild only the nodes it touches.

        Used by the exec-DSL factories so ``A.x`` reads made mid-exec
        see fresh values. The DSL emits commands in the order the user
        wrote them, which is already topological, so no re-sort is
        needed per call; a full ``sortCommands`` runs once at the end
        of :func:`animageo.parsers.dsl.run`.
        """
        self.add(cmd)
        self.rebuild(full=False, debug=debug)

    def _updateStateLevel(self, name, level):
        queue = deque()
        queue.append((name, level))
        
        while queue:
            current_name, current_level = queue.popleft()
            # Without a cycle no level exceeds the number of objects; with one
            # (a DSL line that redefines a name from itself, ``A =
            # Midpoint(A, B)``) the levels would grow forever.
            if current_level > len(self.state):
                raise ValueError(
                    f"dependency cycle through '{current_name}'")
            
            if self.state[current_name]['level'] < current_level:
                self.state[current_name]['level'] = current_level
                
                for output in self.state[current_name]['outputs']:
                    next_level = current_level + 1
                    if next_level > self.state[output]['level']:
                        queue.append((output, next_level))

    def sortCommands(self):
        """Sort commands in dependency order using Kahn's topological sort.

        Raises ValueError if a dependency cycle is detected.
        """
        n = len(self.commands)
        if n == 0:
            return

        # Build mapping: output_name -> command index
        producer = {}
        for idx, cmd in enumerate(self.commands):
            for output in cmd.outputs:
                producer[output] = idx

        # Build adjacency list and in-degree
        adj = [[] for _ in range(n)]
        in_degree = [0] * n

        for idx, cmd in enumerate(self.commands):
            deps_seen = set()
            for inp in cmd.inputs:
                inp_name = inp.name if hasattr(inp, 'name') else inp
                if isinstance(inp_name, str) and inp_name in producer:
                    dep_idx = producer[inp_name]
                    if dep_idx != idx and dep_idx not in deps_seen:
                        adj[dep_idx].append(idx)
                        in_degree[idx] += 1
                        deps_seen.add(dep_idx)

        # Kahn's algorithm
        queue = deque(i for i in range(n) if in_degree[i] == 0)
        sorted_indices = []

        while queue:
            i = queue.popleft()
            sorted_indices.append(i)
            for j in adj[i]:
                in_degree[j] -= 1
                if in_degree[j] == 0:
                    queue.append(j)

        if len(sorted_indices) != n:
            cycle_cmds = [str(self.commands[i]) for i in range(n) if in_degree[i] > 0]
            raise ValueError(f"Dependency cycle detected among commands: {cycle_cmds}")

        self.commands = [self.commands[i] for i in sorted_indices]

    def updateStateLevels(self, command):
        for output in command.outputs:
            if is_number(output): raise Exception(f'output could not be a number: {output}')
            if is_angle_degrees(output): raise Exception(f'output could not be an angle_size: {output}')    
            if output not in self.state:
                self.state[output] = { 'level': 0, 'inputs': [], 'outputs': [], 'input_commands': [], 'built': False }
            
            self.state[output]['built'] = False
            appendIfNew(command, self.state[output]['input_commands'])
            
            for input in command.inputs:
                if is_number(input): continue
                if is_angle_degrees(input): continue
                if input not in self.state:
                    self.state[input] = { 'level': 0, 'inputs': [], 'outputs': [], 'input_commands': [], 'built': False }

                appendIfNew(output, self.state[input]['outputs'])
                appendIfNew(input, self.state[output]['inputs'])
                
                self._updateStateLevel(output, max(self.state[output]['level'], self.state[input]['level'] + 1))


    def updateCommand(self, nameCommand, inputs, outputs = None):
        command = None if outputs is None else self.commandByElementName(outputs[0])
        if command is not None:
            command.name = nameCommand
            command.inputs = inputs
            command.outputs = outputs
            self.updateStateLevels(command)
        else:
            self.add(Command(nameCommand, inputs, outputs))

    def element(self, name: str): #) -> Element | None:
        result = list(filter(lambda elem: elem.name == name, self.elements))
        return result[0] if result else None

    def var(self, name: str): #) -> Var | None:
        result = list(filter(lambda var: var.name == name, self.vars))
        return result[0] if result else None

    def objectByName(self, name: str): #) -> Element | Var | None:
        for elem in self.elements:
            if elem.name == name: return elem
        for var in self.vars:
            if var.name == name: return var
        for key in self.phantoms:
            if key == name: return self.phantoms[key]   
        return None

    def commandByElementName(self, name: str): #) -> Command | None:
        result = list(filter(lambda comm: name in comm.outputs, self.commands))
        return result[0] if result else None

    def dataByStr(self, text):
        obj = self.objectByName(text)
        if obj is not None: return obj.data

        if is_number(text): return float(text)
        if is_angle_degrees(text): return AngleSizeFromStr(text)
        if is_boolean(text): return boolean(text)

        #raise Exception("Not found object(s) '{}' or not processing".format(text))
        return None

    def prepareInputs(self, command):
        for i in range(len(command.inputs)):
            value = command.inputs[i]
            if not isinstance(value, str):
                continue
            if self.objectByName(value) is not None:
                command.inputs[i] = self.dataByStr(value)
                continue
            if _IDENTIFIER_RE.match(value) or is_number(value) \
                    or is_angle_degrees(value) or is_boolean(value):
                command.inputs[i] = self.dataByStr(value)
            # Otherwise: literal string (DSL expression, equation, etc.)
            # — leave as-is so string-arg commands like function_T /
            # conic_T / implicit_curve_T receive the raw text.

    def update_tparam(self, name, tparam, log=None):
        """Update the curve/locus parameter (``tparam``) of a
        constrained point and mark dependents for rebuild.

        For a point constrained to a circle, ``tparam`` is the angle
        in radians; for a segment/line/ray it's the linear parameter
        along the direction.
        """
        elem = self.element(name)
        if elem is None:
            logger.warning("update_tparam('%s'): element not found", name)
            return
        elem.tparam = tparam
        self.state[name]['built'] = False
        for output in self.state[name]['outputs']:
            self.state[output]['built'] = False
        if log is not None:
            log[name] = True

    def tparam_from_coords(self, name, coords):
        """Coords → path parameter for a path-constrained (tparam) point.

        Public API for animation clients: given captured ``[x, y]``
        coordinates of point ``name`` (constrained to a circle/segment/
        ray/line/conic/locus/function), compute the tparam that places
        the point at (the projection of) those coordinates. Returns a
        float — or a ``(branch, t)`` tuple for a hyperbola — or ``None``
        (with a warning) when the element is not a tparam point or its
        path is not recognized.
        """
        from .tparam import tparam_from_point_and_path
        elem = self.element(name)
        if elem is None or elem.tparam is None:
            logger.warning("tparam_from_coords('%s'): not a tparam point", name)
            return None
        cmd = self.commandByElementName(name)
        if not cmd:
            logger.warning("tparam_from_coords('%s'): no defining command", name)
            return None
        pt = Point(coords)
        for inp_name in cmd.inputs:
            inp_obj = self.objectByName(inp_name) if isinstance(inp_name, str) else inp_name
            inp_data = inp_obj.data if hasattr(inp_obj, 'data') else inp_obj
            t = tparam_from_point_and_path(pt, inp_data)
            if t is not None:
                return t
        logger.warning("tparam_from_coords('%s'): path input not recognized", name)
        return None

    def get_independents(self):
        """Return dict of independent (animatable) elements with their types and values.

        Returns dict: name -> {type, value/coords/tparam, ...}
        Types: 'free_point', 'tparam_point', 'free_text',
        'number', 'measure', 'angle', 'boolean'
        """
        result = {}
        for name, st in self.state.items():
            elem = self.element(name)
            var = self.var(name)

            # Free point: level 0, is a Point, no input commands
            if elem and isinstance(elem.data, Point) and st['level'] == 0 and not st['input_commands']:
                result[name] = {
                    'type': 'free_point',
                    'coords': elem.data.coords.tolist()
                }
                continue

            # Parametrically-constrained point: has a curve/locus
            # parameter and input commands.
            if elem and isinstance(elem.data, Point) and elem.tparam is not None and st['input_commands']:
                cmd = self.commandByElementName(name)
                constraint = 'unknown'
                if cmd:
                    for inp_name in cmd.inputs:
                        inp_obj = self.objectByName(inp_name) if isinstance(inp_name, str) else inp_name
                        inp_data = inp_obj.data if hasattr(inp_obj, 'data') else inp_obj
                        if isinstance(inp_data, Circle):
                            constraint = 'circle'
                            break
                        elif isinstance(inp_data, Segment):
                            constraint = 'segment'
                            break
                        elif isinstance(inp_data, Ray):
                            constraint = 'ray'
                            break
                        elif isinstance(inp_data, Line):
                            constraint = 'line'
                            break
                        elif isinstance(inp_data, Conic):
                            constraint = _CONIC_CONSTRAINTS.get(inp_data.type, 'unknown')
                            break
                        elif isinstance(inp_data, LocusCurve):
                            constraint = 'locus'
                            break
                        elif isinstance(inp_data, Function):
                            constraint = 'function'
                            break
                tp = elem.tparam
                result[name] = {
                    'type': 'tparam_point',
                    'constraint': constraint,
                    'tparam': list(tp) if isinstance(tp, (tuple, list)) else tp,
                    'coords': elem.data.coords.tolist()
                }
                continue

            # Free text: a movable GeoGebra text object with literal position.
            # Text anchored to a point follows that point and is not a separate
            # keyframe input.
            if (elem and isinstance(elem.data, Text)
                    and elem.data.anchor_point is None
                    and elem.data.position is not None
                    and st['level'] == 0 and not st['input_commands']):
                result[name] = {
                    'type': 'free_text',
                    'position': np.asarray(elem.data.position[:2], dtype=float).tolist()
                }
                continue

            # Free variable: level 0, no input commands
            if var and st['level'] == 0 and not st['input_commands']:
                def bounds(v):
                    # Optional slider min/max/step, if a GGB import (or a caller)
                    # stored them on the var's style. Absent → the consumer
                    # (e.g. the JSXGraph exporter) falls back to a heuristic.
                    out = {}
                    style = getattr(v, 'style', None)
                    if style:
                        for src, dst in (('slider_min', 'min'),
                                         ('slider_max', 'max'),
                                         ('slider_step', 'step')):
                            val = style.get(src)
                            if val is not None:
                                out[dst] = val
                    return out

                if isinstance(var.data, Measure):
                    result[name] = {'type': 'measure',
                                    'value': var.data.value,
                                    'dim': var.data.dimension,
                                    **bounds(var)}
                elif isinstance(var.data, AngleSize):
                    result[name] = {'type': 'angle', 'value': var.data.value,
                                    **bounds(var)}
                elif isinstance(var.data, Boolean):
                    result[name] = {'type': 'boolean', 'value': var.data.value}
                elif isinstance(var.data, (int, float)):
                    result[name] = {'type': 'number', 'value': var.data,
                                    **bounds(var)}

        return result

    def rebuild(self, debug = False, full = False):
        if debug: logger.debug('rebuild(full=%s)', full)
        if full:
            logger.info("Rebuilding construction (%d commands)", len(self.commands))
        
        log = {}
        if full:
            for command in self.commands: self.apply(command, debug, log = log)
        else:
            state = []
            for name in self.state:
                level = self.state[name]['level']
                while level >= len(state): state.append([])
                state[level].append(name)

            for level in range(len(state)):
                for name in state[level]:
                    if not self.state[name]['built']:
                        for command in self.state[name]['input_commands']:
                            self.apply(command, debug = debug, log = log)
        
        return log

    def copy(self, command):
        assert(isinstance(command, Command))
        command_copy = Command(command.name, list(command.inputs).copy(), list(command.outputs).copy())
        return command_copy

    def apply(self, command_original, debug = False, log = None):
        command = self.copy(command_original)            
        self.prepareInputs(command)
        input_data = [obj.data if hasattr(obj,"data") else obj for obj in command.inputs]
        
        # Special case for Point on a curve: if ``.tparam`` is set,
        # pass it to the command as an extra input so the dispatcher
        # can compute the position along the locus (circle angle,
        # segment/line/ray linear parameter).
        if len(command.outputs) == 1 and self.element(command.outputs[0]):
            if isinstance(self.element(command.outputs[0]).data, Point):
                if self.element(command.outputs[0]).tparam is not None:
                    input_data.append(self.element(command.outputs[0]).tparam)
        
        # Special case for Intersect(Circle/Conic, ...): GeoGebra orders
        # intersections by already-known points on the input objects.
        points_order = None
        binding = getattr(command_original, '_ggb_intersection', None)
        if command.name == 'Intersect':
            points_order = self._intersect_points_order(command_original, input_data)
            if binding is None and points_order and is_number(input_data[-1]):
                input_data.append(points_order)

        if command.name == 'Locus':
            if (
                command_original.outputs
                and command_original.outputs[0] in self._locus_sampling_suppressed_outputs
            ):
                return
            output_data = [self._build_locus(command_original, input_data)]
            if debug:
                str_inputs = [obj.name if hasattr(obj,"name") else obj for obj in command_original.inputs]
                logger.debug("locus: %s >> %s", str_inputs, command_original.outputs)
                logger.debug("    out: %s", output_data)
            for i in range(len(output_data)):
                if i < len(command.outputs):
                    if self.element(command.outputs[i]) is not None:
                        if not self.element(command.outputs[i]).fixed:
                            self.update(command.outputs[i], output_data[i], log=log)
                    else:
                        self.update(command.outputs[i], output_data[i], log=log)
            return
        
        f = command.func(log_unsupported=False)

        if f is not None:
            try:
                output_data = (binding.compute(input_data, points_order)
                               if binding is not None else NotImplemented)
                bound = output_data is not NotImplemented
                if not bound:
                    args = input_data
                    if binding is not None and points_order and is_number(input_data[-1]):
                        args = input_data + [points_order]
                    output_data = f(*args)
                if not isinstance(output_data, list): output_data = [output_data]
                if not bound and command.name == 'Intersect' and points_order:
                    output_data = order_points_by_reference(output_data, points_order)
                if debug:
                    str_inputs = [obj.name if hasattr(obj,"name") else obj for obj in command_original.inputs]
                    logger.debug("%s: %s >> %s", f.__name__, str_inputs, command_original.outputs)
                    logger.debug("    in:  %s", input_data)
                    logger.debug("    out: %s", output_data)

                # Output names are stable slots, including currently undefined
                # ones. Keeping every slot lets GGB import retain its visual
                # metadata and clears an old result when an intersection vanishes.
                for i, name in enumerate(command.outputs):
                    data = output_data[i] if i < len(output_data) else None
                    elem = self.element(name)
                    if elem is None or not elem.fixed:
                        self.update(name, data, log=log)
            except Exception as e:
                str_inputs = [obj.name if hasattr(obj,"name") else obj for obj in command_original.inputs]
                logger.warning("Command '%s(%s)' failed: %s", f.__name__, str_inputs, e)
                for i in range(len(command.outputs)):
                    obj = self.element(command.outputs[i])
                    if obj is None or not obj.fixed:
                        self.update(command.outputs[i], None, log = log)
        else:
            str_inputs = [obj.name if hasattr(obj,"name") else obj for obj in command_original.inputs]
                    
            has_none_attr = False
            for inp in input_data: 
                if inp is None: 
                    has_none_attr = True
                    break
            
            if has_none_attr:
                self._record_dependency_skip(command_original, command, input_data)
                if debug:
                    logger.debug("%s: %s >> %s (undefined args)", strFullCommand(command.name, command.inputs), str_inputs, command_original.outputs)
            else:
                diagnostic = self._record_unsupported_command(command_original, command, input_data)
                if self.log_unsupported and not self._unsupported_summary_logged:
                    n_unique = len(self._command_diagnostic_keys)
                    n_skips = sum(1 for d in self.command_diagnostics if d.get('reason') == 'dependency_skip')
                    logger.warning(
                        "Unsupported commands detected: %d unique signatures, %d dependent skips. "
                        "Use --log-level DEBUG for full list or check construction.command_diagnostics.",
                        n_unique, n_skips,
                    )
                    self._unsupported_summary_logged = True
                if self.strict_unsupported:
                    raise UnsupportedCommandError(diagnostic)
                
            for i in range(len(command.outputs)):
                obj = self.element(command.outputs[i])
                if obj is None or not obj.fixed:
                    self.update(command.outputs[i], None, log = log)

    def _record_unsupported_command(self, command_original, prepared_command, input_data):
        signature = [type(x).__name__ for x in input_data]
        outputs = [getattr(o, 'name', str(o)) for o in command_original.outputs]
        key = (command_original.name, tuple(signature), tuple(outputs))
        if key in self._command_diagnostic_keys:
            for diagnostic in self.command_diagnostics:
                if (
                    diagnostic.get('command') == command_original.name
                    and tuple(diagnostic.get('signature', [])) == tuple(signature)
                    and tuple(diagnostic.get('outputs', [])) == tuple(outputs)
                ):
                    return diagnostic
        diagnostic = {
            'command': command_original.name,
            'signature': signature,
            'outputs': outputs,
            'reason': 'unsupported_signature',
        }
        self.command_diagnostics.append(diagnostic)
        self._command_diagnostic_keys.add(key)
        root_id = len(self.command_diagnostics) - 1
        for output in outputs:
            self._unsupported_roots_by_output[output] = root_id
        return diagnostic

    def record_expression_diagnostic(self, reason, output, expression,
                                     parameters=None, detail=None,
                                     command='Expression'):
        """Record a problem with a parsed expression rather than a command —
        e.g. a formula that mentions a slider but had to be imported as a
        frozen snapshot. Same dict shape as the command diagnostics, so a
        client can warn the user that the object will not follow the number.
        """
        diagnostic = {
            'command': command,
            'signature': [],
            'outputs': [output],
            'reason': reason,
            'expression': expression,
        }
        if parameters:
            diagnostic['parameters'] = list(parameters)
        if detail:
            diagnostic['detail'] = detail
        self.command_diagnostics.append(diagnostic)
        return diagnostic

    def _intersect_points_order(self, command_original, input_data):
        """Return GeoGebra-like point ordering hints for Intersect outputs.

        The indexed Intersect(..., 1/2) path and the multi-output
        Intersect(...) -> A, B path must use the same ordering contract.
        For circle/conic intersections, prefer points that already define the
        curve, then points from the other input object.
        """
        if len(input_data) < 2:
            return None

        first_two = input_data[:2]
        curve_index = None
        for i, data in enumerate(first_two):
            if isinstance(data, (Circle, Conic)):
                curve_index = i
                break
        if curve_index is None:
            return None

        ordered_input_indices = [curve_index]
        ordered_input_indices.extend(
            i for i in range(len(first_two)) if i != curve_index
        )

        points_order = []
        for input_index in ordered_input_indices:
            original_input = command_original.inputs[input_index]
            input_name = (
                original_input.name if hasattr(original_input, "name")
                else original_input
            )
            if not isinstance(input_name, str) or input_name not in self.state:
                continue
            for name in self.state[input_name]['inputs']:
                elem = self.element(name)
                if elem is not None and isinstance(elem.data, Point):
                    points_order.append(elem.data)

        return points_order or None

    def _record_dependency_skip(self, command_original, prepared_command, input_data):
        root_ids = []
        for raw_input in command_original.inputs:
            name = getattr(raw_input, 'name', raw_input)
            if isinstance(name, str) and name in self._unsupported_roots_by_output:
                root_id = self._unsupported_roots_by_output[name]
                if root_id not in root_ids:
                    root_ids.append(root_id)
        outputs = [getattr(o, 'name', str(o)) for o in command_original.outputs]
        for output in outputs:
            for root_id in root_ids:
                self._unsupported_roots_by_output[output] = root_id
        for root_id in root_ids:
            diagnostic = self.command_diagnostics[root_id]
            dependents = diagnostic.setdefault('dependents', [])
            dependent = {
                'command': command_original.name,
                'signature': [type(x).__name__ for x in input_data],
                'outputs': outputs,
                'reason': 'depends_on_unsupported',
            }
            dep_key = (
                dependent['command'],
                tuple(dependent['signature']),
                tuple(dependent['outputs']),
            )
            if not any(
                (
                    item.get('command'),
                    tuple(item.get('signature', [])),
                    tuple(item.get('outputs', [])),
                ) == dep_key
                for item in dependents
            ):
                dependents.append(dependent)

    def _build_locus(self, command_original, input_data):
        """Build a sampled numeric locus for GeoGebra Locus(Point, Point).

        GeoGebra's locus can be symbolic or dynamically sampled. AnimaGeo's
        current model stores a numeric polyline: sample the mover point's
        path parameter, rebuild the dependent point, and collect its coords.
        """
        if len(input_data) < 2 or input_data[0] is None:
            return None
        if len(command_original.inputs) < 2 or len(command_original.outputs) < 1:
            return LocusCurve([input_data[0].coords])

        dependent_name = command_original.inputs[0]
        mover_name = command_original.inputs[1]
        output_name = command_original.outputs[0]
        dependent_elem = self.element(dependent_name)
        mover_elem = self.element(mover_name)
        if dependent_elem is None or mover_elem is None:
            return LocusCurve([input_data[0].coords])

        ts = self._locus_sample_parameters(mover_name, mover_elem)
        if not ts:
            return LocusCurve([dependent_elem.data.coords])

        original_tparam = mover_elem.tparam
        points = []
        try:
            self._locus_sampling_suppressed_outputs.add(output_name)
            for t in ts:
                self.update_tparam(mover_name, t)
                if output_name in self.state:
                    self.state[output_name]['built'] = True
                self.rebuild(full=False)
                current = self.element(dependent_name)
                if current is not None and isinstance(current.data, Point):
                    coords = current.data.coords
                    if np.all(np.isfinite(coords)):
                        if not points or not np.allclose(points[-1], coords, atol=1e-8):
                            points.append(coords.copy())
        finally:
            mover_elem.tparam = original_tparam
            if mover_name in self.state:
                self.state[mover_name]['built'] = False
                for output in self.state[mover_name]['outputs']:
                    self.state[output]['built'] = False
            if output_name in self.state:
                self.state[output_name]['built'] = True
            self.rebuild(full=False)
            if output_name in self.state:
                self.state[output_name]['built'] = False
            self._locus_sampling_suppressed_outputs.discard(output_name)

        if not points:
            current = self.element(dependent_name)
            if current is not None and isinstance(current.data, Point):
                points = [current.data.coords.copy()]
        return LocusCurve(points)

    def _locus_sample_parameters(self, mover_name, mover_elem):
        cmd = self.commandByElementName(mover_name)
        if cmd is None or not cmd.inputs:
            return []
        raw_path = cmd.inputs[0]
        path_obj = self.objectByName(raw_path) if isinstance(raw_path, str) else raw_path
        path_data = path_obj.data if hasattr(path_obj, 'data') else path_obj
        n = 80
        original = mover_elem.tparam

        if isinstance(path_data, Segment):
            return np.linspace(0.0, 1.0, n).tolist()
        if isinstance(path_data, Arc):
            return np.linspace(path_data.angles[0], path_data.angles[1], n).tolist()
        if isinstance(path_data, Circle):
            return np.linspace(0.0, 2 * np.pi, n, endpoint=False).tolist()
        if isinstance(path_data, Ray):
            hi = max(10.0, float(original or 0.0) * 2.0)
            return np.linspace(0.0, hi, n).tolist()
        if isinstance(path_data, Line):
            center = float(original or 0.0)
            return np.linspace(center - 10.0, center + 10.0, n).tolist()
        if isinstance(path_data, Conic):
            if path_data.type in (ConicType.CIRCLE, ConicType.ELLIPSE):
                return np.linspace(0.0, 2 * np.pi, n, endpoint=False).tolist()
            if path_data.type == ConicType.HYPERBOLA:
                branch = 1.0
                center = 0.0
                if isinstance(original, (tuple, list)):
                    branch = 1.0 if float(original[0]) >= 0 else -1.0
                    center = float(original[1])
                return [(branch, t) for t in np.linspace(center - 3.0, center + 3.0, n)]
            if path_data.type == ConicType.PARABOLA:
                center = float(original or 0.0)
                return np.linspace(center - 10.0, center + 10.0, n).tolist()
        if isinstance(path_data, LocusCurve):
            return np.linspace(0.0, 1.0, n).tolist()
        return []
