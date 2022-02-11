"""
Tests of ASDL-ADT's memoization functionality. Memoized constructors always return an
identical node, given equal arguments (which therefore will not necessarily compare
identical via "is" to the resulting object's fields, themselves)
"""

import pytest

import asdl_adt


@pytest.fixture(scope="session", name="memo")
def fixture_memo():
    """
    A test grammar with fully memoized types, partially memoized types, and
    non-memoized types.
    """
    memo_grammar = asdl_adt.ADT(
        """
        module memo {
            memo_prod = ( int x, int y )

            memo_sum = A()
                     | B( int val )

            normal_prod = ( int x, int y )
            normal_sum = C()
                       | D( int val )

            partial_sum = E( int val ) | F()
        }
        """,
    )
    asdl_adt.memo(memo_grammar, ["memo_prod", "A", "B", "E"])
    return memo_grammar


def test_memoization(memo):
    """
    Test that memoized objects are identical (via is) and that non-memoized objects are
    equal (via ==).
    """

    assert memo.memo_prod(3, 4) is memo.memo_prod(3, 4)
    assert memo.memo_prod(3, 4) is not memo.memo_prod(3, 5)

    assert memo.A() is memo.A()
    assert memo.B(3) is memo.B(3)
    assert memo.B(3) is not memo.B(4)

    assert memo.normal_prod(3, 4) is not memo.normal_prod(3, 4)
    assert memo.normal_prod(3, 4) == memo.normal_prod(3, 4)

    assert memo.C() is not memo.C()
    assert memo.C() == memo.C()

    assert memo.D(3) is not memo.D(3)
    assert memo.D(3) == memo.D(3)

    assert memo.E(3) is memo.E(3)

    assert memo.F() is not memo.F()
    assert memo.F() == memo.F()
