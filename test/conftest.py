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
