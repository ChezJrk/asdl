"""
Tests of mixin class feature
"""

import pytest

from asdl_adt import ADT


def test_basic_mixin():
    """
    Test that a basic mixin class is properly injected into the given sum type
    alternative, and not the others.
    """

    class MixinA:  # pylint: disable=C0115,C0116,R0903
        def double(self):
            return self.update(x=2 * self.x)

    mixin_grammar = ADT(
        """
        module test_basic_mixin {
            prod = ( int x, int y )
            sum = A( int x )
                | B( float y )
                | C( int x, int y )
        }
        """,
        mixin_types={
            "A": MixinA,
        },
    )

    obj = mixin_grammar.A(3)
    assert obj.double() == mixin_grammar.A(6)

    with pytest.raises(AttributeError, match="'B' object has no attribute 'double'"):
        mixin_grammar.B(3.14).double()
