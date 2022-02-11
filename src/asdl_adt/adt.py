"""
This is the main parsing and class metaprogramming module in ASDL-ADT.
"""

import sys
import textwrap
from types import ModuleType
from weakref import WeakValueDictionary

import asdl


def _asdl_parse(asdl_str):
    parser = asdl.ASDLParser()
    module = parser.parse(asdl_str)
    return module


def _build_superclasses(asdl_mod):
    classes = {}

    def create_invalid_init():
        def invalid_init(self):
            assert False, f"{type(self).__name__} should never be instantiated"

        return invalid_init

    for name, definition in asdl_mod.types.items():
        if isinstance(definition, asdl.Sum):
            classes[name] = type(name, (), {"__init__": create_invalid_init()})
        elif isinstance(definition, asdl.Product):
            classes[name] = type(name, (), {})
    return classes


_builtin_checks = {
    "string": lambda x: isinstance(x, str),
    "int": lambda x: isinstance(x, int),
    "object": lambda x: x is not None,
    "float": lambda x: isinstance(x, float),
    "bool": lambda x: isinstance(x, bool),
}


def _build_checks(superclasses, ext_checks):
    checks = _builtin_checks.copy()

    def make_check(superclass):
        return lambda x: isinstance(x, superclass)

    for name in ext_checks:
        checks[name] = ext_checks[name]
    for name in superclasses:
        assert name not in checks, f"Name conflict for type '{name}'"
        checks[name] = make_check(superclasses[name])
    return checks


def _build_classes(asdl_mod, ext_checks):
    superclasses = _build_superclasses(asdl_mod)
    check_funcs = _build_checks(superclasses, ext_checks)

    mod = ModuleType(asdl_mod.name)
    # TODO: Investigate how to make generated modules fully native/safe/reliable
    sys.modules[asdl_mod.name] = mod  # register the new module

    err_cls = type(asdl_mod.name + "Err", (Exception,), {})

    def basic_check(i, name, argname, typ, indent="    "):
        typname = typ
        if typ in superclasses:
            typname = asdl_mod.name + "." + typ
        err_msg = f'expected arg {i} "{name}" to be type "{typname}"'
        return (
            f"{indent}if not CHK['{typ}']({argname}):\n"
            f"{indent}    raise TypeError('{err_msg}')"
        )

    def opt_check(i, name, argname, typ, indent="    "):
        subidnt = indent + "    "
        return (
            f"{indent}if {argname} is not None:\n"
            f"{basic_check(i, name, argname, typ, subidnt)}"
        )

    def seq_check(i, name, argname, typ, indent="    "):
        return (
            f"{indent}if not type({argname}) is list:\n"
            f"{indent}    raise TypeError('expected arg {i} \"{name}\" to be a list')\n"
            f"{indent}for j,e in enumerate({argname}):\n"
            f"{basic_check(i, name + '[]', argname + '[j]', typ, indent + '    ')}"
        )

    def create_initfn(cls_name, fields):
        nameargs = ", ".join([f.name for i, f in enumerate(fields)])
        argstr = ", ".join([f"arg_{i}" for i, f in enumerate(fields)])
        checks = "\n".join(
            [
                seq_check(i, f.name, f"arg_{i}", f.type)
                if f.seq
                else (
                    opt_check(i, f.name, f"arg_{i}", f.type)
                    if f.opt
                    else basic_check(i, f.name, f"arg_{i}", f.type)
                )
                for i, f in enumerate(fields)
            ]
        )
        assign = "\n    ".join(
            [f"self.{f.name} = arg_{i}" for i, f in enumerate(fields)]
        )
        if not fields:
            checks = "    pass"
            assign = "pass"

        exec_out = {"Err": err_cls, "CHK": check_funcs}
        exec_str = (
            f"def {cls_name}_init_inner(self,{argstr}):\n"
            f"{checks}\n"
            f"    {assign}\n"
            f"def {cls_name}_init(self,{nameargs}):\n"
            f"    {cls_name}_init_inner(self,{nameargs})"
        )
        # un-comment this line to see what's
        # really going on
        # print(exec_str)
        exec(exec_str, exec_out)
        return exec_out[cls_name + "_init"]

    def create_reprfn(cls_name, fields):
        prints = ",".join([f"{f.name}={{repr(self.{f.name})}}" for f in fields])
        exec_out = {"Err": err_cls}
        exec_str = f"def {cls_name}_repr(self):" f'\n    return f"{cls_name}({prints})"'
        # un-comment this line to see what's
        # really going on
        # print(exec_str)
        exec(exec_str, exec_out)
        return exec_out[cls_name + "_repr"]

    def create_eqfn(cls_name, fields):
        compares = " and ".join(
            ["type(self) is type(o)"]
            + [f"(self.{f.name} == o.{f.name})" for f in fields]
        )
        exec_out = {"Err": err_cls}
        exec_str = f"def {cls_name}_eq(self,o):" f"\n    return {compares}"
        # un-comment this line to see what's
        # really going on
        # print(exec_str)
        exec(exec_str, exec_out)
        return exec_out[cls_name + "_eq"]

    def create_hashfn(cls_name, fields):
        hashes = ",".join(["type(self)"] + [f"self.{f.name}" for f in fields])
        exec_out = {"Err": err_cls}
        exec_str = f"def {cls_name}_hash(self):" f"\n    return hash(({hashes}))"
        # un-comment this line to see what's
        # really going on
        # print(exec_str)
        exec(exec_str, exec_out)
        return exec_out[cls_name + "_hash"]

    def create_prod(cls_name, prod_node):
        cls = superclasses[cls_name]
        fields = prod_node.fields
        cls.__init__ = create_initfn(cls_name, fields)
        cls.__repr__ = create_reprfn(cls_name, fields)
        cls.__eq__ = create_eqfn(cls_name, fields)
        cls.__hash__ = create_hashfn(cls_name, fields)
        cls.__slots__ = tuple(f.name for f in fields)
        cls.__match_args__ = tuple(f.name for f in fields)
        return cls

    def create_sum_constructor(cls_name, supercls, fields):
        return type(
            cls_name,
            (supercls,),
            {
                "__init__": create_initfn(cls_name, fields),
                "__repr__": create_reprfn(cls_name, fields),
                "__eq__": create_eqfn(cls_name, fields),
                "__hash__": create_hashfn(cls_name, fields),
                "__slots__": tuple(f.name for f in fields),
                "__match_args__": tuple(f.name for f in fields),
            },
        )

    def create_sum(type_name, sum_node):
        cls = superclasses[type_name]
        attrs = sum_node.attributes
        for sum_case in sum_node.types:
            ctor = create_sum_constructor(sum_case.name, cls, sum_case.fields + attrs)
            assert not hasattr(
                mod, sum_case.name
            ), f"name '{sum_case.name}' conflict in module '{mod}'"
            setattr(cls, sum_case.name, ctor)
            setattr(mod, sum_case.name, ctor)
        return cls

    for name, definition in asdl_mod.types.items():
        if isinstance(definition, asdl.Product):
            setattr(mod, name, create_prod(name, definition))
        elif isinstance(definition, asdl.Sum):
            setattr(mod, name, create_sum(name, definition))
        else:  # pragma nocover - very defensive
            assert False, "unexpected kind of asdl type"

    return mod


