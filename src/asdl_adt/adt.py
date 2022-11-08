"""
This is the main parsing and class metaprogramming module in ASDL-ADT.
"""
from __future__ import annotations

import functools
import inspect
import sys
import textwrap
import typing
from abc import ABC, abstractmethod
from collections import OrderedDict
from types import ModuleType
from typing import Any, Mapping, Callable, Optional, Collection, List, Union, Type

import asdl
import attrs

from asdl_adt.validators import ValidationError, instance_of, subclass_of


def _normalize(func):
    signature = inspect.signature(func)

    @functools.wraps(func)
    def _func(*args, **kwargs):
        call = signature.bind(*args, **kwargs)
        return func(*call.args, **call.kwargs)

    return _func


def _make_validator(point_valid, seq: bool, opt: bool):
    def validate(val):
        if val is None and opt:
            return val

        if seq:
            if not isinstance(val, list):
                raise ValidationError(list, type(val))
            try:
                return [point_valid(y) for y in val]
            except ValidationError as err:
                raise ValidationError(List[err.expected], List[err.actual]) from err

        return point_valid(val)

    return validate


# pylint: disable=too-few-public-methods
class _AsdlAdtBase(ABC):
    @abstractmethod
    def __init__(self):  # pragma: no cover (unreachable)
        assert False, "Should be unreachable."

    def update(self, **kwargs):
        """
        Useful wrapper for creating a copy of an instance of a generated class,
        with only certain fields changed.
        """
        return attrs.evolve(self, **kwargs)


class _BuildClasses(asdl.VisitorBase):
    """A visitor that constructs an IR module from a parsed ASDL tree."""

    _builtin_types = {
        "bool": bool,
        "float": float,
        "int": int,
        "object": object,
        "string": str,
    }

    def __init__(
        self,
        ext_types: Optional[Mapping[str, type]] = None,
        mixin_types: Optional[Mapping[str, type]] = None,
        memoize: Optional[Collection[str]] = None,
    ):
        super().__init__()
        self.module: Optional[ModuleType] = None

        self._mixin_types = mixin_types or {}
        self._memoize = memoize or set()
        self._type_map = {
            **_BuildClasses._builtin_types,
            **(ext_types or {}),
        }
        self._base_types = {}

    @staticmethod
    def _make_function(name: str, args: List[str], body: List[str], **context):
        body = body or ["pass"]
        body = textwrap.indent("\n".join(body), " " * 4)
        source = f'def {name}({", ".join(args)}):\n' + body
        # exec required because Python functions can't have dynamically named arguments.
        exec(source, context)  # pylint: disable=W0122
        return context[name]

    @staticmethod
    def _init_fn(fields: OrderedDict[str, Any]):
        """
        Make an __init__ method that can be injected into a class.
        """
        context = {}
        body = []

        for name, validator in fields.items():
            if validator:
                context[f"_validate_{name}"] = validator
                body.append(f"{name} = _validate_{name}({name})")

            body.append(f"object.__setattr__(self, '{name}', {name})")

        args = ["self"] + list(fields)
        return _BuildClasses._make_function("__init__", args, body, **context)

    @staticmethod
    def _cached_new_fn(supertype, fields):
        new_function = _BuildClasses._make_function(
            "__new__",
            ["cls"] + list(fields),
            ["return super(supertype, cls).__new__(cls)"],
            supertype=supertype,
        )
        return _normalize(functools.lru_cache(maxsize=None)(new_function))

    def _adt_class(self, *, name, base, fields: Union[List[str], OrderedDict]):
        basename = self.module.__name__  # pylint: disable=no-member
        members = {
            **({} if isinstance(fields, list) else {"__init__": self._init_fn(fields)}),
            "__qualname__": f"{basename}.{name}",
            "__annotations__": {f: None for f in fields},
        }

        if mixin := self._mixin_types.get(name):
            base_types = (base, mixin)
        else:
            base_types = (base,)

        cls = attrs.frozen(init=False)(type(name, base_types, members))
        if cls.__name__ in self._memoize:
            cls.__new__ = self._cached_new_fn(cls, fields)
        return cls

    def _visit_fields(self, node, attributes=None):
        validator_map = OrderedDict()
        for field in node.fields + (attributes or []):
            self.visit(field, validator_map)
        return validator_map

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitModule(self, mod: asdl.Module):
        """
        Create a new Python module and populate it with types corresponding to the
        given ASDL definitions.
        """
        self.module = ModuleType(mod.name)

        # Collect top-level names as stub/abstract classes
        for dfn in mod.dfns:
            # The "base" type is the actual, final type for products, but we cannot
            # create validators for the __init__ function until all the types have
            # been created, so we will wait until visitProduct is called later to
            # attach it.
            base_type = self._adt_class(
                name=dfn.name,
                base=_AsdlAdtBase,
                fields=(
                    [f.name for f in dfn.value.fields]
                    if isinstance(dfn.value, asdl.Product)
                    else []
                ),
            )
            setattr(self.module, dfn.name, base_type)
            self._base_types[dfn.name] = base_type
            self._type_map[dfn.name] = base_type

        # Fill in classes
        for dfn in mod.dfns:
            self.visit(dfn)

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitType(self, typ: asdl.Type):
        """
        Forwards to either the sum or product handler
        """
        self.visit(typ.value, self._base_types[typ.name])

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitProduct(self, prod: asdl.Product, base_type):
        """
        Creates a new data type for the current product type and adds it to the module.
        """
        base_type.__init__ = self._init_fn(self._visit_fields(prod))
        base_type.__abstractmethods__ = frozenset(
            set(base_type.__abstractmethods__) - {"__init__"}
        )

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitSum(self, sum_node: asdl.Sum, base_type):
        """
        Adds all the constructors associated with this sum type to the module.
        """
        for t in sum_node.types:
            self.visit(t, base_type, sum_node.attributes)

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitConstructor(self, cons: asdl.Constructor, base_type, attributes):
        """
        Creates a new data type for the current constructor and adds it to the module.
        """
        ctor_type = self._adt_class(
            name=cons.name,
            base=base_type,
            fields=self._visit_fields(cons, attributes),
        )
        setattr(self.module, cons.name, ctor_type)

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitField(self, field: asdl.Field, fields: OrderedDict):
        """
        Updates the "fields" dict with a mapping from field name to validator.
        """
        fields[field.name] = _make_validator(
            self._get_point_validator(field), field.seq, field.opt
        )

    def _get_point_validator(self, field: asdl.Field):
        point_validator = self._type_map[field.type]

        if isinstance(point_validator, type):
            return instance_of(point_validator)

        if isinstance(point_validator, type(Type[object])):
            (typ,) = typing.get_args(point_validator)
            return subclass_of(typ)

        if callable(point_validator):
            return point_validator

        raise ValueError(f"Unknown validator type {type(point_validator)}")


