import logging
import numpy as np

# Package imports
from typing import List, Optional, Tuple
from psycopg2.extras import RealDictCursor
from sqlalchemy.orm import Session
from sqlalchemy.exc import DatabaseError, InterfaceError, IntegrityError

# Local files imports
from .base import get_db_session
from celery_config.tasks import celery
from core.config import get_settings
from .models import Embedding
from services.embeddings_service import OpenAIEmbeddingsService


"""
This script provides functions to interact with the database.
It handles the creation of the database connection and the storage of embeddings.
The functions are designed to be used in the context of the application.
The database is used to store the embeddings of the content to avoid recomputing them each time the application is run.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve the environment variables as settings
settings = get_settings()

# Initialize the embeddings model
embeddings_service = OpenAIEmbeddingsService()


class DatabaseOperationError(Exception):
    """
    Custom exception for database operations.
    This exception is raised when there is an error interacting with the database.
    """
    pass


def get_embedding_from_db(content: str, collection: str) -> Embedding:
    """
    Retrieves the embedding from the database if it exists.

    :param content: The content to look for in the database.
    :param collection: The collection the content belongs to.
    :return: The embedding if found, otherwise None.
    """
    if not content or not collection:
        logging.error("Content and collection name are required to retrieve an embedding.")
        raise ValueError("Content and collection name cannot be empty.")

    try:
        with get_db_session() as session:
            # Perform a query to retrieve the embedding based on content and collection
            embedding = session.query(Embedding) \
                            .filter(Embedding.content == content, Embedding.collection == collection) \
                            .first()
            
            # Or like this
            # result = session.execute(
            #     select(
            #         Embedding.content,
            #         Embedding.embedding,
            #         Embedding.answer
            #     ).where(Embedding.content == content, Embedding.collection == collection)
            # ).fetchone()

            # Retrieve the question's embedding and its associated answer
            if not embedding:
                logging.info(f"No embedding found for question '{content}' in collection '{collection}'.")
            
            return embedding
        
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f"Failed to retrieve embedding for question '{content}' in collection '{collection}' due to an integrity error")
        raise integrity_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error retrieving embedding from database: {database_exception}")
        raise DatabaseOperationError(f"Failed to retrieve embedding from database: {database_exception}")
    
    except Exception as select_excep:
        logging.error(f"Unexpected error occured when retrieving embedding: {select_excep}")
        raise DatabaseOperationError(f"Unexpected error occured when retrieving embedding: {select_excep}")

    return None


def get_embeddings_from_collection(collection: str, limit: int = 100) -> List[Embedding]:
    """
    Retrieves all embeddings from a specific collection.

    :param collection: The collection to retrieve the embeddings from.
    :param limit: The maximum number of embeddings to retrieve.
    :return: A list of Embedding objects or None if an error occurs.
    """
    if not collection:
        logging.error("Collection name is required to retrieve embeddings.")
        raise ValueError("Collection name cannot be empty.")

    try:
        # Run the SQL query using the local session
        with get_db_session() as session:
            embeddings = session.query(Embedding) \
                                .filter(Embedding.collection == collection) \
                                .limit(limit) \
                                .all()

            # Return the list of existing embeddings in the collection
            if not embeddings:
                logging.info(f"No embeddings found for the collection '{collection}'.")

            return embeddings
        
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f"Failed to retrieve embeddings from collection '{collection}' due to an integrity error")
        raise integrity_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error retrieving embeddings from collection {collection}: {database_exception}")
        raise DatabaseOperationError(f"Failed to retrieve embeddings from collection {collection}: {database_exception}")
    
    except Exception as select_from_collection_excep:
        logging.error(f"Unexpected error when retrieving embeddings from collection {collection}: {select_from_collection_excep}")
        raise DatabaseOperationError(f"Unexpected error when retrieving embeddings from collection {collection}: {select_from_collection_excep}")
    
    return None


def add_embedding_to_db(content: str, answer: str, collection: str) -> None:
    """
    Adds a single embedding to the database.

    :param content: The content to add.
    :param answer: The answer associated with the content.
    :param collection: The collection the content belongs to.
    :return: None
    """
    if not content or not answer or not collection:
        logging.error("Content, answer, and collection name are required to add an embedding.")
        raise ValueError("Content, answer, and collection name cannot be empty.")

    try:
        # Run the SQL query using the local session
        with get_db_session() as session:
            # Check if the embedding already exists in the database
            existing_embedding = get_embedding_from_db(content, collection)

            if existing_embedding is None:
                logging.info(f"Adding embedding for content '{content}' to collection '{collection}'...")

                # Compute the embedding for the content
                content_embedding = embeddings_service.compute_embedding(content)

                # Create an SQLAlchemy object
                embedding_object = Embedding(
                    content=content,
                    embedding=content_embedding,
                    answer=answer,
                    collection=collection
                )

                # Add the object to the session
                session.add(embedding_object)

                logging.info(f"Added embedding for content '{content}' to collection '{collection}'.")
            
            else:
                logging.warning(f"Embedding for content '{content}' already exists in collection '{collection}'.")
                return
    
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f"Failed to add embedding for question '{content}' in collection '{collection}' due to an integrity error")
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error adding embedding to database: {database_exception}")
        raise DatabaseOperationError(f"Failed to add embedding: {database_exception}")

    except Exception as insert_excep:
        logging.error(f"Unexpected error when adding embedding to database: {insert_excep}")
        raise DatabaseOperationError(f"Unexpected error when adding embedding to database: {insert_excep}")

    return


@celery.task
def add_embeddings_to_db(items: List[Tuple[str, str, str]]) -> None:
    """
    Adds embeddings to the database in batches, specified by the batch size Pydantic setting.
    It handles large batches by splitting them into smaller chunks.
    It checks if the embedding already exists in the database before inserting it.
    The @celery.task decorator is used to make this function a Celery task, allowing it to be executed asynchronously.

    :param items: A list of tuples containing the content (question), answer and collection for each embedding.
    :return: None
    """
    if not items or 0 == len(items):
        logging.error("No items provided to add embeddings.")
        raise ValueError("Items cannot be empty.")

    try:
        # Run the SQL query using the local Session
        with get_db_session() as session:
            batch_size = int(settings.batch_size)

            for idx in range(0, len(items), batch_size):
                batch = items[idx:idx + batch_size]

                embeddings_to_insert = []

                for content, answer, collection in batch:
                    # Check if the embedding already exists in the database
                    existing_embedding = get_embedding_from_db(content, collection)

                    # If it didn't exist before
                    if existing_embedding is None:
                        # Compute the new embedding
                        content_embedding = embeddings_service.compute_embedding(content)
                        
                        # Create an SQLAlchemy object
                        embedding_object = Embedding(
                            content=content,
                            embedding=content_embedding,
                            answer=answer,
                            collection=collection
                        )
                        
                        # Append it to the list of objects
                        embeddings_to_insert.append(embedding_object)

                        logging.info(f"Added embedding for content '{content}' to the list to add to collection '{collection}'")

                    else:
                        logging.warning(f"Embedding for content '{content}' already exists in collection '{collection}'!")
                        return

            # If we actually have stuff to add
            if embeddings_to_insert:
                # Add all objects in a single batch insert
                # SQLAlchemy automatically batches inserts with add_all()
                session.add_all(embeddings_to_insert)

                logging.info(f"Added {len(embeddings_to_insert)} embeddings to the database.")

    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f"Failed to add embeddings in collection '{collection}' due to an integrity error")
        raise integrity_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error adding embeddings to database: {database_exception}")
        raise DatabaseOperationError(f"Failed to add embeddings: {database_exception}")
    
    except Exception as insert_excep:
        logging.error(f"Unexpected error when adding embeddings to database: {insert_excep}")
        raise DatabaseOperationError(f"Unexpected error when adding embeddings to database: {insert_excep}")

    return


@celery.task
def update_embeddings_in_db(items: List[Tuple[str, str, str]]) -> None:
    """
    Updates the embeddings in the database in batches, using the batch size Pydantic setting.
    It handles large batches by splitting them into smaller chunks.
    It checks if the embedding already exists in the database before updating it.
    The @celery.task decorator is used to make this function a Celery task, allowing it to be executed asynchronously.

    :param items: A list of tuples containing the content (question), answer and collection for each embedding.
    :return: None
    """
    if not items or 0 == len(items):
        logging.error("No items provided to update embeddings.")
        raise ValueError("Items cannot be empty.")

    try:
        # Run the SQL query using the local Session
        with get_db_session() as session:
            batch_size = int(settings.batch_size)

            for idx in range(0, len(items), batch_size):
                batch = items[idx:idx + batch_size]

                for content, answer, collection in batch:
                    # Check if the embedding already exists in the database
                    existing_embedding = get_embedding_from_db(content, collection)

                    # If it existed before
                    if existing_embedding is not None:
                        # Compute the new embedding
                        embedding = embeddings_service.compute_embedding(content)

                        # Update the in-memory object
                        existing_embedding.embedding = embedding
                        existing_embedding.answer = answer
                    else:
                        logging.info(f"Cannot update embedding for content '{content}' because it does not exist in collection '{collection}'!")
                        return
    
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f"Failed to update embeddings in collection '{collection}' due to an integrity error")
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error updating embeddings in database: {database_exception}")
        raise DatabaseOperationError(f"Failed to update embeddings: {database_exception}")
    
    except Exception as update_excep:
        logging.error(f"Unexpected error when updating embeddings in database: {update_excep}")
        raise DatabaseOperationError(f"Unexpected error when updating embeddings in database: {update_excep}")

    return


def search_for_similarity_in_db(
        session: Session,
        query_embedding: np.ndarray, 
        collection: str
    ) -> Tuple[Embedding, float]:
    """
    Searches for the most similar embedding to the query embedding directly in the database.

    Why is this better than an in-memory similiarity search?
    
    1.  The usage of a database query: The similarity search is done using an SQL query that runs on the PostgreSQL database. 
        The embeddings are stored in a table, and the search is performed on this table `(SELECT content, answer, 1 - (embedding <=> %s::vector))`, which returns the most similar result.

    2.  pgvector: The `<=>` operator is specific to `pgvector` for computing the distance between vectors (embeddings). 
        This computation happens inside the database.

    3.  Efficient Vector Search: Since the search is happening directly on the database level, it's more scalable and efficient for large datasets, 
        as it leverages the database's indexing and optimized search capabilities, rather than loading all embeddings into memory.
    
    :param session: The database session to use for the search.
    :param query_embedding: The embedding of the query to search for.
    :param collection: The collection to search within.
    :return: An Embedding object and similarity score if a match is found; otherwise None.
    """
    if not session:
        logging.error("No database session provided to search for similarity.")
        raise ValueError("Database session cannot be empty.")
    
    if not query_embedding or not collection:
        logging.error("Query embedding and collection name are required to search for similarity.")
        raise ValueError("Query embedding and collection name cannot be empty.")

    try:
        # A bit of a hack to be able to use pgvector's <=> operator in SQLAlchemy
        # Retrieve the underlying DBAPI connection from the SQLAlchemy engine
        raw_connection = session.connection().connection

        # Create a cursor which returns results as dictionaries
        with raw_connection.cursor(cursor_factory=RealDictCursor) as curs:

            # It sorts the most similar embeddings to the prompt embedding (by using pgvector's <=> operator) descendingly
            search_query = """
                SELECT content, answer, 1 - (embedding <=> %s::vector) AS similarity
                FROM embeddings
                WHERE collection = %s
                ORDER BY similarity DESC
                LIMIT 1;
            """

            # Execute the query using the cursor
            curs.execute(
                search_query,
                (query_embedding, collection)
            )

            # Grab a single result from the query
            result = curs.fetchone()

        # If we actually get a result
        if result:
            # Retrieve the embedding for the matched content
            embedding = get_embedding_from_db(result['content'], collection)

            # Construct an Embedding object
            similar_embedding = Embedding(
                content=result['content'],
                embedding=embedding,
                answer=result['answer'],
                collection=collection
            )

            # Retrieve the similarity score
            similarity_score = result['similarity']

            logging.info(f"Similarity score: {similarity_score} for content {similar_embedding.content}")
            
            return similar_embedding, similarity_score
    
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f'Failed to search for similarity in collection {collection} due to an integrity error')
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error searching for similarity in the database: {database_exception}")
        raise DatabaseOperationError(f"Failed to search for similarity: {database_exception}")
    
    except Exception as similiarity_search_error:
        logging.error(f"Unexpected error when searching for similarity in the database: {similiarity_search_error}")
        raise DatabaseOperationError(f"Unexpected error when searching for similarity in the database: {similiarity_search_error}")

    return None, 0.0


def delete_embedding_from_db(content: str, collection: str) -> Embedding:
    """
    Deletes the embedding from the database.
    Checks if the embedding already exists

    :param content: The content to delete from the database.
    :param collection: The collection the content belongs to.
    :return: The Embedding object that was deleted, or None if it didn't exist.
    """
    if not content or not collection:
        logging.error("Content and collection name are required to delete an embedding.")
        raise ValueError("Content and collection name cannot be empty.")

    try:
        # Prepare the embedding object that will be deleted
        embedding_to_return = None
        
        with get_db_session() as session:
            # Check if the embedding already exists in the database
            embedding_to_delete = get_embedding_from_db(content, collection)

            # If it existed before
            if embedding_to_delete is not None:
                # Save the embedding object that will be deleted
                embedding_to_return = embedding_to_delete

                logging.info(f"Deleting embedding for content '{content}' from collection '{collection}'")
                
                # Delete that embedding
                session.delete(embedding_to_delete)

                return embedding_to_return

            else:
                logging.error(f'The question {content} does not have a stored embedding!')
                raise ValueError(f'Embedding for the question "{content}" not found in collection "{collection}"!')
    
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f'Failed to delete embedding from collection {collection} due to an integrity error')
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error deleting embedding from database: {database_exception}")
        raise DatabaseOperationError(f"Failed to delete embedding: {database_exception}")
    
    except Exception as delete_excep:
        logging.error(f"Unexpected error when deleting embedding from database: {delete_excep}")
        raise DatabaseOperationError(f"Unexpected error when deleting embedding from database: {delete_excep}")

    return
