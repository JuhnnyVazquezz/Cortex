from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# CAMBIA 'tupassword' POR TU CONTRASEÑA REAL DE POSTGRESQL
# Si tu usuario no es 'postgres', cámbialo también.
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:123@localhost/cortex_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()