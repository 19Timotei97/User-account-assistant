import logging

# Package imports
from sqlalchemy.exc import DatabaseError, InterfaceError, IntegrityError
from typing import List

# Local files imports
from .base import get_db_session
from .models import Embedding, Collection


"""
This module provides functions to manage collections in the database.

Functions:
- get_collection(collection_name: str): Retrieves a collection from the database by its name.
- get_collections(): Retrieves all collections from the database.
- add_collection(collection_name: str): Adds a new collection to the database.
- update_collection(old_collection_name: str, new_collection_name: str): Updates the collection in the database 
    with the new collection name.
- delete_collection(collection_name: str): Deletes the collection from the database.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_collection_from_db(collection_name: str) -> Collection:
    """
    Retrieves a collection from the database by its name.

    :param collection_name: The name of the collection to retrieve.
    :return: The collection object if found else None.
    """
    try:
        with get_db_session() as session:
            # Run the SQL query using the local session
            collection = session.query(Collection) \
                            .filter(Collection.name == collection_name) \
                            .first()

            if collection is None:
                logging.info(f"Collection '{collection_name}' not found in the database!")
                return None

            return collection

    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f"Failed to retrieve collection '{collection_name}' due to an integrity error.")
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error retrieving collection '{collection_name}' from database: {database_exception}")
        raise database_exception

    return


def get_collections_from_db(limit: int = 100) -> List[Collection]:
    """
    Retrieves all collections from the database.

    :param limit: The maximum number of collections to retrieve.
    :return: A list of collections if found else None.
    """
    try:
        with get_db_session() as session:
            # Run the SQL query using the local session
            collections = session.query(Collection.name) \
                            .distinct() \
                            .limit(limit) \
                            .all()

            # Return the list of collections
            if collections is None:
                logging.info("No collections found in the database!")
                return None
            
            return collections
        
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs
        
        logging.error("Failed to retrieve collections due to an integrity error.")
        raise integrity_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error retrieving collections from database: {database_exception}")
        raise
    
    return


def add_collection_to_db(collection_name: str) -> None:
    """
    Adds a new collection to the database if it doesn't already exist.

    :param collection_name: The name of the collection to add.
    :return: None
    """
    if not collection_name:
        logging.error("Collection name cannot be empty.")
        raise ValueError("Collection name cannot be empty.")

    try:
        # Run the SQL query using the local session
        with get_db_session() as session:
            # Check if the collection already exists
            existing_collection = session.query(Collection.name) \
                .filter(Collection.name == collection_name) \
                .first()

            if existing_collection:
                logging.warning(f"Collection '{collection_name}' already exists.")
                return

            # Add a new embedding with the collection name
            new_collection = Collection(
                name=collection_name
            )

            session.add(new_collection)

            # Attempt to commit the new embedding
            session.commit()

    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs
        
        logging.error(f"Failed to add collection '{collection_name}' due to an integrity error.")
        raise integrity_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error adding collection to database: {database_exception}")
        raise database_exception
    
    return


def update_collection_in_db(old_collection_name: str, new_collection_name: str) -> None:
    """
    Updates the collection in the database with the new collection name.
    Checks if the old collection exists before attempting to update it.

    :param old_collection_name: The name of the collection to update.
    :param new_collection_name: The new name of the collection.
    :return: None
    """
    if not new_collection_name:
        logging.error("New collection name cannot be empty.")
        raise ValueError("New collection name cannot be empty.")

    try:
        with get_db_session() as session:
            # Check if the old collection exists
            old_collection = session.query(Collection.name) \
                                    .filter(Collection.name == old_collection_name) \
                                    .first()
            
            if not old_collection:
                logging.warning(f"Collection '{old_collection_name}' does not exist!")
                return None

            # Update the collection with the new name
            old_collection.name = new_collection_name

            # Retrieve all embeddings from the old collection
            update_collection_objs = session.query(Embedding) \
                                        .filter(Embedding.collection == old_collection_name) \
                                        .all()
            
            # Update their collection name to the new one
            for obj in update_collection_objs:
                obj.collection = new_collection_name

            session.commit()  # Attempt to commit the new collection name
    
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs
        
        logging.error(f"Failed to update collection '{old_collection_name}' with name {new_collection_name} due to an integrity error.")
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error updating collection in database: {database_exception}")
        raise database_exception
    
    return


def delete_collection_from_db(collection_name: str) -> None:
    """
    Deletes the collection from the database and the associated embeddings.
    Checks if the collection exists before attempting to delete it.

    :param collection_name: The name of the collection to delete.
    :return: None
    """
    if not collection_name:
        logging.error("Collection name cannot be empty.")
        raise ValueError("Collection name cannot be empty.")

    try:
        with get_db_session() as session:
            # Check if the collection exists before attempting to delete
            collection_to_delete = session.query(Collection.name) \
                                    .filter(Collection.name == collection_name) \
                                    .first()

            if not collection_to_delete:
                logging.warning(f"Collection '{collection_name}' does not exist!")
                return None
            
            # Retrieve all records with the collection name
            delete_collection_objs = session.query(Embedding) \
                                        .filter(Embedding.collection == collection_name) \
                                        .all()

            # Update the collection name for each record
            for obj in delete_collection_objs:
                session.delete(obj)

            # Also remove the collection from the Collection table
            session.delete(collection_to_delete)

            # Attempt to commit the deleted collection name
            session.commit()
    
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs
        
        logging.error(f"Failed to delete collection '{collection_name}' due to an integrity error.")
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error deleting collection from database: {database_exception}")
        raise

    return
