from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, String, Integer, Numeric, text, TIMESTAMP

class Base(DeclarativeBase): pass

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    side: Mapped[str] = mapped_column(String(8), index=True)   # BUY/SELL
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    price: Mapped[float] = mapped_column(Numeric(18,4))
    qty: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), index=True)  # WORKING/FILLED/CANCELLED
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
