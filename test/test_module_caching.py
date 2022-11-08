"""
Coverage-focused test for object identity of same-named ADT types.
"""

from asdl_adt import ADT


def test_module_caching():
    """
    Test that creating a second module with the same name returns the same
    object identically as the first call
    """

    grammar_a = ADT("module cache_test { foo = ( int bar ) }")
    grammar_b = ADT("module cache_test { foo = ( int bar ) }")
    assert grammar_a is grammar_b
