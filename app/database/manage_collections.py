import logging

# Package imports
from typing import List
from psycopg2.sql import SQL
from psycopg2.errors import DatabaseError, InterfaceError, UniqueViolation

# Local files imports
from utils.utils import create_connection


"""
This script provides functions to manage collections in the database.

Functions:
- get_collections(): Retrieves all collections from the database.
- add_collection(collection_name: str): Adds a new collection to the database.
- update_collection(old_collection_name: str, new_collection_name: str): Updates the collection in the database 
    with the new collection name.
- delete_collection(collection_name: str): Deletes the collection from the database.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_collections() -> List:
    """
    Retrieves all collections from the database.

    :return: A list of collections.
    """
    try:
        with create_connection() as conn:
            with conn.cursor() as curs:
                curs.execute("SELECT DISTINCT collection FROM embeddings")
                collections = [row[0] for row in curs.fetchall()]
        
        return collections
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error retrieving collections from database: {database_exception}")
        raise


def add_collection(collection_name: str) -> None:
    """
    Adds a new collection to the database if it doesn't already exist.

    :param collection_name: The name of the collection to add.
    :return: None
    """
    if not collection_name:
        logging.error("Collection name cannot be empty.")
        raise ValueError("Collection name cannot be empty.")

    try:
        with create_connection() as conn:
            with conn.cursor() as curs:
                # Check if collection already exists
                check_collection_existence_query = SQL(
                    "SELECT 1 FROM embeddings WHERE collection = {} LIMIT 1").format(collection_name)
                curs.execute(check_collection_existence_query)
                # curs.execute("SELECT 1 FROM embeddings WHERE collection = %s LIMIT 1", (collection_name,))
                
                if curs.fetchone():
                    logging.warning(f"Collection '{collection_name}' already exists.")
                    return
                
                # Insert the new collection
                collection_insertion_query = SQL(
                    "INSERT INTO embeddings (collection) VALUES ({})").format(collection_name)
                curs.execute(collection_insertion_query)

                # curs.execute(
                #     "INSERT INTO embeddings (collection) VALUES (%s)",
                #     (collection_name,)
                # )
            conn.commit()
    
    except UniqueViolation as unique_violation_excep:
        logging.warning(f"Collection '{collection_name}' already exists!")
        raise unique_violation_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error adding collection to database: {database_exception}")
        raise database_exception


def update_collection(old_collection_name: str, new_collection_name: str) -> None:
    """
    Updates the collection in the database with the new collection name.

    :param old_collection_name: The name of the collection to update.
    :param new_collection_name: The new name of the collection.
    :return: None
    """
    if not new_collection_name:
        logging.error("New collection name cannot be empty.")
        raise ValueError("New collection name cannot be empty.")

    try:
        with create_connection() as conn:
            with conn.cursor() as curs:
                # Check if the old collection exists
                check_collection_existence_query = SQL(
                    "SELECT 1 FROM embeddings WHERE collection = {} LIMIT 1").format(old_collection_name)
                curs.execute(check_collection_existence_query)
                # curs.execute("SELECT 1 FROM embeddings WHERE collection = %s LIMIT 1", (old_collection_name,))
                
                if not curs.fetchone():
                    logging.warning(f"Collection '{old_collection_name}' does not exist.")
                    return

                # Update the collection name
                update_collection_query = SQL(
                    "UPDATE embeddings SET collection = {} WHERE collection = {}").format(new_collection_name, old_collection_name)
                curs.execute(update_collection_query)
                
                # curs.execute(
                #     "UPDATE embeddings SET collection = %s WHERE collection = %s",
                #     (new_collection_name, old_collection_name)
                # )
            conn.commit()
    except UniqueViolation as unique_violation_excep:
        logging.warning(f"Collection '{new_collection_name}' already exists!")
        raise unique_violation_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error updating collection in database: {database_exception}")
        raise database_exception


def delete_collection(collection_name: str) -> None:
    """
    Deletes the collection from the database.

    :param collection_name: The name of the collection to delete.
    :return: None
    """
    if not collection_name:
        logging.error("Collection name cannot be empty.")
        raise ValueError("Collection name cannot be empty.")

    try:
        with create_connection() as conn:
            with conn.cursor() as curs:
                # Check if the collection exists before attempting to delete
                check_collection_existence_query = SQL(
                    "SELECT 1 FROM embeddings WHERE collection = {} LIMIT 1").format(collection_name)
                curs.execute(check_collection_existence_query)
                # curs.execute("SELECT 1 FROM embeddings WHERE collection = %s LIMIT 1", (collection_name,))
                
                if not curs.fetchone():
                    logging.warning(f"Collection '{collection_name}' does not exist.")
                    return

                # Delete the specified collection
                delete_collection_query = SQL(
                    "DELETE FROM embeddings WHERE collection = {}").format(collection_name)
                curs.execute(delete_collection_query)
                
                # curs.execute(
                #     "DELETE FROM embeddings WHERE collection = %s",
                #     (collection_name,)
                # )
            conn.commit()
    
    except UniqueViolation as unique_violation_excep:
        logging.warning(f"Collection '{collection_name}' does not exist!")
        raise unique_violation_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error deleting collection from database: {database_exception}")
        raise
