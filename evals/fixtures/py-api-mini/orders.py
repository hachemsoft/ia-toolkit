ORDERS = {1: [{"price": 10.0, "qty": 2}, {"price": 2.5, "qty": 1}]}


def total(items):
    """Total of an order, in euros."""
    return sum(item["price"] * item["qty"] for item in items)


def get_order(order_id):
    if order_id not in ORDERS:
        raise KeyError("Not found")
    return ORDERS[order_id]
