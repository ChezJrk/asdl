def test_update(simple_grammar):
    obj_before = simple_grammar.C(3, 4)
    obj_after = simple_grammar.C(3, 6)
    assert obj_before.update(y=6) == obj_after


def test_update_memoized(memo_grammar):
    obj_before = memo_grammar.memo_prod(3, 4)
    obj_after = memo_grammar.memo_prod(3, 6)

    obj_updated = obj_before.update(y=6)

    assert obj_updated is obj_after
