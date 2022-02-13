"""
Tests that object immutability is respected through the standard Python features.
Of course one can always object.__setattr__, but one should not...
"""

import pytest
from attr.exceptions import FrozenInstanceError


def test_immutable_prod(simple_grammar):
    """
    Test that product types are correctly made immutable
    """
    obj = simple_grammar.prod(3, 4)
    with pytest.raises(FrozenInstanceError):
        obj.x = 10
    with pytest.raises(FrozenInstanceError):
        obj.y = 10


def test_immutable_sum(simple_grammar):
    """
    Test that sum types are correctly made immutable
    """
    obj_a = simple_grammar.A(3)
    with pytest.raises(FrozenInstanceError):
        obj_a.x = 10

    obj_b = simple_grammar.B(3.0)
    with pytest.raises(FrozenInstanceError):
        obj_b.y = 10.0


def test_has_hash(simple_grammar):
    """
    Test that generated classes have hashes
    """
    obj_prod = simple_grammar.prod(3, 4)
    obj_a = simple_grammar.A(3)
    obj_b = simple_grammar.B(3.0)

    assert isinstance(hash(obj_prod), int)
    assert isinstance(hash(obj_a), int)
    assert isinstance(hash(obj_b), int)


def test_hash_is_different(simple_grammar):
    """
    Test that generated classes have different hashes when they are different
    """

    # Different values, easy tests
    assert hash(simple_grammar.prod(0, 1)) != hash(simple_grammar.prod(2, 3))
    assert hash(simple_grammar.A(0)) != hash(simple_grammar.A(1))
    assert hash(simple_grammar.B(0.0)) != hash(simple_grammar.B(1.0))

    # Same field names and arguments, ensures the type is part of the hash
    assert hash(simple_grammar.prod(0, 1)) != hash(simple_grammar.C(0, 1))


def test_equal_objects_equal_hashes(simple_grammar):
    """
    Test that generated classes have equal hashes when they are equal, even when not
    memoized.
    """

    assert hash(simple_grammar.prod(0, 1)) == hash(simple_grammar.prod(0, 1))
    assert hash(simple_grammar.A(0)) == hash(simple_grammar.A(0))
    assert hash(simple_grammar.B(0.0)) == hash(simple_grammar.B(0.0))
