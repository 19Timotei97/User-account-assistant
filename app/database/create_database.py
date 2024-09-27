import os
import psycopg2
import psycopg2.sql
import time
import logging

# Local files imports
from utils.utils import create_db_connection


"""
This script sets up the database and tables for the contextual FAQ assistant.
It first creates the database if it doesn't exist, then sets up the necessary tables.
The script also includes a retry mechanism for table creation in case of errors.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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
    db_name = os.getenv('POSTGRES_DB')

    # Connect to the default database (postgres)
    try:
        with psycopg2.connect(
            dbname='postgres',
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            host='db',
            port='5432'
        ) as conn:
            # Allow database creation
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            
            with conn.cursor() as curs:
                curs.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                exists = curs.fetchone()
                
                if not exists:
                    curs.execute(f"CREATE DATABASE {psycopg2.sql.Identifier(db_name)}")
                    logging.info(f"Database {db_name} created successfully!")
                else:
                    logging.info(f"Database {db_name} already exists!")
    
    except psycopg2.OperationalError as operational_excep:
        logging.error(f"OperationalError while connecting or creating the database: {operational_excep}")
        raise DatabaseCreationError("Failed to create database due to operational issues") from operational_excep
    
    except psycopg2.DatabaseError as database_excep:
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
            with create_db_connection() as conn:
                with conn.cursor() as curs:

                    # Create the embeddings table
                    curs.execute(
                    """
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
                    """)

                conn.commit()

                logging.info("Database setup completed successfully!")
                return
        
        except psycopg2.OperationalError as operation_excep:
            # Handle connection-related issues
            logging.error(f"Operational error while setting up the database: {operation_excep}")
            
            if retries < max_retries - 1:
                logging.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            
            retries += 1

        except psycopg2.ProgrammingError as programming_excep:
            # Handle SQL-related issues
            logging.error(f"Programming error (SQL issue) while setting up the database: {programming_excep}")
            raise DatabaseSetupError(f"Failed due to a SQL issue: {programming_excep}")

        except psycopg2.DatabaseError as database_excep:
            # General database errors
            logging.error(f"Database error occurred: {database_excep}")
            raise DatabaseSetupError(f"Failed due to a database issue: {database_excep}")

        except psycopg2.Error as general_excep:
            # Catch-all for other psycopg2-related errors
            logging.error(f"General psycopg2 error occurred: {general_excep}")
            raise DatabaseSetupError(f"Failed due to a general psycopg2 issue: {general_excep}")

        except Exception as unexpected_excep:
            # Catch-all for unexpected issues not related to psycopg2
            logging.error(f"An unexpected error occurred: {unexpected_excep}")
            raise DatabaseSetupError(f"An unexpected error occurred: {unexpected_excep}")

    raise Exception(f"Failed to set up the database after {max_retries} attempts.")
