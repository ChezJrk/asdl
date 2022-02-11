"""
A module for parsing ASDL grammars into Python Class hierarchies
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
    scs = {}

    def create_invalid_init():
        def invalid_init(self):
            assert False, f"{type(self).__name__} should never be instantiated"

        return invalid_init

    for nm, v in asdl_mod.types.items():
        if isinstance(v, asdl.Sum):
            scs[nm] = type(nm, (), {"__init__": create_invalid_init()})
        elif isinstance(v, asdl.Product):
            scs[nm] = type(nm, (), {})
    return scs


_builtin_checks = {
    "string": lambda x: isinstance(x, str),
    "int": lambda x: isinstance(x, int),
    "object": lambda x: x is not None,
    "float": lambda x: isinstance(x, float),
    "bool": lambda x: isinstance(x, bool),
}


def _build_checks(scs, ext_checks):
    checks = _builtin_checks.copy()

    def make_check(superclass):
        return lambda x: isinstance(x, superclass)

    for nm in ext_checks:
        checks[nm] = ext_checks[nm]
    for nm in scs:
        assert nm not in checks, f"Name conflict for type '{nm}'"
        sc = scs[nm]
        checks[nm] = make_check(sc)
    return checks


def _build_classes(asdl_mod, ext_checks):
    SC = _build_superclasses(asdl_mod)
    CHK = _build_checks(SC, ext_checks)

    mod = ModuleType(asdl_mod.name)
    # TODO: Investigate how to make generated modules fully native/safe/reliable
    sys.modules[asdl_mod.name] = mod  # register the new module

    Err = type(asdl_mod.name + "Err", (Exception,), {})

    def basic_check(i, name, argname, typ, indent="    "):
        typname = typ
        if typ in SC:
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

    def create_initfn(C_name, fields):
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

        exec_out = {"Err": Err, "CHK": CHK}
        exec_str = (
            f"def {C_name}_init_inner(self,{argstr}):\n"
            f"{checks}\n"
            f"    {assign}\n"
            f"def {C_name}_init(self,{nameargs}):\n"
            f"    {C_name}_init_inner(self,{nameargs})"
        )
        # un-comment this line to see what's
        # really going on
        # print(exec_str)
        exec(exec_str, exec_out)
        return exec_out[C_name + "_init"]

    def create_reprfn(C_name, fields):
        prints = ",".join([f"{f.name}={{repr(self.{f.name})}}" for f in fields])
        exec_out = {"Err": Err}
        exec_str = f"def {C_name}_repr(self):" f'\n    return f"{C_name}({prints})"'
        # un-comment this line to see what's
        # really going on
        # print(exec_str)
        exec(exec_str, exec_out)
        return exec_out[C_name + "_repr"]

    def create_eqfn(C_name, fields):
        compares = " and ".join(
            ["type(self) is type(o)"]
            + [f"(self.{f.name} == o.{f.name})" for f in fields]
        )
        exec_out = {"Err": Err}
        exec_str = f"def {C_name}_eq(self,o):" f"\n    return {compares}"
        # un-comment this line to see what's
        # really going on
        # print(exec_str)
        exec(exec_str, exec_out)
        return exec_out[C_name + "_eq"]

    def create_hashfn(C_name, fields):
        hashes = ",".join(["type(self)"] + [f"self.{f.name}" for f in fields])
        exec_out = {"Err": Err}
        exec_str = f"def {C_name}_hash(self):" f"\n    return hash(({hashes}))"
        # un-comment this line to see what's
        # really going on
        # print(exec_str)
        exec(exec_str, exec_out)
        return exec_out[C_name + "_hash"]

    def create_prod(name, prod_node):
        C = SC[name]
        fields = prod_node.fields
        C.__init__ = create_initfn(name, fields)
        C.__repr__ = create_reprfn(name, fields)
        C.__eq__ = create_eqfn(name, fields)
        C.__hash__ = create_hashfn(name, fields)
        C.__slots__ = tuple(f.name for f in fields)
        C.__match_args__ = tuple(f.name for f in fields)
        return C

    def create_sum_constructor(cname, ty, fields):
        return type(
            cname,
            (ty,),
            {
                "__init__": create_initfn(cname, fields),
                "__repr__": create_reprfn(cname, fields),
                "__eq__": create_eqfn(cname, fields),
                "__hash__": create_hashfn(cname, fields),
                "__slots__": tuple(f.name for f in fields),
                "__match_args__": tuple(f.name for f in fields),
            },
        )

    def create_sum(type_name, sum_node):
        T = SC[type_name]
        afields = sum_node.attributes
        for c in sum_node.types:
            C = create_sum_constructor(c.name, T, c.fields + afields)
            assert not hasattr(
                mod, c.name
            ), f"name '{c.name}' conflict in module '{mod}'"
            setattr(T, c.name, C)
            setattr(mod, c.name, C)
        return T

    for nm, t in asdl_mod.types.items():
        if isinstance(t, asdl.Product):
            setattr(mod, nm, create_prod(nm, t))
        elif isinstance(t, asdl.Sum):
            setattr(mod, nm, create_sum(nm, t))
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
    for nm, fn in ext_key.items():
        keymap[nm] = fn
    for nm in asdl_mod.types:
        keymap[nm] = id

    def create_listkey(f):
        i = "i" if f.name != "i" else "ii"
        return f"tuple( K['{f.type}']({i}) for {i} in {f.name} ),"

    def create_optkey(f):
        return f"None if {f.name} is None else K['{f.type}']({f.name}),"

    def create_newfn(name, fields):
        if name not in whitelist:
            return
        ty = getattr(mod, name)

        args = ", ".join([f.name for f in fields])
        key = "".join(
            [
                create_listkey(f)
                if f.seq
                else (create_optkey(f) if f.opt else f"K['{f.type}']({f.name}),")
                for f in fields
            ]
        )

        exec_out = {"T": ty, "K": keymap}
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

        ty._memo_cache = WeakValueDictionary({})
        ty.__new__ = exec_out[name + "_new"]

    def expand_sum(sum_node):
        attrs = sum_node.attributes
        for c in sum_node.types:
            create_newfn(c.name, c.fields + attrs)

    for nm, t in asdl_mod.types.items():
        if isinstance(t, asdl.Product):
            create_newfn(nm, t.fields)
        elif isinstance(t, asdl.Sum):
            expand_sum(t)
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
