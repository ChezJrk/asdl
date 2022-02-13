import pytest
from attr.exceptions import FrozenInstanceError


def test_immutable_prod(simple_grammar):
    p = simple_grammar.prod(3, 4)
    with pytest.raises(FrozenInstanceError):
        p.x = 10
    with pytest.raises(FrozenInstanceError):
        p.y = 10


def test_immutable_sum(simple_grammar):
    a = simple_grammar.A(3)
    with pytest.raises(FrozenInstanceError):
        a.x = 10

    b = simple_grammar.B(3.0)
    with pytest.raises(FrozenInstanceError):
        b.y = 10.0


def test_has_hash(simple_grammar):
    p = simple_grammar.prod(3, 4)
    a = simple_grammar.A(3)
    b = simple_grammar.B(3.0)

    print(hash(p))
    print(hash(a))
    print(hash(b))


def test_hash_is_different(simple_grammar):
    assert hash(simple_grammar.prod(0, 1)) != hash(simple_grammar.prod(2, 3))
    assert hash(simple_grammar.A(0)) != hash(simple_grammar.A(1))
    assert hash(simple_grammar.B(0.0)) != hash(simple_grammar.B(1.0))
    assert hash(simple_grammar.prod(0, 1)) != hash(simple_grammar.C(0, 1))


def test_equal_objects_equal_hashes(simple_grammar):
    assert hash(simple_grammar.prod(0, 1)) == hash(simple_grammar.prod(0, 1))
    assert hash(simple_grammar.A(0)) == hash(simple_grammar.A(0))
    assert hash(simple_grammar.B(0.0)) == hash(simple_grammar.B(0.0))