def ADT(  # pylint: disable=invalid-name
    asdl_str: str,
    *,
    ext_types: Optional[Mapping[str, Union[type, Callable]]] = None,
    memoize: Optional[Collection[str]] = None,
    mixin_types: Optional[Mapping[str, type]] = None,
):
    """
    Function that converts an ASDL grammar into a Python Module.

    The returned module will contain one class for every ASDL type
    declared in the input grammar, and one (sub-)class for every
    constructor in each of those types.  These constructors will
    type-check objects on construction to ensure conformity with the
    given grammar.

    ASDL Syntax
    =================
    The grammar of ASDL follows this BNF::

        module      ::= "module" Id "{" [definitions] "}"
        definitions ::= { TypeId "=" type }
        type        ::= product | sum
        product     ::= fields ["attributes" fields]
        fields      ::= "(" { field, "," } field ")"
        field       ::= TypeId ["?" | "*"] [Id]
        sum         ::= constructor { "|" constructor } ["attributes" fields]
        constructor ::= ConstructorId [fields]

    Parameters
    =================
    asdl_str : str
        The ASDL definition string
    ext_types : Optional[Mapping[str, Union[type, Callable]]]
        A mapping of custom type names to Python types. Used to create validators for
        the __init__ method of generated classes. Several built-in types are implied,
        with the following corresponding Python types:
        *   'bool' - bool
        *   'float' - float
        *   'int' - int
        *   'object' - (anything except None)
        *   'string' - str
    memoize : Optional[Collection[str]]
        collection of constructor names to memoize, optional
    mixin_types : Optional[Mapping[str, type]]
        A mapping of generated type names (matching the ASDL productions) to
        mixin classes from which to inherit. This is useful for injecting custom
        methods into the generated classes.

    Returns
    =================
    A newly created module with classes for each ASDL type and constructor

    Example
    =================
    ::

        PolyMod = ADT(\"\"\" module PolyMod {
            expr = Var   ( id    name  )
                 | Const ( float val   )
                 | Sum   ( expr* terms )
                 | Prod  ( float coeff, expr* terms )
                 attributes( string? tag )
        }\"\"\", {
            "id" : lambda x: type(x) is str and str.isalnum(),
        })
    """
    asdl_ast = asdl.ASDLParser().parse(asdl_str)
    assert isinstance(asdl_ast, asdl.Module)

    if mod := sys.modules.get(asdl_ast.name):
        return mod

    builder = _BuildClasses(ext_types, mixin_types, memoize)
    builder.visit(asdl_ast)

    mod = builder.module
    mod.__doc__ = (
        textwrap.dedent(
            """
            ASDL Module generated by asdl_adt
            Original ASDL description:
            """
        )
        + textwrap.dedent(asdl_str)
    )

    sys.modules[asdl_ast.name] = mod

    return mod
