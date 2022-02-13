"""
Test data structure invariants in a real-world grammar.
"""

import inspect
from dataclasses import dataclass

import pytest

from asdl_adt import ADT


@dataclass(frozen=True)
class Sym:
    """
    A simple wrapper around a string for testing custom type validation.
    """

    name: str


@pytest.fixture(scope="session", name="ueq_grammar")
def fixture_ueq_grammar():
    """
    A grammar representing a unification equation from the SYSTL project.
    """

    return ADT(
        """
        module UEq {
            problem = ( sym*  holes,   -- symbols the solution is requested for
                        sym*  knowns,  -- symbols allowed in solution expressions
                        pred* preds    -- conj of equations
                      )

            pred = Conj( pred* preds )
                 | Disj( pred* preds )
                 | Cases( sym case_var, pred* cases )
                 | Eq( expr lhs, expr rhs )

            expr = Const( int val )
                 | Var( sym name )
                 | Add( expr lhs, expr rhs )
                 | Scale( int coeff, expr e )
        }
        """,
        {"sym": Sym},
    )


def _public_names(obj):
    # If a class has __slots__, it does not have a __dict__.
    # Old Python versions do nothing special with __slots__.
    fields = getattr(obj, "__dict__", getattr(obj, "__slots__", {}))
    return set(filter(lambda x: not x.startswith("_"), fields))


def test_module_names(ueq_grammar):
    """
    Test that the generated module has the exact set of expected exports.
    """

    assert _public_names(ueq_grammar) == {
        "problem",
        "pred",
        "Conj",
        "Disj",
        "Cases",
        "Eq",
        "expr",
        "Const",
        "Var",
        "Add",
        "Scale",
    }


def test_module_subtyping(ueq_grammar):
    """
    Test that generated classes have the expected subtyping relationships.
    """

    assert isinstance(ueq_grammar.problem, type)
    assert isinstance(ueq_grammar.pred, type)
    assert isinstance(ueq_grammar.expr, type)

    for case in ("Conj", "Disj", "Cases", "Eq"):
        assert issubclass(getattr(ueq_grammar, case), ueq_grammar.pred)

    for case in ("Const", "Var", "Add", "Scale"):
        assert issubclass(getattr(ueq_grammar, case), ueq_grammar.expr)


def test_module_function_signatures(ueq_grammar):
    """
    Test that generated constructors have the expected arguments in the expected order
    """

    test_cases = [
        (ueq_grammar.problem, ["self", "holes", "knowns", "preds"]),
        (ueq_grammar.pred, ["self"]),
        (ueq_grammar.Conj, ["self", "preds"]),
        (ueq_grammar.Disj, ["self", "preds"]),
        (ueq_grammar.Cases, ["self", "case_var", "cases"]),
        (ueq_grammar.Eq, ["self", "lhs", "rhs"]),
        (ueq_grammar.expr, ["self"]),
        (ueq_grammar.Const, ["self", "val"]),
        (ueq_grammar.Var, ["self", "name"]),
        (ueq_grammar.Add, ["self", "lhs", "rhs"]),
        (ueq_grammar.Scale, ["self", "coeff", "e"]),
    ]

    for (cls, expected_args) in test_cases:
        real_args = inspect.getfullargspec(cls.__init__)
        assert real_args.args == expected_args
        assert real_args.varargs is None
        assert real_args.varkw is None
        assert real_args.defaults is None
        assert real_args.kwonlyargs == []
        assert real_args.kwonlydefaults is None
        assert real_args.annotations == {}


def test_module_abstract_classes(ueq_grammar):
    """
    That that superclasses are abstract (i.e. cannot be directly instantiated)
    """

    # TODO: with pytest.raises(TypeError, match='Can\'t instantiate abstract class'):
    abc_err = r"Can't instantiate abstract class \w+ with abstract method __init__"
    with pytest.raises(TypeError, match=abc_err):
        ueq_grammar.pred()

    with pytest.raises(TypeError, match=abc_err):
        ueq_grammar.expr()


def test_create_empty_problem(ueq_grammar):
    """
    Simple test to create a product type with empty lists.
    """
    problem = ueq_grammar.problem([], [], [])
    assert isinstance(problem, ueq_grammar.problem)
    assert problem.holes == []
    assert problem.preds == []
    assert problem.knowns == []


def test_create_problem(ueq_grammar):
    """
    Test that constructed problem instances have the expected structure
    """

    problem = ueq_grammar.problem(
        [Sym("x")],
        [Sym("y")],
        [ueq_grammar.Eq(ueq_grammar.Var(Sym("x")), ueq_grammar.Var(Sym("y")))],
    )
    assert isinstance(problem, ueq_grammar.problem)
    assert problem.holes == [Sym("x")]
    assert problem.knowns == [Sym("y")]
    assert problem.preds == [
        ueq_grammar.Eq(ueq_grammar.Var(Sym("x")), ueq_grammar.Var(Sym("y")))
    ]
    assert _public_names(problem) == {"holes", "knowns", "preds"}


def test_create_pred(ueq_grammar):
    """
    Test that constructed predicates have the expected structure
    """

    eq_node = ueq_grammar.Eq(ueq_grammar.Var(Sym("x")), ueq_grammar.Const(3))
    assert isinstance(eq_node, ueq_grammar.Eq)
    assert eq_node.lhs == ueq_grammar.Var(Sym("x"))
    assert eq_node.rhs == ueq_grammar.Const(3)
    assert _public_names(eq_node) == {"lhs", "rhs"}

    cases = ueq_grammar.Cases(Sym("y"), [eq_node])
    assert isinstance(cases, ueq_grammar.Cases)
    assert cases.case_var == Sym("y")
    assert cases.cases == [eq_node]
    assert _public_names(cases) == {"case_var", "cases"}

    disj = ueq_grammar.Disj([eq_node])
    assert isinstance(disj, ueq_grammar.Disj)
    assert disj.preds == [eq_node]
    assert _public_names(disj) == {"preds"}

    conj = ueq_grammar.Conj([eq_node])
    assert isinstance(conj, ueq_grammar.Conj)
    assert conj.preds == [eq_node]
    assert _public_names(conj) == {"preds"}


def test_create_expr(ueq_grammar):
    """
    Test that constructed expressions have the expected structure
    """

    const = ueq_grammar.Const(3)
    assert isinstance(const, ueq_grammar.Const)
    assert const.val == 3
    assert _public_names(const) == {"val"}

    var = ueq_grammar.Var(Sym("foo"))
    assert isinstance(var, ueq_grammar.Var)
    assert var.name == Sym("foo")
    assert _public_names(var) == {"name"}

    add = ueq_grammar.Add(var, const)
    assert isinstance(add, ueq_grammar.Add)
    assert add.lhs == var and add.rhs == const
    assert _public_names(add) == {"lhs", "rhs"}

    scale = ueq_grammar.Scale(5, var)
    assert isinstance(scale, ueq_grammar.Scale)
    assert scale.coeff == 5 and scale.e == var
    assert _public_names(scale) == {"coeff", "e"}


def test_invalid_arg_type_throws(ueq_grammar):
    """
    Test that generated data type constructors validate the types of their arguments.
    """

    with pytest.raises(TypeError, match=r"expected: Sym, actual: str"):
        ueq_grammar.Var("not-a-sym")

    with pytest.raises(TypeError, match=r"expected: List\[UEq\.pred\], actual: list"):
        ueq_grammar.Conj([3])
