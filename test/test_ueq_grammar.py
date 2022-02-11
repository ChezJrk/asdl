import inspect
from dataclasses import dataclass

import pytest

from asdl_adt import ADT


@dataclass(frozen=True)
class Sym:
    name: str


@pytest.fixture(scope="session")
def ueq_grammar():
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
        {"sym": lambda x: isinstance(x, Sym)},
    )


def _public_names(obj):
    # If a class has __slots__, it does not have a __dict__.
    # Old Python versions do nothing special with __slots__.
    fields = obj.__dict__ or getattr(obj, "__slots__", {})
    return set(filter(lambda x: not x.startswith("_"), fields))


def test_module_names(ueq_grammar):
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
    assert isinstance(ueq_grammar.problem, type)
    assert isinstance(ueq_grammar.pred, type)
    assert isinstance(ueq_grammar.expr, type)

    for case in ("Conj", "Disj", "Cases", "Eq"):
        assert issubclass(getattr(ueq_grammar, case), ueq_grammar.pred)

    for case in ("Const", "Var", "Add", "Scale"):
        assert issubclass(getattr(ueq_grammar, case), ueq_grammar.expr)


def test_module_function_signatures(ueq_grammar):
    def check_args(cls, expected_args):
        real_args = inspect.getfullargspec(cls.__init__)
        assert real_args.args == expected_args
        assert real_args.varargs is None
        assert real_args.varkw is None
        assert real_args.defaults is None
        assert real_args.kwonlyargs == []
        assert real_args.kwonlydefaults is None
        assert real_args.annotations == {}

    check_args(ueq_grammar.problem, ["self", "holes", "knowns", "preds"])

    check_args(ueq_grammar.pred, ["self"])
    check_args(ueq_grammar.Conj, ["self", "preds"])
    check_args(ueq_grammar.Disj, ["self", "preds"])
    check_args(ueq_grammar.Cases, ["self", "case_var", "cases"])
    check_args(ueq_grammar.Eq, ["self", "lhs", "rhs"])

    check_args(ueq_grammar.expr, ["self"])
    check_args(ueq_grammar.Const, ["self", "val"])
    check_args(ueq_grammar.Var, ["self", "name"])
    check_args(ueq_grammar.Add, ["self", "lhs", "rhs"])
    check_args(ueq_grammar.Scale, ["self", "coeff", "e"])


def test_module_abstract_classes(ueq_grammar):
    # TODO: with pytest.raises(TypeError, match='Can\'t instantiate abstract class'):
    with pytest.raises(AssertionError, match=r"pred should never be instantiated"):
        ueq_grammar.pred()

    with pytest.raises(AssertionError, match=r"expr should never be instantiated"):
        ueq_grammar.expr()


def test_create_problem(ueq_grammar):
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
    eq = ueq_grammar.Eq(ueq_grammar.Var(Sym("x")), ueq_grammar.Const(3))
    assert isinstance(eq, ueq_grammar.Eq)
    assert eq.lhs == ueq_grammar.Var(Sym("x"))
    assert eq.rhs == ueq_grammar.Const(3)
    assert _public_names(eq) == {"lhs", "rhs"}

    cases = ueq_grammar.Cases(Sym("y"), [eq])
    assert isinstance(cases, ueq_grammar.Cases)
    assert cases.case_var == Sym("y")
    assert cases.cases == [eq]
    assert _public_names(cases) == {"case_var", "cases"}

    disj = ueq_grammar.Disj([eq])
    assert isinstance(disj, ueq_grammar.Disj)
    assert disj.preds == [eq]
    assert _public_names(disj) == {"preds"}

    conj = ueq_grammar.Conj([eq])
    assert isinstance(conj, ueq_grammar.Conj)
    assert conj.preds == [eq]
    assert _public_names(conj) == {"preds"}


def test_create_expr(ueq_grammar):
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
    with pytest.raises(TypeError, match=r'expected arg 0 "name" to be type "sym"'):
        ueq_grammar.Var("not-a-sym")

    with pytest.raises(
        TypeError, match=r'expected arg 0 "preds\[\]" to be type "UEq\.pred"'
    ):
        ueq_grammar.Conj([3])
