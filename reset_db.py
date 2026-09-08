import os
os.environ["DATABASE_URL"] = "postgresql+psycopg2://keep:keep@localhost:5432/keep"

from sqlalchemy import text
from app.db.session import engine
from app.db.models import Base

def reset_db():
    print("Dropping existing tables...")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS items CASCADE;"))
    
    print("Recreating tables with new schema...")
    Base.metadata.create_all(bind=engine)
    print("Done! The database schema is now up to date.")

if __name__ == "__main__":
    reset_db()
