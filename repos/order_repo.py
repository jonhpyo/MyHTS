from infra.db import SessionLocal
from models.db_models import Order

class OrderRepo:
    def create(self, *, side, symbol, price, qty, status="WORKING") -> Order:
        with SessionLocal() as s:
            od = Order(side=side, symbol=symbol, price=price, qty=qty, status=status)
            s.add(od)
            s.commit()
            s.refresh(od)
            return od

    def list_recent(self, limit=20):
        with SessionLocal() as s:
            return s.query(Order).order_by(Order.id.desc()).limit(limit).all()

    def update_status(self, order_id: int, status: str):
        with SessionLocal() as s:
            od = s.get(Order, order_id)
            if not od: return None
            od.status = status
            s.commit()
            s.refresh(od)
            return od
