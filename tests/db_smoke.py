from repos.order_repo import OrderRepo

if __name__ == "__main__":
    repo = OrderRepo()
    o = repo.create(side="SELL",  symbol="NQ", price=20000.5, qty=2)
    print("INSERTED:", o.id)
    rows = repo.list_recent()
    print("RECENT:", [(r.id, r.side, r.symbol, float(r.price), r.qty, r.status) for r in rows][:3])
