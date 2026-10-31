def order_payload(row):
    return {"id": row["order_id"], "customer": row["customer_id"], "amount": row["amount"]}
