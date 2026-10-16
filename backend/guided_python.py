"""Code Quest guided Python interpreter.

A constrained, safe interpreter for beginner lessons. It is a strict superset of
the legacy ``_python_output`` subset and adds the constructs the phase curriculum
needs before learners switch to real Python:

  - ``while`` loops with ``break`` / ``continue``
  - slicing (``value[start:stop:step]``)
  - f-strings with basic format specs
  - comprehensions (list, dict, set)
  - sets
  - extended string / list / dict / set methods
  - ``try`` / ``except`` / ``finally``, ``raise``, ``assert``
  - tuple unpacking in assignments and loop targets

Errors raise :class:`GuidedError`, which carries an optional ``kind`` used by
``try`` / ``except`` matching (ValueError, TypeError, ZeroDivisionError, ...).
"""

import ast
import operator
from decimal import Decimal
from typing import Optional

MAX_STEPS_DEFAULT = 10_000
MAX_OUTPUT_CHARS_DEFAULT = 5_000
MAX_COLLECTION_DEFAULT = 1_000
MAX_CALL_DEPTH_DEFAULT = 12

_KNOWN_EXCEPTIONS = {
    "Exception",
    "ValueError",
    "TypeError",
    "ZeroDivisionError",
    "KeyError",
    "IndexError",
    "AssertionError",
    "RuntimeError",
    "NameError",
}


