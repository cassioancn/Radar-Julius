from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from .db import Base

class TrackedProduct(Base):
    """Produto ou nicho monitorado ativamente pelo Radar Julius (por busca ou por URL específica)."""
    __tablename__ = "tracked_products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    niche = Column(String(100), default="Geral", index=True)
    target_drop_pct = Column(Float, default=10.0)  # Queda mínima em % para alerta
    last_best_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    user_cep = Column(String(10), nullable=True)
    user_city = Column(String(100), nullable=True)
    user_state = Column(String(5), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)

    # Suporte a monitoramento de Link Web Específico
    target_url = Column(Text, nullable=True)
    is_url_specific = Column(Boolean, default=False)
    image_url = Column(Text, nullable=True)
    store_name = Column(String(100), nullable=True)

    # Relacionamentos
    captures = relationship("PriceCapture", back_populates="product", cascade="all, delete-orphan")
    historical_top = relationship("HistoricalTopPrice", back_populates="product", cascade="all, delete-orphan", order_by="HistoricalTopPrice.rank")
    notifications = relationship("NotificationLog", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TrackedProduct(id={self.id}, name='{self.name}', target_drop={self.target_drop_pct}%, is_url={self.is_url_specific})>"


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
    """Registro de alertas de queda de preço disparados."""
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("tracked_products.id"), nullable=False)
    store_name = Column(String(100), nullable=False)
    old_price = Column(Float, nullable=False)
    new_price = Column(Float, nullable=False)
    drop_pct = Column(Float, nullable=False)
    status = Column(String(50), default="sent")  # sent, failed, pending
    channel = Column(String(50), default="whatsapp")
    sent_at = Column(DateTime, default=datetime.utcnow)
    response_payload = Column(Text, nullable=True)


class Coupon(Base):
    """Cupons de desconto ativos para Mercado Livre, Shopee, Amazon e outros marketplaces."""
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    store = Column(String(100), nullable=False, index=True)  # Mercado Livre, Shopee, Amazon, Magalu
    code = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    discount_description = Column(String(255), nullable=False)
    category = Column(String(100), default="Geral")
    min_spend = Column(Float, nullable=True)
    discount_value = Column(Float, nullable=True)
    discount_type = Column(String(20), default="percent")  # 'percent' ou 'fixed'
    rules = Column(Text, nullable=True)
    url = Column(Text, nullable=False)
    badge = Column(String(100), nullable=True)
    verified_active = Column(Boolean, default=True)
    last_verified_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Coupon(store='{self.store}', code='{self.code}', discount='{self.discount_description}')>"


class ShoppingBasket(Base):
    """Cesta de compras salva pelo usuário para otimização multi-mercados."""
    __tablename__ = "shopping_baskets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), default="Minha Cesta de Compras")
    user_city = Column(String(100), nullable=True)
    user_state = Column(String(5), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("BasketItem", back_populates="basket", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ShoppingBasket(id={self.id}, name='{self.name}', items={len(self.items)})>"


class BasketItem(Base):
    """Item individual pertencente a uma cesta de compras."""
    __tablename__ = "basket_items"

    id = Column(Integer, primary_key=True, index=True)
    basket_id = Column(Integer, ForeignKey("shopping_baskets.id"), nullable=False, index=True)
    item_name = Column(String(255), nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String(20), default="un")  # un, kg, L

    basket = relationship("ShoppingBasket", back_populates="items")

    def __repr__(self):
        return f"<BasketItem(name='{self.item_name}', qty={self.quantity} {self.unit})>"
