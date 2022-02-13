"""
This is the main parsing and class metaprogramming module in ASDL-ADT.
"""
import abc
import textwrap
from abc import ABC, abstractmethod
from collections import OrderedDict
from functools import cache
from types import ModuleType
from typing import Type, Any, Mapping, Optional, Collection

import asdl
import attrs


def _no_init(self):
    pass


def _make_validator(typ: Type[Any], seq: bool, opt: bool):
    def validate(x):
        if (
            (opt and x is None)
            or (not seq and isinstance(x, typ))
            or (seq and isinstance(x, list) and all(isinstance(y, typ) for y in x))
        ):
            return

        expected = typ.__qualname__
        if seq:
            expected = f"List[{expected}]"
        actual = type(x).__qualname__

        raise TypeError(f"expected: {expected}, actual: {actual}")

    return staticmethod(validate)


@attrs.frozen
class _AsdlAdtBase(ABC):
    def update(self, **kwargs):
        return attrs.evolve(self, **kwargs)


class BuildClasses(asdl.VisitorBase):
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
            **BuildClasses._builtin_types,
            **(ext_types or {}),
        }
        self._base_types = {}

    def _make_init(self, fields: Optional[OrderedDict[str, Any]]):
        """
        Make an __init__ method that can be injected into a class. Must use exec
        because dynamic Python functions cannot have named arguments.
        """

        if fields is None:
            return abstractmethod(_no_init)

        globals_dict = {}
        init_lines = []

        for name, validator in fields.items():
            if validator:
                globals_dict[f"_validate_{name}"] = validator
                init_lines.append(f"_validate_{name}({name})")

            init_lines.append(f"object.__setattr__(self, '{name}', {name})")

        init_lines = init_lines or ["pass"]
        exec(
            textwrap.dedent(
                """
                def __init__(self, {args}):
                {body}
                """
            ).format(
                args=", ".join(fields),
                body=textwrap.indent("\n".join(init_lines), "    "),
            ),
            globals_dict,
        )

        return globals_dict["__init__"]

    def _maybe_memoize(self, typ: type):
        if typ.__name__ in self._memoize:

            @cache
            def new_fn(inner_cls, *_, **__):
                return super(typ, inner_cls).__new__(inner_cls)

            typ.__new__ = new_fn

    def _make_class(self, name: str, base: type, fields, **kwargs):
        return attrs.frozen(
            type(
                name,
                (base,),
                {
                    "__init__": self._make_init(fields),
                    "__qualname__": f"{self.module.__name__}.{name}",
                    "__annotations__": {f: None for f in (fields or ())},
                    **kwargs,
                },
            )
        )

    def _make_base_type(self, typ: asdl.Type) -> type:
        if isinstance(typ.value, asdl.Product):
            # The "base" type is the actual, final type for products, so tell
            # attrs which fields to create now.
            fields = {field.name: None for field in typ.value.fields}
        else:
            fields = {}

        base_type = self._make_class(
            typ.name, _AsdlAdtBase, None, __annotations__=fields
        )
        self._maybe_memoize(base_type)
        return base_type

    # noinspection PyPep8Naming
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
    def visitType(self, typ: asdl.Type):
        # Forward to Sum or Product
        self.visit(typ.value, self._base_types[typ.name])

    # noinspection PyPep8Naming
    def visitProduct(self, prod: asdl.Product, base_type: Type[ABC]):
        fields = OrderedDict()
        for f in prod.fields:
            self.visit(f, fields)

        base_type.__init__ = self._make_init(fields)
        abc.update_abstractmethods(base_type)

    # noinspection PyPep8Naming
    def visitSum(self, sum_node: asdl.Sum, base_type: Type[ABC]):
        for t in sum_node.types:
            self.visit(t, base_type)

    # noinspection PyPep8Naming
    def visitConstructor(self, cons: asdl.Constructor, base_type: Type[ABC]):
        fields = OrderedDict()
        for f in cons.fields:
            self.visit(f, fields)

        ctor_type = self._make_class(cons.name, base_type, fields)
        self._maybe_memoize(ctor_type)
        setattr(self.module, cons.name, ctor_type)

    # noinspection PyPep8Naming
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

    builder = BuildClasses(ext_types, memoize)
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
