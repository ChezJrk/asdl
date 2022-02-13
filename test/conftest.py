import pytest

from asdl_adt import ADT


@pytest.fixture(scope="session")
def simple_grammar():
    """
    A simple grammar for testing
    """
    return ADT(
        """
        module UEq {
            prod = ( int x, int y )
            sum = A( int x ) 
                | B( float y )
                | C( int x, int y )
        }
        """
    )


@pytest.fixture(scope="session")
def memo_grammar():
    """
    A test grammar with fully memoized types, partially memoized types, and
    non-memoized types.
    """
    return ADT(
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
        memoize={"memo_prod", "A", "B", "E"},
    )
