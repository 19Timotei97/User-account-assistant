import logging
import time

# Package imports
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, DatabaseError, ProgrammingError, SQLAlchemyError

# Local files imports
from core.config import get_settings


"""
This script sets up the database and tables for the contextual FAQ assistant.
It first creates the database if it doesn't exist, then sets up the necessary tables.
The script also includes a retry mechanism for table creation in case of errors.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve the environment variables as settings
settings = get_settings()


class DatabaseCreationError(Exception):
    """
    Custom exception for database creation errors.
    This exception is raised when there is an error creating the database.
    """
    pass


class DatabaseSetupError(Exception):
    """
    Custom exception for database setup errors.
    This exception is raised when there is an error setting up the database.
    """
    pass


def create_database_if_not_exists() -> None:
    """
    Creates the database if it doesn't exist.
    This method ensures that the database exists before the app tries to access it.

    :return: None
    """
    db_name = settings.postgres_db
    db_user = settings.postgres_user
    db_password = settings.postgres_password
    db_host = settings.postgres_host
    db_port = settings.postgres_port

    # Connect to the default database (postgres)
    try:
        logging.info("Trying to create the database if it doesn't exist...")

        # Create the default postgres URL
        default_database_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/postgres"

        # Connect to the default database (postgres)
        init_engine = create_engine(default_database_url)

        with init_engine.connect() as conn:
            # Allow database creation
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")

            # Check for database existence first
            database_existence = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname=:db_name"), 
                {"db_name": db_name}
            )
            
            if not database_existence.fetchone():
                conn.execute(text("CREATE DATABASE {db_name}"))
                logging.info(f"Database {db_name} created successfully!")

            else:
                logging.info(f"Database {db_name} already exists!")

    except OperationalError as operational_excep:
        logging.error(f"OperationalError while connecting or creating the database: {operational_excep}")
        raise DatabaseCreationError("Failed to create database due to operational issues") from operational_excep
    
    except DatabaseError as database_excep:
        logging.error(f"DatabaseError: {database_excep}")
        raise DatabaseCreationError("Failed to create the database") from database_excep
    
    except Exception as database_creation_excep:
        logging.error(f"An unexpected error occurred when creating the database: {database_creation_excep}")
        raise database_creation_excep


def setup_database(max_retries: int = 5, retry_delay: int = 5) -> None:
    """
    Sets up the database by creating the necessary tables if they don't exist.
    It also tries to create the database altogheter if it doesn't exist.

    Keeping collections within the same table as embeddings, by storing the collection name alongside the embedding data. 
    The main downside is potential inefficiency with larger datasets, but for this specific use-case is the easiest choice.

    :param max_retries: Maximum number of retries for table creation
    :param retry_delay: Delay in seconds between retries
    :return: None
    """
    create_database_if_not_exists()

    # Set a retry mechanism for table creation
    retries = 0

    while retries < max_retries:
        try:
            # Create an engine to connect to the database
            engine = create_engine(settings.database_url)

            # Create the needed table and extension
            with engine.connect() as conn:

                conn = conn.execution_options(isolation_level="AUTOCOMMIT")

                # Check if the embeddings table already exists
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.tables 
                        WHERE table_name = 'embeddings'
                    );
                """))

                table_exists = result.scalar()

                if not table_exists:
                    logging.info("Creating embeddings table...")

                    # Create the embeddings table
                    conn.execute(text("""
                        CREATE EXTENSION IF NOT EXISTS vector;
                        
                        CREATE TABLE IF NOT EXISTS embeddings (
                            id SERIAL PRIMARY KEY,
                            content TEXT NOT NULL,
                            embedding vector(1536),
                            answer TEXT NOT NULL,
                            collection VARCHAR(255) NOT NULL
                        );

                        CREATE INDEX IF NOT EXISTS embeddings_collection_idx ON embeddings(collection);
                        
                        CREATE INDEX IF NOT EXISTS embeddings_vector_idx ON embeddings USING ivfflat (embedding vector_cosine_ops);
                    """))

                    logging.info("Embeddings table created successfully!")
                else:
                    logging.info("Embeddings table already exists!")

            logging.info("Database setup completed successfully!")
            return
        
        except OperationalError as operation_excep:
            # Handle connection-related issues
            logging.error(f"Operational error while setting up the database: {operation_excep}")
            
            if retries < max_retries - 1:
                logging.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            
            retries += 1

        except ProgrammingError as programming_excep:
            # Handle SQL-related issues
            logging.error(f"Programming error (SQL issue) while setting up the database: {programming_excep}")
            raise DatabaseSetupError(f"Failed due to a SQL issue: {programming_excep}")

        except DatabaseError as database_excep:
            # General database errors
            logging.error(f"Database error occurred: {database_excep}")
            raise DatabaseSetupError(f"Failed due to a database issue: {database_excep}")

        except SQLAlchemyError as general_excep:
            # Catch-all for other sqlalchemy-related errors
            logging.error(f"General sqlalchemy error occurred: {general_excep}")
            raise DatabaseSetupError(f"Failed due to a general sqlalchemy issue: {general_excep}")

        except Exception as unexpected_excep:
            # Catch-all for unexpected issues not related to sqlalchemy
            logging.error(f"An unexpected error occurred: {unexpected_excep}")
            raise DatabaseSetupError(f"An unexpected error occurred: {unexpected_excep}")

    raise Exception(f"Failed to set up the database after {max_retries} attempts.")
