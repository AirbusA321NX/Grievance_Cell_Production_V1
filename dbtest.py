from database import engine, Base
from sqlalchemy import inspect


def reset_database():
    # Drop all tables
    Base.metadata.drop_all(engine)

    # Create all tables
    Base.metadata.create_all(engine)

    # Verify the grievances table structure
    inspector = inspect(engine)
    print("\nColumns in grievances table:")
    for column in inspector.get_columns('grievances'):
        print(f"- {column['name']} ({column['type']})")


if __name__ == "__main__":
    reset_database()
    print("\nDatabase reset complete!")