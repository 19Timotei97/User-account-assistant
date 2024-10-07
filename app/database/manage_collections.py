import logging

# Package imports
from sqlalchemy.exc import DatabaseError, InterfaceError, IntegrityError
from typing import List

# Local files imports
from .base import get_db_session
from .models import Embedding


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
        with get_db_session() as session:
            # Run the SQL query using the local session
            result = session.query(Embedding.collection) \
                            .distinct() \
                            .all()

            # Create a list of returned collections
            collections = [row[0] for row in result.fetchall()]
            
            return collections
        
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs
        
        logging.error("Failed to retrieve collections due to an integrity error.")
        raise integrity_excep
    
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
        # Run the SQL query using the local session
        with get_db_session() as session:
            # Check if the collection already exists
            existing_collection = session.query(Embedding.collection) \
                .filter(Embedding.collection == collection_name) \
                .first()

            if existing_collection:
                logging.warning(f"Collection '{collection_name}' already exists.")
                return

            # Add a new embedding with the collection name
            new_embedding = Embedding(
                content="placeholder_content",
                embedding=[0] * 1536,  # placeholder for embedding
                answer="placeholder_answer",
                collection=collection_name
            )

            session.add(new_embedding)

            # Attempt to commit the new embedding
            session.commit()

    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs
        
        logging.error(f"Failed to add collection '{collection_name}' due to an integrity error.")
        raise integrity_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error adding collection to database: {database_exception}")
        raise database_exception


def update_collection(old_collection_name: str, new_collection_name: str) -> None:
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
            old_collection = session.query(Embedding.collection) \
                                    .filter(Embedding.collection == old_collection_name) \
                                    .first()
            
            if not old_collection:
                logging.warning(f"Collection '{old_collection_name}' does not exist.")
                return

            # Retrieve all records with the old collection name
            old_collection_objs = session.query(Embedding) \
                                        .filter(Embedding.collection == old_collection_name) \
                                        .all()

            # Update the collection name for each record
            for obj in old_collection_objs:
                obj.collection = new_collection_name

            session.commit()  # Attempt to commit the new collection name
    
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs
        
        logging.error(f"Failed to update collection '{old_collection_name}' with name {new_collection_name} due to an integrity error.")
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error updating collection in database: {database_exception}")
        raise database_exception


def delete_collection(collection_name: str) -> None:
    """
    Deletes the collection from the database.
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
            collection_to_delete = session.query(Embedding.collection) \
                                    .filter(Embedding.collection == collection_name) \
                                    .first()

            if not collection_to_delete:
                logging.warning(f"Collection '{collection_name}' does not exist.")
                return
            
            # Retrieve all records with the collection name
            delete_collection_objs = session.query(Embedding) \
                                        .filter(Embedding.collection == collection_name) \
                                        .all()

            # Update the collection name for each record
            for obj in delete_collection_objs:
                session.delete(obj)

            # Attempt to commit the deleted collection name
            session.commit()
    
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs
        
        logging.error(f"Failed to delete collection '{collection_name}' due to an integrity error.")
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error deleting collection from database: {database_exception}")
        raise
