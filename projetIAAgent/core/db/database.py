from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./cv_agent.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def migrate_sqlite_schema():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "candidates" not in tables:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("candidates")}
    statements = []

    if "is_fit" not in existing_columns:
        statements.append(
            "ALTER TABLE candidates ADD COLUMN is_fit BOOLEAN DEFAULT 1"
        )
    if "rejection_reason" not in existing_columns:
        statements.append(
            "ALTER TABLE candidates ADD COLUMN rejection_reason TEXT"
        )

    if not statements:
        statements = []

    if "job_profiles" in tables:
        job_profile_columns = {column["name"] for column in inspector.get_columns("job_profiles")}
        if "required_languages" not in job_profile_columns:
            statements.append(
                "ALTER TABLE job_profiles ADD COLUMN required_languages TEXT DEFAULT '[]'"
            )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