class GuidedError(Exception):
    """A safe, learner-facing error from the guided interpreter."""

    def __init__(self, message: str, kind: str = "Exception", line: Optional[int] = None, column: Optional[int] = None, text: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.line = line
        self.column = column
        self.text = text if text is not None else message


class _ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _Function:
    def __init__(self, parameters, body):
        self.parameters = parameters
        self.body = body


def run(
    source: str,
    initial_environment: Optional[dict] = None,
    *,
    max_steps: int = MAX_STEPS_DEFAULT,
    max_output_chars: int = MAX_OUTPUT_CHARS_DEFAULT,
    max_collection: int = MAX_COLLECTION_DEFAULT,
    max_call_depth: int = MAX_CALL_DEPTH_DEFAULT,
) -> str:
    try:
        tree = ast.parse(source, mode="exec")
    except (SyntaxError, ValueError) as exc:
        line = getattr(exc, "lineno", None)
        column = getattr(exc, "offset", None)
        raise GuidedError(f"Syntax error: {getattr(exc, 'msg', 'check the code format')}.", line=line, column=column) from None
    except RecursionError:
        raise GuidedError("This code is nested too deeply. Try a simpler version.") from None

    output: list[str] = []
    output_chars = 0
    environment: dict = dict(initial_environment or {})
    steps = 0

    def fail(message: str, kind: str = "Exception", line: Optional[int] = None, column: Optional[int] = None, text: Optional[str] = None):
        raise GuidedError(message, kind=kind, line=line, column=column, text=text)

    def tick() -> None:
        nonlocal steps
        steps += 1
        if steps > max_steps:
            fail("This program is doing too much work. Check your loops.")

    def append_output(value: str) -> None:
        nonlocal output_chars
        if output_chars + len(value) > max_output_chars:
            fail("The program produced too much output.")
        output.append(value)
        output_chars += len(value)

    def display(value, nested=False, depth=0):
        """Write a bounded representation without expanding nested collections at once."""
        if isinstance(value, (list, tuple)):
            if depth >= 64:
                fail("That value is nested too deeply to display.")
            opening, closing = ("[", "]") if isinstance(value, list) else ("(", ")")
            append_output(opening)
            for index, item in enumerate(value):
                if index:
                    append_output(", ")
                display(item, nested=True, depth=depth + 1)
            if isinstance(value, tuple) and len(value) == 1:
                append_output(",")
            append_output(closing)
            return
        if isinstance(value, set):
            if depth >= 64:
                fail("That value is nested too deeply to display.")
            if not value:
                append_output("set()")
                return
            append_output("{")
            for index, item in enumerate(value):
                if index:
                    append_output(", ")
                display(item, nested=True, depth=depth + 1)
            append_output("}")
            return
        if isinstance(value, dict):
            if depth >= 64:
                fail("That value is nested too deeply to display.")
            append_output("{")
            for index, (key, item) in enumerate(value.items()):
                if index:
                    append_output(", ")
                display(key, nested=True, depth=depth + 1)
                append_output(": ")
                display(item, nested=True, depth=depth + 1)
            append_output("}")
            return
        if isinstance(value, str):
            append_output(repr(value) if nested else value)
        elif value is None:
            append_output("None")
        elif value is True:
            append_output("True")
        elif value is False:
            append_output("False")
        else:
            append_output(str(value))

    def guard_collection(value):
        """Bound the work Python's native nested collection comparisons can do."""
        pending = [value]
        visited = 0
        while pending:
            current = pending.pop()
            visited += 1
            if visited > 5_000:
                fail("That comparison involves a collection that is too large.")
            if isinstance(current, (list, tuple, set)):
                pending.extend(current)
            elif isinstance(current, dict):
                pending.extend(current.keys())
                pending.extend(current.values())

    def safe_result(value):
        if isinstance(value, (str, list, tuple)) and len(value) > max_collection * 5:
            fail("That value is too large to display in Code Quest.")
        if isinstance(value, set) and len(value) > max_collection * 5:
            fail("That value is too large to display in Code Quest.")
        if isinstance(value, int) and value.bit_length() > 4096:
            fail("That number is too large for this exercise.")
        if isinstance(value, Decimal) and (not value.is_finite() or (value and abs(value.adjusted()) > 4_096)):
            fail("That decimal is too large for this exercise.")
        return value

    binary_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.BitOr: operator.or_,
        ast.BitAnd: operator.and_,
    }
    comparisons = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.Is: operator.is_,
        ast.IsNot: operator.is_not,
        ast.In: lambda left, right: left in right,
        ast.NotIn: lambda left, right: left not in right,
    }
    iterable_types = (list, tuple, range, dict, str, set)

    def evaluate_iterable(node, scope, depth, what):
        values = evaluate(node, scope, depth)
        if not isinstance(values, iterable_types):
            fail(f"{what} needs a list, tuple, dictionary, range, set, or text value.")
        try:
            size = len(values)
        except (TypeError, OverflowError):
            fail(f"{what} involves a collection that is too large.")
        if size > max_collection:
            fail(f"{what} involves a collection that is too large (limit {max_collection:,}).")
        return values

    def evaluated_slice(node, scope, depth):
        lower = evaluate(node.lower, scope, depth) if node.lower is not None else None
        upper = evaluate(node.upper, scope, depth) if node.upper is not None else None
        step = evaluate(node.step, scope, depth) if node.step is not None else None
        for part in (lower, upper, step):
            if part is not None and not isinstance(part, int):
                fail("Slice positions must be whole numbers.", kind="TypeError")
        return slice(lower, upper, step)

    def evaluate(node, scope, depth=0):
        tick()
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in scope:
                fail(f"The name '{node.id}' has not been defined yet.", kind="NameError")
            return scope[node.id]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            if len(node.elts) > max_collection:
                fail("That collection is too large for this exercise.")
            values = [evaluate(item, scope, depth) for item in node.elts]
            if isinstance(node, ast.List):
                return values
            if isinstance(node, ast.Tuple):
                return tuple(values)
            try:
                return set(values)
            except TypeError:
                fail("Set items must be simple values like numbers or text.", kind="TypeError")
        if isinstance(node, ast.Dict):
            if len(node.keys) > max_collection:
                fail("That collection is too large for this exercise.")
            return {
                evaluate(key, scope, depth): evaluate(value, scope, depth)
                for key, value in zip(node.keys, node.values)
                if key is not None
            }
        if isinstance(node, ast.ListComp):
            return run_comprehension(node, scope, depth, "list")
        if isinstance(node, ast.SetComp):
            return run_comprehension(node, scope, depth, "set")
        if isinstance(node, ast.DictComp):
            return run_comprehension(node, scope, depth, "dict")
        if isinstance(node, ast.JoinedStr):
            return evaluated_fstring(node, scope, depth)
        if isinstance(node, ast.BinOp) and type(node.op) in binary_operators:
            left = evaluate(node.left, scope, depth)
            right = evaluate(node.right, scope, depth)
            if isinstance(node.op, ast.Mult):
                sequence, count = (left, right) if isinstance(left, (str, list, tuple)) and isinstance(right, int) else (right, left) if isinstance(right, (str, list, tuple)) and isinstance(left, int) else (None, None)
                if sequence is not None and len(sequence) * max(0, count) > 5_000:
                    fail("That multiplication would create a value that is too large.")
            try:
                return safe_result(binary_operators[type(node.op)](left, right))
            except ZeroDivisionError:
                fail("You cannot divide by zero.", kind="ZeroDivisionError")
            except (TypeError, ValueError, OverflowError):
                fail("That operation does not work with those values.", kind="TypeError")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            value = evaluate(node.operand, scope, depth)
            try:
                result = not value if isinstance(node.op, ast.Not) else value if isinstance(node.op, ast.UAdd) else -value
                return safe_result(result)
            except (TypeError, ValueError):
                fail("That operation does not work with this value.", kind="TypeError")
        if isinstance(node, ast.Compare):
            left = evaluate(node.left, scope, depth)
            for operation, comparator in zip(node.ops, node.comparators):
                right = evaluate(comparator, scope, depth)
                try:
                    if isinstance(left, (list, tuple, set)) or isinstance(right, (list, tuple, set)):
                        guard_collection(left)
                        guard_collection(right)
                    matched = comparisons[type(operation)](left, right)
                except (KeyError, TypeError, ValueError):
                    fail("That comparison does not work with these values.", kind="TypeError")
                if not matched:
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result = True
                for item in node.values:
                    result = evaluate(item, scope, depth)
                    if not result:
                        return result
                return result
            result = False
            for item in node.values:
                result = evaluate(item, scope, depth)
                if result:
                    return result
            return result
        if isinstance(node, ast.IfExp):
            branch = node.body if evaluate(node.test, scope, depth) else node.orelse
            return evaluate(branch, scope, depth)
        if isinstance(node, ast.Subscript):
            value = evaluate(node.value, scope, depth)
            if isinstance(node.slice, ast.Slice):
                index = evaluated_slice(node.slice, scope, depth)
            else:
                index = evaluate(node.slice, scope, depth)
            try:
                result = value[index]
            except TypeError:
                fail("That item cannot be read from this value.", kind="TypeError")
            except KeyError:
                fail("That item cannot be read from this value.", kind="KeyError")
            except (IndexError, ValueError):
                fail("That item cannot be read from this value.", kind="IndexError")
            except OverflowError:
                fail("That index is out of range.", kind="IndexError")
            return safe_result(result)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = evaluate(node.func.value, scope, depth)
            arguments = [evaluate(argument, scope, depth) for argument in node.args]
            options = {}
            for keyword in node.keywords:
                if keyword.arg is None:
                    fail("This method call form is not supported yet.")
                options[keyword.arg] = evaluate(keyword.value, scope, depth)
            return call_method(receiver, node.func.attr, arguments, options)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return call_builtin(node, scope, depth)
        fail("That code feature is not in the current lesson yet.")

    def evaluated_fstring(node, scope, depth):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
                continue
            if not isinstance(value, ast.FormattedValue):
                fail("This f-string form is not supported yet.")
            inner = evaluate(value.value, scope, depth)
            if value.conversion == 115:
                text = str(inner)
            elif value.conversion == 114:
                text = repr(inner)
            elif value.format_spec is not None:
                spec = evaluated_fstring(value.format_spec, scope, depth)
                if len(spec) > 20:
                    fail("That format specification is too long.")
                try:
                    text = format(inner, spec)
                except (TypeError, ValueError):
                    fail("That format specification does not fit this value.", kind="ValueError")
            else:
                text = str(inner)
            parts.append(text)
        return "".join(parts)

    def call_method(receiver, method, arguments, options):
        try:
            return _call_method_inner(receiver, method, arguments, options)
        except GuidedError:
            raise
        except (TypeError, ValueError):
            fail(f"'{method}()' does not work with those values.", kind="TypeError")
        except KeyError:
            fail(f"'{method}()' could not find that item.", kind="KeyError")
        except IndexError:
            fail(f"'{method}()' could not find that position.", kind="IndexError")

    def _call_method_inner(receiver, method, arguments, options):
        if options and not (isinstance(receiver, list) and method == "sort"):
            fail("This method call form is not supported yet.")
        if isinstance(receiver, str):
            if method in {"lower", "upper", "strip", "title", "lstrip", "rstrip", "capitalize", "casefold", "isdigit", "isalpha", "isupper", "islower", "isspace", "isnumeric", "isalnum"} and not arguments:
                return getattr(receiver, method)()
            if method == "split" and len(arguments) <= 1:
                if arguments and not isinstance(arguments[0], str):
                    fail("split() needs text as its separator.", kind="TypeError")
                pieces = receiver.split(*arguments)
                if len(pieces) > max_collection:
                    fail("That split would create too many pieces.")
                return pieces
            if method == "join" and len(arguments) == 1:
                sequence = arguments[0]
                if not isinstance(sequence, (list, tuple)) or not all(isinstance(item, str) for item in sequence):
                    fail("join() needs a list of text values.", kind="TypeError")
                if len(sequence) > max_collection:
                    fail("That join would combine too many pieces.")
                return safe_result(receiver.join(sequence))
            if method == "replace" and len(arguments) in {2, 3}:
                return receiver.replace(*arguments)
            if method in {"startswith", "endswith"} and 1 <= len(arguments) <= 3:
                return getattr(receiver, method)(*arguments)
            if method == "find" and len(arguments) <= 2:
                return receiver.find(*arguments)
            if method == "count" and len(arguments) == 1:
                return receiver.count(arguments[0])
            if method == "index" and len(arguments) == 1:
                return receiver.index(arguments[0])
            if method == "zfill" and len(arguments) == 1:
                return receiver.zfill(arguments[0])
        if isinstance(receiver, (list, tuple)):
            mutator = isinstance(receiver, list)
            if method == "append" and mutator and len(arguments) == 1:
                if len(receiver) >= max_collection:
                    fail("That list is too large for this exercise.")
                receiver.append(arguments[0])
                return None
            if method == "extend" and mutator and len(arguments) == 1:
                extra = arguments[0]
                if not isinstance(extra, iterable_types):
                    fail("extend() needs a list, tuple, or set.", kind="TypeError")
                if len(receiver) + len(extra) > max_collection:
                    fail("That list is too large for this exercise.")
                receiver.extend(extra)
                return None
            if method == "insert" and mutator and len(arguments) == 2:
                if len(receiver) >= max_collection:
                    fail("That list is too large for this exercise.")
                receiver.insert(arguments[0], arguments[1])
                return None
            if method == "pop" and mutator and len(arguments) <= 1:
                if not receiver:
                    fail("pop() needs a list with at least one item.", kind="IndexError")
                try:
                    return receiver.pop(*arguments)
                except IndexError:
                    fail("That position is not in the list.", kind="IndexError")
            if method == "remove" and mutator and len(arguments) == 1:
                try:
                    receiver.remove(arguments[0])
                except ValueError:
                    fail("remove() could not find that item in the list.", kind="ValueError")
                return None
            if method == "sort" and mutator and not arguments:
                reverse = options.get("reverse", False)
                if not isinstance(reverse, bool):
                    fail("sort(reverse=...) needs True or False.", kind="TypeError")
                if len(receiver) > max_collection:
                    fail("That list is too large to sort.")
                receiver.sort(reverse=reverse)
                return None
            if method == "reverse" and mutator and not arguments:
                receiver.reverse()
                return None
            if method == "count" and len(arguments) == 1:
                guard_collection(receiver)
                return receiver.count(arguments[0])
            if method == "index" and len(arguments) == 1:
                try:
                    return receiver.index(arguments[0])
                except ValueError:
                    fail("index() could not find that item in the list.", kind="ValueError")
            if method == "clear" and mutator and not arguments:
                receiver.clear()
                return None
        if isinstance(receiver, dict):
            if method == "get" and 1 <= len(arguments) <= 2:
                return receiver.get(*arguments)
            if method in {"keys", "values", "items"} and not arguments:
                return list(getattr(receiver, method)())
            if method == "update" and len(arguments) == 1:
                if not isinstance(arguments[0], dict):
                    fail("update() needs a dictionary.", kind="TypeError")
                if len(receiver) + len(arguments[0]) > max_collection:
                    fail("That dictionary is too large for this exercise.")
                receiver.update(arguments[0])
                return None
            if method == "pop" and len(arguments) == 1:
                if arguments[0] not in receiver:
                    fail("pop() could not find that key.", kind="KeyError")
                return receiver.pop(arguments[0])
            if method == "clear" and not arguments:
                receiver.clear()
                return None
        if isinstance(receiver, set):
            if method == "add" and len(arguments) == 1:
                if len(receiver) >= max_collection:
                    fail("That set is too large for this exercise.")
                receiver.add(arguments[0])
                return None
            if method in {"discard", "remove"} and len(arguments) == 1:
                if method == "remove" and arguments[0] not in receiver:
                    fail("remove() could not find that item in the set.", kind="KeyError")
                receiver.discard(arguments[0])
                return None
            if method in {"union", "intersection", "difference"} and len(arguments) == 1:
                other = arguments[0]
                if not isinstance(other, (set, list, tuple)):
                    fail(f"{method}() needs a set or list.", kind="TypeError")
                result = getattr(receiver, method)(other)
                if len(result) > max_collection:
                    fail("That set is too large for this exercise.")
                return result
            if method in {"issubset", "issuperset"} and len(arguments) == 1:
                other = arguments[0]
                if not isinstance(other, (set, list, tuple)):
                    fail(f"{method}() needs a set or list.", kind="TypeError")
                return getattr(receiver, method)(other)
            if method == "clear" and not arguments:
                receiver.clear()
                return None
        fail(f"'{method}()' is not available for this value.")

    def call_builtin(node, scope, depth):
        name = node.func.id
        if name == "print":
            arguments = [evaluate(argument, scope, depth) for argument in node.args]
            options = {keyword.arg: evaluate(keyword.value, scope, depth) for keyword in node.keywords if keyword.arg in {"sep", "end"}}
            if len(options) != len(node.keywords) or not all(isinstance(value, str) for value in options.values()):
                fail("print() only supports text values for sep and end.")
            for index, value in enumerate(arguments):
                if index:
                    append_output(options.get("sep", " "))
                display(value)
            append_output(options.get("end", "\n"))
            return None

        keyword_options = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                fail("This call form is not supported yet.")
            keyword_options[keyword.arg] = evaluate(keyword.value, scope, depth)
        if keyword_options and not (name == "sorted" and set(keyword_options) <= {"reverse"}):
            fail(f"{name}() does not support named arguments in this lesson.")
        arguments = [evaluate(argument, scope, depth) for argument in node.args]

        if name == "range":
            if not 1 <= len(arguments) <= 3 or not all(isinstance(value, int) for value in arguments):
                fail("range() needs one to three whole-number values.", kind="TypeError")
            try:
                values = range(*arguments)
            except (ValueError, TypeError):
                fail("Those values do not make a valid range.", kind="ValueError")
            try:
                if len(values) > max_collection:
                    fail("That range is too large for this exercise.")
            except OverflowError:
                fail("That range is too large for this exercise.")
            return values
        if name == "len":
            if len(arguments) != 1:
                fail("len() needs one value.", kind="TypeError")
            try:
                return len(arguments[0])
            except OverflowError:
                fail("That collection is too large for this exercise.")
            except TypeError:
                fail("len() needs a list, tuple, dictionary, set, or text value.", kind="TypeError")
        if name in {"sum", "min", "max", "sorted", "round", "int", "float", "str", "bool", "list", "dict", "tuple", "set", "enumerate", "zip", "abs", "any", "all"}:
            if len(arguments) > 2 and name != "sorted":
                fail(f"{name}() received too many values.", kind="TypeError")
            try:
                if name in {"sum", "min", "max", "sorted", "enumerate", "zip", "any", "all"}:
                    for argument in arguments[:1]:
                        if not isinstance(argument, iterable_types) and not isinstance(argument, (list, tuple)):
                            fail(f"{name}() needs a bounded list, tuple, range, set, or text value.", kind="TypeError")
                        if len(argument) > max_collection:
                            fail(f"{name}() needs a collection with at most {max_collection:,} items.")
                if name == "sum": return sum(*arguments)
                if name == "min": return min(*arguments)
                if name == "max": return max(*arguments)
                if name == "sorted":
                    return sorted(*arguments, reverse=bool(keyword_options.get("reverse", False)))
                if name == "round": return round(*arguments)
                if name == "int": return int(*arguments)
                if name == "float": return float(*arguments)
                if name == "str": return str(*arguments)
                if name == "bool": return bool(*arguments)
                if name == "list": return list(*arguments)
                if name == "dict": return dict(*arguments)
                if name == "tuple": return tuple(*arguments)
                if name == "set": return set(*arguments)
                if name == "enumerate": return list(enumerate(*arguments))
                if name == "zip": return list(zip(*arguments))
                if name == "abs": return abs(*arguments)
                if name == "any": return any(*arguments)
                if name == "all": return all(*arguments)
            except GuidedError:
                raise
            except ValueError:
                fail(f"{name}() cannot use those values.", kind="ValueError")
            except (TypeError, OverflowError, ArithmeticError):
                fail(f"{name}() cannot use those values.", kind="TypeError")
        if name in scope and isinstance(scope[name], _Function):
            function = scope[name]
            if len(arguments) != len(function.parameters):
                fail(f"{name}() received the wrong number of values.", kind="TypeError")
            if depth >= max_call_depth:
                fail("This function call is nested too deeply.")
            local_scope = dict(scope)
            local_scope.update(zip(function.parameters, arguments))
            try:
                execute_block(function.body, local_scope, depth + 1)
            except _ReturnSignal as returned:
                return returned.value
            return None
        fail(f"'{name}()' is not available in this learning runner.")

    def run_comprehension(node, scope, depth, mode):
        local = dict(scope)
        result = [] if mode == "list" else set() if mode == "set" else {}

        def collect():
            if mode == "list":
                if len(result) >= max_collection:
                    fail("That comprehension is too large for this exercise.")
                result.append(evaluate(node.elt, local, depth))
            elif mode == "set":
                item = evaluate(node.elt, local, depth)
                if item not in result and len(result) >= max_collection:
                    fail("That comprehension is too large for this exercise.")
                try:
                    result.add(item)
                except TypeError:
                    fail("Set items must be simple values like numbers or text.", kind="TypeError")
            else:
                key = evaluate(node.key, local, depth)
                value = evaluate(node.value, local, depth)
                if key not in result and len(result) >= max_collection:
                    fail("That comprehension is too large for this exercise.")
                result[key] = value

        def walk(generators):
            comprehension = generators[0]
            values = evaluate_iterable(comprehension.iter, local, depth, "A comprehension loop")
            for value in values:
                tick()
                assign_target(comprehension.target, value, local, depth)
                matched = True
                for condition in comprehension.ifs:
                    if not evaluate(condition, local, depth):
                        matched = False
                        break
                if matched:
                    if len(generators) > 1:
                        walk(generators[1:])
                    else:
                        collect()

        walk(node.generators)
        return result

    def handler_matches(handler_type, kind) -> bool:
        names: list[str] = []

        def collect(node):
            if isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.Tuple):
                for item in node.elts:
                    collect(item)

        collect(handler_type)
        return kind in names or "Exception" in names

    def assign_target(target, value, scope, depth=0):
        if isinstance(target, ast.Name):
            scope[target.id] = value
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            if not isinstance(value, (list, tuple, str)) or len(value) != len(target.elts):
                fail("That unpacking does not match the number of names.", kind="ValueError")
            for sub_target, item in zip(target.elts, value):
                assign_target(sub_target, item, scope, depth)
            return
        if isinstance(target, ast.Subscript):
            container = evaluate(target.value, scope, depth)
            if isinstance(target.slice, ast.Slice):
                fail("This assignment form is not supported yet.")
            key = evaluate(target.slice, scope, depth)
            if isinstance(container, dict) and isinstance(key, (str, int)):
                if key not in container and len(container) >= max_collection:
                    fail("That dictionary is too large for this exercise.")
                container[key] = value
            elif isinstance(container, list) and isinstance(key, int) and 0 <= key < len(container):
                container[key] = value
            else:
                fail("That item cannot be updated in this value.", kind="TypeError")
            return
        fail("This assignment form is not supported yet.")

    def execute_block(statements, scope, depth=0):
        for statement in statements:
            tick()
            if isinstance(statement, ast.Expr):
                evaluate(statement.value, scope, depth)
            elif isinstance(statement, ast.Assign):
                assigned = evaluate(statement.value, scope, depth)
                for target in statement.targets:
                    assign_target(target, assigned, scope, depth)
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is not None:
                scope[statement.target.id] = evaluate(statement.value, scope, depth)
            elif isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name) and type(statement.op) in binary_operators:
                if statement.target.id not in scope:
                    fail(f"The name '{statement.target.id}' has not been defined yet.", kind="NameError")
                try:
                    scope[statement.target.id] = safe_result(binary_operators[type(statement.op)](scope[statement.target.id], evaluate(statement.value, scope, depth)))
                except ZeroDivisionError:
                    fail("You cannot divide by zero.", kind="ZeroDivisionError")
                except (TypeError, ValueError, OverflowError):
                    fail("That update does not work with these values.", kind="TypeError")
            elif isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Subscript) and type(statement.op) in binary_operators:
                container = evaluate(statement.target.value, scope, depth)
                key = evaluate(statement.target.slice, scope, depth)
                if not isinstance(container, (dict, list)):
                    fail("That item cannot be updated in this value.", kind="TypeError")
                try:
                    container[key] = safe_result(binary_operators[type(statement.op)](container[key], evaluate(statement.value, scope, depth)))
                except ZeroDivisionError:
                    fail("You cannot divide by zero.", kind="ZeroDivisionError")
                except (KeyError, IndexError, TypeError, ValueError, OverflowError):
                    fail("That update does not work with these values.", kind="TypeError")
            elif isinstance(statement, ast.If):
                branch = statement.body if evaluate(statement.test, scope, depth) else statement.orelse
                execute_block(branch, scope, depth)
            elif isinstance(statement, ast.For):
                if statement.orelse:
                    fail("for/else is not supported in this lesson yet.")
                values = evaluate_iterable(statement.iter, scope, depth, "A for loop")
                for value in values:
                    tick()
                    assign_target(statement.target, value, scope, depth)
                    try:
                        execute_block(statement.body, scope, depth)
                    except _ContinueSignal:
                        continue
                    except _BreakSignal:
                        break
            elif isinstance(statement, ast.While):
                if statement.orelse:
                    fail("while/else is not supported in this lesson yet.")
                while evaluate(statement.test, scope, depth):
                    tick()
                    try:
                        execute_block(statement.body, scope, depth)
                    except _ContinueSignal:
                        continue
                    except _BreakSignal:
                        break
            elif isinstance(statement, ast.Break):
                raise _BreakSignal()
            elif isinstance(statement, ast.Continue):
                raise _ContinueSignal()
            elif isinstance(statement, ast.Try):
                try:
                    try:
                        execute_block(statement.body, scope, depth)
                    except GuidedError as error:
                        handled = False
                        for handler in statement.handlers:
                            if handler.type is None or handler_matches(handler.type, error.kind):
                                if handler.name:
                                    scope[handler.name] = error.text
                                execute_block(handler.body, scope, depth)
                                handled = True
                                break
                        if not handled:
                            raise
                finally:
                    if statement.finalbody:
                        execute_block(statement.finalbody, scope, depth)
            elif isinstance(statement, ast.Raise):
                if statement.exc is None:
                    fail("Use the raise ValueError(\"message\") form in this lesson.")
                if isinstance(statement.exc, ast.Call) and isinstance(statement.exc.func, ast.Name):
                    kind_name = statement.exc.func.id
                    arguments = [evaluate(argument, scope, depth) for argument in statement.exc.args]
                    detail = str(arguments[0]) if arguments else ""
                elif isinstance(statement.exc, ast.Name):
                    kind_name, detail = statement.exc.id, ""
                else:
                    fail("This raise form is not supported yet.")
                kind = kind_name if kind_name in _KNOWN_EXCEPTIONS else "Exception"
                message = f"{kind_name}: {detail}" if detail else kind_name
                fail(message, kind=kind, text=detail)
            elif isinstance(statement, ast.Assert):
                if not evaluate(statement.test, scope, depth):
                    detail = str(evaluate(statement.msg, scope, depth)) if statement.msg is not None else ""
                    fail(f"AssertionError: {detail}" if detail else "AssertionError: the check failed.", kind="AssertionError", text=detail)
            elif isinstance(statement, ast.FunctionDef) and not statement.decorator_list and not statement.args.defaults and not statement.args.kwonlyargs:
                if statement.args.vararg or statement.args.kwarg or statement.args.posonlyargs:
                    fail("Functions in this lesson use regular named parameters.")
                scope[statement.name] = _Function([argument.arg for argument in statement.args.args], statement.body)
            elif isinstance(statement, ast.Return):
                raise _ReturnSignal(evaluate(statement.value, scope, depth) if statement.value else None)
            elif isinstance(statement, ast.Pass):
                pass
            else:
                fail("That statement is not supported in this lesson yet.")

    try:
        execute_block(tree.body, environment)
    except _ReturnSignal:
        fail("return can only be used inside a function.")
    except _BreakSignal:
        fail("break can only be used inside a loop.")
    except _ContinueSignal:
        fail("continue can only be used inside a loop.")
    except RecursionError:
        fail("This code is nested too deeply. Try a simpler version.")
    return "".join(output).rstrip("\n")
