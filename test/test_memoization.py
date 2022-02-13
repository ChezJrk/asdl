"""
Tests of ASDL-ADT's memoization functionality. Memoized constructors always return an
identical node, given equal arguments (which therefore will not necessarily compare
identical via "is" to the resulting object's fields, themselves)
"""


def test_memoization(memo_grammar):
    """
    Test that memoized objects are identical (via is) and that non-memoized objects are
    equal (via ==).
    """

    assert memo_grammar.memo_prod(3, 4) is memo_grammar.memo_prod(3, 4)
    assert memo_grammar.memo_prod(3, 4) is not memo_grammar.memo_prod(3, 5)

    assert memo_grammar.A() is memo_grammar.A()
    assert memo_grammar.B(3, 4) is memo_grammar.B(3, 4)
    assert memo_grammar.B(3, 4) is not memo_grammar.B(4, 4)

    assert memo_grammar.normal_prod(3, 4) is not memo_grammar.normal_prod(3, 4)
    assert memo_grammar.normal_prod(3, 4) == memo_grammar.normal_prod(3, 4)

    assert memo_grammar.C() is not memo_grammar.C()
    assert memo_grammar.C() == memo_grammar.C()

    assert memo_grammar.D(3) is not memo_grammar.D(3)
    assert memo_grammar.D(3) == memo_grammar.D(3)

    assert memo_grammar.E(3) is memo_grammar.E(3)

    assert memo_grammar.F() is not memo_grammar.F()
    assert memo_grammar.F() == memo_grammar.F()


def test_memoized_kwargs(memo_grammar):
    """
    Test that the caching mechanism correctly handles keyword arguments
    """
    assert memo_grammar.B(3, 4) is memo_grammar.B(x=3, y=4)
