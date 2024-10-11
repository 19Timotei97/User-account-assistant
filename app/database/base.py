import logging

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


"""
This module defines the engine and session for database operations.
It also creates the database tables based on the defined models.

It defines the 'get_db_session' method for returning a database session, which is used in the routes.
The session is managed using a context manager to ensure proper commit and rollback operations.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# Define a declarative base for the database table
Base = declarative_base()

# Create all tables defined in models
Base.metadata.create_all(engine)

# Definine a a namespace that can store data specific to each thread
thread_local = local()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Provides a database session.
    This ensures proper session management, including commit, rollback, and closure.
    It also defines different sessions for each thread to ensure concurrency.
    It uses the contextmanager decorator to ensure proper usage of the session in a 'with' statement.

    With the `@contextmanager` decorator:
        - the logic **before** the `yield` acts as the `__enter__` method.
        - the logic **after** the `yield` acts as the `__exit__` method, which includes cleanup operations.

    :return: A database session object.
    """
    # If the thread already defined a session, use that one
    if hasattr(thread_local, 'session') and thread_local.session is not None:
        yield thread_local.session
        return
    
    # Define a new database session
    db_session = SessionLocal()

    # Assign the session to the current thread
    thread_local.session = db_session

    try:
        # Retrieve and commit transactions
        yield db_session # Yield control to the block inside the 'with' statement
        db_session.commit()
        
    except Exception as session_excep:
        # In case any exception occurs, rollback changes
        db_session.rollback()
        
        logging.error(f"Error occurred in database session: {session_excep}")
        
        raise session_excep
    
    finally:
        # Close and remove the session
        db_session.close()

        # Delete the session from the thread
        del thread_local.session
