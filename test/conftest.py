"""
Common fixtures defining grammars that are reused across multiple tests
"""
from types import ModuleType

import pytest

from asdl_adt import ADT


@pytest.fixture(scope="session")
def public_names():
    """
    A helper function for getting the set of public fields of a Python object
    """

    def _public_names(obj):
        # The module will use the __dict__ property here by necessity, but all the
        # generated classes ought to use __slots__ for efficiency.
        fields = obj.__dict__ if isinstance(obj, ModuleType) else obj.__slots__
        return set(filter(lambda x: not x.startswith("_"), fields))

    return _public_names


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
                     | B( int x, int y )

            normal_prod = ( int x, int y )
            normal_sum = C()
                       | D( int val )

            partial_sum = E( int val ) | F()
        }
        """,
        memoize={"memo_prod", "A", "B", "E"},
    )
