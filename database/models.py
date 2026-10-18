from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from .db import Base

class TrackedProduct(Base):
    """Produto ou nicho monitorado ativamente pelo Radar Julius."""
    __tablename__ = "tracked_products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    niche = Column(String(100), default="Geral", index=True)
    target_drop_pct = Column(Float, default=10.0)  # Queda mínima em % para alerta
    last_best_price = Column(Float, nullable=True)
    user_cep = Column(String(10), nullable=True)
    user_city = Column(String(100), nullable=True)
    user_state = Column(String(5), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)

    # Relacionamentos
    captures = relationship("PriceCapture", back_populates="product", cascade="all, delete-orphan")
    historical_top = relationship("HistoricalTopPrice", back_populates="product", cascade="all, delete-orphan", order_by="HistoricalTopPrice.rank")

    def __repr__(self):
        return f"<TrackedProduct(id={self.id}, name='{self.name}', target_drop={self.target_drop_pct}%)>"


class PriceCapture(Base):
    """Registro individual de captura de preço de uma loja em uma data/hora."""
    __tablename__ = "price_captures"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("tracked_products.id"), nullable=False, index=True)
    store_name = Column(String(100), nullable=False, index=True)
    store_type = Column(String(50), default="retail")  # 'retail' ou 'supermarket'
    product_title = Column(String(500), nullable=False)
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)
    discount_pct = Column(Float, nullable=True)
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    location_city = Column(String(100), nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)

    product = relationship("TrackedProduct", back_populates="captures")

    def __repr__(self):
        return f"<PriceCapture(store='{self.store_name}', price={self.price}, date='{self.captured_at}')>"


class HistoricalTopPrice(Base):
    """Os 3 melhores preços históricos de todos os tempos de cada produto monitorado."""
    __tablename__ = "historical_top_prices"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("tracked_products.id"), nullable=False, index=True)
    rank = Column(Integer, nullable=False)  # 1, 2 ou 3
    store_name = Column(String(100), nullable=False)
    product_title = Column(String(500), nullable=False)
    price = Column(Float, nullable=False)
    url = Column(Text, nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("TrackedProduct", back_populates="historical_top")

    def __repr__(self):
        return f"<HistoricalTopPrice(rank={self.rank}, store='{self.store_name}', price={self.price})>"


class NotificationLog(Base):
    """Registro de alertas de queda de preço disparados via n8n."""
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("tracked_products.id"), nullable=False)
    store_name = Column(String(100), nullable=False)
    old_price = Column(Float, nullable=False)
    new_price = Column(Float, nullable=False)
    drop_pct = Column(Float, nullable=False)
    status = Column(String(50), default="sent")  # sent, failed, pending
    channel = Column(String(50), default="n8n_webhook")
    sent_at = Column(DateTime, default=datetime.utcnow)
    response_payload = Column(Text, nullable=True)

