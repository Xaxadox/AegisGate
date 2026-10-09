from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from src.core.config import settings

# URL de conexao dinamica definida via settings (SQLite em dev/testes ou MySQL)
SQLALCHEMY_DATABASE_URL = settings.sqlalchemy_database_url

# Argumentos de engine adaptativos: check_same_thread apenas para SQLite
engine_kwargs = {"pool_pre_ping": True}
if "sqlite" in SQLALCHEMY_DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    """Base declarativa moderna compativel com tipagem do SQLAlchemy 2.0."""
    pass

# Dependência do FastAPI (Injeção de Dependência)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
