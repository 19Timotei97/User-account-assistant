import logging
import numpy as np

# Package imports
from typing import List, Optional, Tuple
from psycopg2.extras import RealDictCursor
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


def get_embedding_from_db(content: str, collection: str) -> np.ndarray:
    """
    Retrieves the embedding from the database if it exists.

    :param content: The content to look for in the database.
    :param collection: The collection the content belongs to.
    :return: The embedding if found, otherwise None.
    """
    try:
        with get_db_session() as session:
            # Perform a query to retrieve the embedding based on content and collection
            result = session.query(Embedding) \
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
            if result:
                return np.array(result.embedding)
        
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f'Failed to retrieve embedding for question {content} in collection {collection} due to an integrity error')
        raise integrity_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error retrieving embedding from database: {database_exception}")
        raise DatabaseOperationError(f"Failed to retrieve embedding from database: {database_exception}")
    
    except Exception as select_excep:
        logging.error(f"Unexpected error occured when retrieving embedding: {select_excep}")
        raise DatabaseOperationError(f"Unexpected error occured when retrieving embedding: {select_excep}")

    return None


def get_embeddings_from_collection(collection: str, limit: int = 100) -> List[Tuple[str, np.ndarray, str]]:
    """
    Retrieves all embeddings from a specific collection.

    :param collection: The collection to retrieve the embeddings from.
    :param limit: The maximum number of embeddings to retrieve.
    :return: A list of tuples containing the content (question), embedding and the answer.
    """
    try:
        # Run the SQL query using the local session
        with get_db_session() as session:
            results = session.query(Embedding) \
                                .filter(Embedding.collection == collection) \
                                .limit(limit) \
                                .all()

            # Return the list of existing embeddings in the collection
            return [
                (result.content, np.array(result.embedding), result.answer) 
            for result in results]
        
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f'Failed to retrieve embeddings from collection {collection} due to an integrity error')
        raise integrity_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error retrieving embeddings from collection {collection}: {database_exception}")
        raise DatabaseOperationError(f"Failed to retrieve embeddings from collection {collection}: {database_exception}")
    
    except Exception as select_from_collection_excep:
        logging.error(f"Unexpected error when retrieving embeddings from collection {collection}: {select_from_collection_excep}")
        raise DatabaseOperationError(f"Unexpected error when retrieving embeddings from collection {collection}: {select_from_collection_excep}")
    
    return []


def add_embedding_to_db(content: str, answer: str, collection: str) -> None:
    """
    Adds a single embedding to the database.

    :param content: The content to add.
    :param answer: The answer associated with the content.
    :param collection: The collection the content belongs to.
    :return: None
    """
    try:
        # Run the SQL query using the local session
        with get_db_session() as session:
            # Check if the embedding already exists in the database
            existing_embedding = get_embedding_from_db(content, collection)

            if existing_embedding is None:
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

        logging.error(f'Failed to add embedding for question {content} in collection {collection} due to an integrity error')
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error adding embedding to database: {database_exception}")
        raise DatabaseOperationError(f"Failed to add embedding: {database_exception}")

    except Exception as insert_excep:
        logging.error(f"Unexpected error when adding embedding to database: {insert_excep}")
        raise DatabaseOperationError(f"Unexpected error when adding embedding to database: {insert_excep}")


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

                    else:
                        logging.warning(f"Embedding for content '{content}' already exists in collection '{collection}'.")

            # If we actually have stuff to add
            if embeddings_to_insert:
                # Add all objects in a single batch insert
                # SQLAlchemy automatically batches inserts with add_all()
                session.add_all(embeddings_to_insert)

    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f'Failed to add embeddings in collection {collection} due to an integrity error')
        raise integrity_excep
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error adding embeddings to database: {database_exception}")
        raise DatabaseOperationError(f"Failed to add embeddings: {database_exception}")
    
    except Exception as insert_excep:
        logging.error(f"Unexpected error when adding embeddings to database: {insert_excep}")
        raise DatabaseOperationError(f"Unexpected error when adding embeddings to database: {insert_excep}")


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
    try:
        # Run the SQL query using the local Session
        with get_db_session() as session:
            batch_size = int(settings.batch_size)

            for idx in range(0, len(items), batch_size):
                batch = items[idx:idx + batch_size]

                for content, answer, collection in batch:
                    # Check if the embedding already exists in the database
                    existing_embedding = session.query(Embedding) \
                                                .filter(Embedding.content == content, Embedding.collection == collection) \
                                                .first()

                    # If it existed before
                    if existing_embedding is not None:
                        # Compute the new embedding
                        embedding = embeddings_service.compute_embedding(content)

                        # Update the in-memory object
                        existing_embedding.embedding = embedding
                        existing_embedding.answer = answer
                    else:
                        logging.info(f"Embedding for content '{content}' did not exist in collection {collection}. Adding it now...")

                        # If it didn't, add the new embedding
                        add_embedding_to_db(content, answer, collection)
    
    except IntegrityError as integrity_excep:
        session.rollback()  # Rollback if an unexpected integrity error occurs

        logging.error(f'Failed to update embeddings in collection {collection} due to an integrity error')
        raise integrity_excep

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error updating embeddings in database: {database_exception}")
        raise DatabaseOperationError(f"Failed to update embeddings: {database_exception}")
    
    except Exception as update_excep:
        logging.error(f"Unexpected error when updating embeddings in database: {update_excep}")
        raise DatabaseOperationError(f"Unexpected error when updating embeddings in database: {update_excep}")


