"""
This is the main parsing and class metaprogramming module in ASDL-ADT.
"""
import abc
import functools
import inspect
import textwrap
from abc import ABC, abstractmethod
from collections import OrderedDict
from functools import cache
from types import ModuleType
from typing import Type, Any, Mapping, Optional, Collection, List

import asdl
import attrs


def _no_init(self):
    pass


def _normalize(func):
    sig = inspect.signature(func)

    @functools.wraps(func)
    def _func(*args, **kwargs):
        ba = sig.bind(*args, **kwargs)
        args, kwargs = ba.args, ba.kwargs
        return func(*args, **kwargs)

    return _func


def _make_validator(typ: Type[Any], seq: bool, opt: bool):
    def validate(val):
        if (
            (opt and val is None)
            or (not seq and isinstance(val, typ))
            or (seq and isinstance(val, list) and all(isinstance(y, typ) for y in val))
        ):
            return

        expected = typ.__qualname__
        if seq:
            expected = f"List[{expected}]"
        actual = type(val).__qualname__

        raise TypeError(f"expected: {expected}, actual: {actual}")

    return staticmethod(validate)


class _AsdlAdtBase(ABC):
    @abstractmethod
    def __init__(self):
        pass

    def update(self, **kwargs):
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
        memoize: Optional[Collection[str]] = None,
    ):
        super().__init__()
        self.module = None
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
    def _make_init(fields: List[str], validators: List[Any]):
        """
        Make an __init__ method that can be injected into a class.
        """
        assert len(fields) == len(validators)

        context = {}
        body = []

        for name, validator in zip(fields, validators):
            if validator:
                context[f"_validate_{name}"] = validator
                body.append(f"_validate_{name}({name})")

            body.append(f"object.__setattr__(self, '{name}', {name})")

        args = ["self"] + list(fields)
        return _BuildClasses._make_function("__init__", args, body, **context)

    @staticmethod
    def _make_cached_new(cls, fields):
        new_function = _BuildClasses._make_function(
            "__new__",
            ['cls'] + list(fields),
            ["return super(typ, cls).__new__(cls)"],
            typ=cls,
        )
        return _normalize(cache(new_function))

    def _make_class(
        self,
        *,
        name: str,
        base: type,
        fields: List[str],
        init: Optional[Any],
        **kwargs,
    ):
        init = {"__init__": init} if init else {}
        cls = attrs.frozen(
            type(
                name,
                (base,),
                {
                    **init,
                    "__qualname__": f"{self.module.__name__}.{name}",
                    "__annotations__": {f: None for f in fields},
                    **kwargs,
                },
            )
        )
        if cls.__name__ in self._memoize:
            cls.__new__ = self._make_cached_new(cls, fields)
        return cls

    def _make_base_type(self, typ: asdl.Type) -> type:
        if isinstance(typ.value, asdl.Product):
            return self._make_class(
                name=typ.name,
                base=_AsdlAdtBase,
                fields=[f.name for f in typ.value.fields],
                # The "base" type is the actual, final type for products, but the
                # init function cannot create validators until all the types have
                # been created, so skip creating it for now (will be attached in
                # visitProduct).
                init=None,
            )
        else:
            # Sum type superclass
            return self._make_class(
                name=typ.name,
                base=_AsdlAdtBase,
                fields=[],
                init=abstractmethod(_no_init),
            )

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitModule(self, mod: asdl.Module):
        self.module = ModuleType(mod.name)

        # Collect top-level names as stub/abstract classes
        for dfn in mod.dfns:
            base_type = self._make_base_type(dfn)
            setattr(self.module, dfn.name, base_type)
            self._base_types[dfn.name] = base_type
            self._type_map[dfn.name] = base_type

        # Fill in classes
        for dfn in mod.dfns:
            self.visit(dfn)

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitType(self, typ: asdl.Type):
        # Forward to Sum or Product
        self.visit(typ.value, self._base_types[typ.name])

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitProduct(self, prod: asdl.Product, base_type: Type[ABC]):
        fields = OrderedDict()
        for f in prod.fields:
            self.visit(f, fields)

        base_type.__init__ = self._make_init(fields.keys(), fields.values())
        abc.update_abstractmethods(base_type)

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitSum(self, sum_node: asdl.Sum, base_type: Type[ABC]):
        for t in sum_node.types:
            self.visit(t, base_type)

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitConstructor(self, cons: asdl.Constructor, base_type: Type[ABC]):
        fields = OrderedDict()
        for f in cons.fields:
            self.visit(f, fields)

        ctor_type = self._make_class(
            name=cons.name,
            base=base_type,
            fields=fields.keys(),
            init=self._make_init(fields.keys(), fields.values()),
        )
        setattr(self.module, cons.name, ctor_type)

    # noinspection PyPep8Naming
    # pylint: disable=invalid-name
    def visitField(self, field: asdl.Field, fields: OrderedDict):
        fields[field.name] = _make_validator(
            self._type_map[field.type], field.seq, field.opt
        )


def ADT(
    asdl_str: str,
    ext_types: Optional[Mapping[str, type]] = None,
    memoize: Optional[Collection[str]] = None,
):
    """Function that converts an ASDL grammar into a Python Module.

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
    ext_types : Optional[Mapping[str, type]]
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

    Returns
    =================
    module
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

    builder = _BuildClasses(ext_types, memoize)
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
    return mod
