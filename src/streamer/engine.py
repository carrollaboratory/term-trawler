from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    "postgresql+psycopg://postgres:temp_password@localhost:5432/term-trawler",
    future=True,
)

LocalSession = sessionmaker(bind=engine, future=True)
