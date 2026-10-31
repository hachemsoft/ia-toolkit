from orders import get_order, total


def test_total_in_euros():
    assert total(get_order(1)) == 22.5


def test_unknown_order():
    try:
        get_order(99)
    except KeyError as exc:
        assert "Not found" in str(exc)