def search_for_similarity_in_db(
        query_embedding: np.ndarray, 
        collection: str
    ) -> Tuple[Optional[str], Optional[str], float]:
    """
    Searches for the most similar embedding to the query embedding directly in the database.

    Why is this better than an in-memory similiarity search?
    
    1.  The usage of a database query: The similarity search is done using an SQL query that runs on the PostgreSQL database. 
        The embeddings are stored in a table, and the search is performed on this table `(SELECT content, answer, 1 - (embedding <=> %s::vector))`, which returns the most similar result.

    2.  pgvector: The `<=>` operator is specific to `pgvector` for computing the distance between vectors (embeddings). 
        This computation happens inside the database.

    3.  Efficient Vector Search: Since the search is happening directly on the database level, it's more scalable and efficient for large datasets, 
        as it leverages the database's indexing and optimized search capabilities, rather than loading all embeddings into memory.
    
    :param query_embedding: The embedding of the query to search for.
    :param collection: The collection to search within.
    :return: The matched content, answer, and similarity score if a match is found; otherwise None.
    """
    try:
        # Run the SQL query using the local Session
        with get_db_session() as session:
            # A bit of a hack to be able to use pgvector's <=> operator in SQLAlchemy
            # Retrieve the underlying DBAPI connection from the SQLAlchemy engine
            raw_connection = session.connection().connection

            # Create a cursor which returns results as dictionaries
            with raw_connection.cursor(cursor_factory=RealDictCursor) as curs:

                # Query to perform similarity search using pgvector
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
                # Retrieve the fields
                matched_content = result['content']
                matched_answer = result['answer']
                similarity_score = result['similarity']

                logging.info(f"Similarity score: {similarity_score} for content {matched_content}")
                
                return matched_content, matched_answer, similarity_score
    
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

    return None, None, 0.0


def delete_embedding_from_db(content: str, collection: str) -> None:
    """
    Deletes the embedding from the database.
    Checks if the embedding already exists

    :param content: The content to delete from the database.
    :param collection: The collection the content belongs to.
    :return: None
    """
    try:
        with get_db_session() as session:
            # Check if the embedding already exists in the database
            embedding_to_delete = session.query(Embedding) \
                .filter(Embedding.content == content, Embedding.collection == collection) \
                .first()

            # If it existed before
            if embedding_to_delete is not None:
                # Delete that embedding
                session.delete(embedding_to_delete)

            else:
                logging.error(f'The question {content} does not have a stored embedding!')
                raise ValueError(f'Embedding for the question "{content}" not found in collection "{collection}".')
    
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