def ADT(asdl_str, ext_checks=None):
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
    ext_checks : dict of functions, optional
        Type-checking functions for all external (undefined) types
        that are not "built-in".
        "built-in" types, and corresponding Python types are
        *   'string' - str
        *   'int' - int
        *   'float' - float
        *   'bool' - bool
        *   'object' - (anything except None)

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
    ext_checks = ext_checks or {}

    asdl_ast = _asdl_parse(asdl_str)
    mod = _build_classes(asdl_ast, ext_checks)
    # cache values in case we might want them
    mod._ext_checks = ext_checks
    mod._ast = asdl_ast
    mod._defstr = asdl_str

    mod.__doc__ = (
        textwrap.dedent(
            """
            ASDL Module generated by asdl_adt
            Original ASDL description:
            """
        )
        + asdl_str
    )
    return mod


_builtin_keymap = {
    "string": lambda x: x,
    "int": lambda x: x,
    "object": lambda x: x,
    "float": lambda x: x,
    "bool": lambda x: x,
}


def _add_memoization(mod, whitelist, ext_key):
    asdl_mod = mod._ast

    keymap = _builtin_keymap.copy()
    for name, function in ext_key.items():
        keymap[name] = function
    for name in asdl_mod.types:
        keymap[name] = id

    def create_listkey(func):
        i = "i" if func.name != "i" else "ii"
        return f"tuple( K['{func.type}']({i}) for {i} in {func.name} ),"

    def create_optkey(func):
        return f"None if {func.name} is None else K['{func.type}']({func.name}),"

    def create_newfn(name, fields):
        if name not in whitelist:
            return
        cls = getattr(mod, name)

        args = ", ".join([f.name for f in fields])
        key = "".join(
            [
                create_listkey(f)
                if f.seq
                else (create_optkey(f) if f.opt else f"K['{f.type}']({f.name}),")
                for f in fields
            ]
        )

        exec_out = {"T": cls, "K": keymap}
        exec_str = (
            f"def {name}_new(cls, {args}):\n"
            f"    key = ({key})\n"
            f"    val = T._memo_cache.get(key)\n"
            f"    if val == None:\n"
            f"        val = super(T,cls).__new__(cls)\n"
            f"        T._memo_cache[key] = val\n"
            f"    return val"
        )
        # un-comment this line to see what's
        # really going on
        # print(exec_str)
        exec(exec_str, exec_out)

        cls._memo_cache = WeakValueDictionary({})
        cls.__new__ = exec_out[name + "_new"]

    def expand_sum(sum_node):
        for constructor in sum_node.types:
            create_newfn(constructor.name, constructor.fields + sum_node.attributes)

    for name, definition in asdl_mod.types.items():
        if isinstance(definition, asdl.Product):
            create_newfn(name, definition.fields)
        elif isinstance(definition, asdl.Sum):
            expand_sum(definition)
        else:  # pragma: nocover - very defensive
            assert False, "unexpected kind of asdl type"


def memo(mod, whitelist, ext_key=None):
    """Function that wraps ADT class constructors with memoization.

    This function should be called right after construction of an ADT
    module.

    Parameters
    =================
    mod : ADT module
        Created by asdl_adt.ADT
    whitelist : list of strings
        Names of every constructor in `mod` that will be memoized.
    ext_key : dict of functions, optional
        Functions for converting external types into key-values for
        memoization. "built-in" type key-functions are built-in.

    Returns
    =================
    Nothing
    """
    ext_key = ext_key or {}
    _add_memoization(mod, whitelist, ext_key)
