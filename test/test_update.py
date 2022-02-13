"""
Test incremental update functionality
"""


def test_update(simple_grammar):
    """
    Test that update produces equal objects on non-memoized grammars
    """
    obj_before = simple_grammar.C(3, 4)
    obj_after = simple_grammar.C(3, 6)
    assert obj_before.update(y=6) == obj_after


def test_update_memoized_product(memo_grammar):
    """
    Test that update produces identical objects on memoized products
    """
    obj_before = memo_grammar.memo_prod(3, 4)
    obj_after = memo_grammar.memo_prod(3, 6)

    obj_updated = obj_before.update(y=6)

    assert obj_updated == obj_after
    assert obj_updated is obj_after


def test_update_memoized_sum(memo_grammar):
    """
    Test that update produces identical objects on memoized sum
    """
    obj_before = memo_grammar.B(3, 4)
    obj_after = memo_grammar.B(3, 6)

    obj_updated = obj_before.update(y=6)

    assert obj_updated == obj_after
    assert obj_updated is obj_after
