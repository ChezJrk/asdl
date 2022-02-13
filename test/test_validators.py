"""
Tests of validator edge cases
"""

# pylint: disable=no-member

import pytest

import asdl_adt


def test_object_is_not_none():
    """
    Test that "object"-typed fields may not be none
    """
    test_adt = asdl_adt.ADT("module test_adt { foo = ( object x ) }")

    assert isinstance(test_adt.foo(3), test_adt.foo)
    assert isinstance(test_adt.foo("bar"), test_adt.foo)

    with pytest.raises(TypeError, match="expected: object, actual: NoneType"):
        test_adt.foo(None)


def test_optional_may_be_none():
    """
    Test that _optional_ "object"-typed fields _may_ be none
    """
    test_adt = asdl_adt.ADT("module test_adt { foo = ( object? x ) }")
    assert isinstance(test_adt.foo(None), test_adt.foo)
