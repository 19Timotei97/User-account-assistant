# Package imports
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from threading import local

# Local files imports
from core.config import get_settings
from typing import Generator


# Retrieve the Pydantic settings
settings = get_settings()

# Create a database engine with connection pooling
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,  # Use a queue pool for connection reusage
    pool_size=10, # at most 10 connection in the pool
    max_overflow=20,
    isolation_level="READ_COMMITTED" # important for managing how concurrent transactions interact with each other
)

# Create a session for database transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Definine a a namespace that can store data specific to each thread
thread_local = local()

# Define a declarative base for the database table
Base = declarative_base()

# Create all tables defined in models (optional, can be moved to a migration script)
Base.metadata.create_all(engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Enables context management (resource management) for the database session.
    This ensures that no multiple sessions are created and the session is closed at the end.
    It ensures that the session is properly committed or rolled back in case of exceptions.
    It also defines different sessions for each thread, to ensure concurrency.

    :return: A database session
    """
    # If the thread already defined a session, use that one
    if hasattr(thread_local, 'session'):
        yield thread_local.session
    
    else:
        # Define a new database session
        db_session = SessionLocal()

        # Assign the session to the current thread
        thread_local.session = db_session

        try:
            # Retrieve and commit transactions
            yield db_session
            db_session.commit()
            
        except Exception:
            # In case any exception occurs, rollback changes
            db_session.rollback()
        finally:
            # Close and remove the session
            db_session.close()

            # Delete the session from the thread
            del thread_local.session
