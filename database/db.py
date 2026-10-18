import os
from pathlib import Path
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Carrega variáveis de ambiente do .env local ao diretório do Radar Julius se existir
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# 1. Tenta carregar de variáveis de ambiente
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Tenta carregar do st.secrets (usado no Streamlit Community Cloud)
if not DATABASE_URL:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
            DATABASE_URL = st.secrets["DATABASE_URL"]
    except Exception:
        pass

# 3. Fallback seguro
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./radar_julius.db"

# Ajuste para URLs Neon ou Heroku que iniciam com postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuração de engine para SQLite vs PostgreSQL
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # Conexão Neon ou Postgres com pool e pré-ping
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    """Inicializa as tabelas no banco de dados se não existirem."""
    from . import models  # Importa os modelos para garantir registro
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db():
    """Gerador de sessão do banco de dados com tratamento seguro de contexto."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
