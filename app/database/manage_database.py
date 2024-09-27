import os
import logging
import json
import numpy as np

# Package imports
from typing import List, Optional, Tuple
from psycopg2.sql import SQL
from psycopg2.extras import execute_values, execute_batch
from psycopg2.errors import DatabaseError, InterfaceError

# Local files imports
from celery_config.tasks import celery
from services.embeddings_service import OpenAIEmbeddingsService
from utils.utils import create_db_connection


"""
This script provides functions to interact with the database.
It handles the creation of the database connection and the storage of embeddings.
The functions are designed to be used in the context of the application.
The database is used to store the embeddings of the content to avoid recomputing them each time the application is run.
"""


# Initialize the embeddings model
embeddings_service = OpenAIEmbeddingsService()

# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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
        with create_db_connection() as conn:
            with conn.cursor() as curs:
                curs.execute(
                    "SELECT embedding FROM embeddings WHERE content = %s AND collection = %s",
                    (content, collection)
                )
                result = curs.fetchone()
                
                if result:
                    return np.array(json.loads(result[0]))
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error retrieving embedding from database: {database_exception}")
        raise DatabaseOperationError(f"Failed to retrieve embedding from database: {database_exception}")
    
    except Exception as select_excep:
        logging.error(f"Unexpected error occured when retrieving embedding: {select_excep}")
        raise DatabaseOperationError(f"Unexpected error occured when retrieving embedding: {select_excep}")

    return None


def get_embeddings_from_collection(collection: str) -> List[Tuple[str, np.ndarray, str]]:
    """
    Retrieves all embeddings from a specific collection.

    :param collection: The collection to retrieve the embeddings from.
    :return: A list of tuples containing the content (question), embedding and the answer.
    """
    try:
        with create_db_connection() as conn:
            with conn.cursor() as curs:
                get_embedding_from_collection_query = SQL(
                    "SELECT content, embedding, answer FROM embeddings WHERE collection = {}").format(collection)
                curs.execute(get_embedding_from_collection_query)

                results = curs.fetchall()

                return [(content, np.array(json.loads(embedding)), answer) for content, embedding, answer in results]
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error retrieving embeddings from collection {collection}: {database_exception}")
        raise DatabaseOperationError(f"Failed to retrieve embeddings from collection {collection}: {database_exception}")
    
    except Exception as select_from_collection_excep:
        logging.error(f"Unexpected error when retrieving embeddings from collection {collection}: {select_from_collection_excep}")
        raise DatabaseOperationError(f"Unexpected error when retrieving embeddings from collection {collection}: {select_from_collection_excep}")
    
    return []


@celery.task
def add_embeddings_to_db(items: List[Tuple[str, str, str]]) -> None:
    """
    Adds embeddings to the database in batches, specified by the BATCH_SIZE environment variable.
    It handles large batches by splitting them into smaller chunks.
    It checks if the embedding already exists in the database before inserting it.
    The @celery.task decorator is used to make this function a Celery task, allowing it to be executed asynchronously.

    :param items: A list of tuples containing the content (question), answer and collection for each embedding.
    :return: None
    """
    try:
        with create_db_connection() as conn:
            with conn.cursor() as curs:
                batch_size = int(os.getenv('BATCH_SIZE'))

                for idx in range(0, len(items), batch_size):
                    batch = items[idx:idx + batch_size]

                    embeddings_to_insert = []

                    for content, answer, collection in batch:
                        existing_embedding = get_embedding_from_db(content, collection)

                        if existing_embedding is None:
                            embedding = embeddings_service.compute_embedding(content)
                            embeddings_to_insert.append((content, json.dumps(embedding), answer, collection))

                if embeddings_to_insert:
                    execute_values(
                        curs,
                        "INSERT INTO embeddings (content, embedding, answer, collection) VALUES %s",
                        embeddings_to_insert
                    )
                conn.commit()
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error adding embeddings to database: {database_exception}")
        raise DatabaseOperationError(f"Failed to add embeddings: {database_exception}")
    
    except Exception as insert_excep:
        logging.error(f"Unexpected error when adding embeddings to database: {insert_excep}")
        raise DatabaseOperationError(f"Unexpected error when adding embeddings to database: {insert_excep}")


@celery.task
def update_embeddings_in_db(items: List[Tuple[str, str, str]]) -> None:
    """
    Updates the embeddings in the database in batches, using the BATCH_SIZE environment variable.
    It handles large batches by splitting them into smaller chunks.
    It checks if the embedding already exists in the database before updating it.
    The @celery.task decorator is used to make this function a Celery task, allowing it to be executed asynchronously.

    :param items: A list of tuples containing the content (question), answer and collection for each embedding.
    :return: None
    """
    try:
        with create_db_connection() as conn:
            with conn.cursor() as curs:
                batch_size = int(os.getenv('BATCH_SIZE'))

                for idx in range(0, len(items), batch_size):
                    batch = items[idx:idx + batch_size]
                    updated_data = []

                    for content, answer, collection in batch:
                        embedding = embeddings_service.compute_embedding(content)
                        updated_data.append((json.dumps(embedding), answer, content, collection))

                    execute_batch(curs, """
                        UPDATE embeddings 
                        SET embedding = %s, answer = %s
                        WHERE content = %s AND collection = %s
                        """,
                        updated_data
                    )
                    conn.commit()
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error updating embeddings in database: {database_exception}")
        raise DatabaseOperationError(f"Failed to update embeddings: {database_exception}")
    
    except Exception as update_excep:
        logging.error(f"Unexpected error when updating embeddings in database: {update_excep}")
        raise DatabaseOperationError(f"Unexpected error when updating embeddings in database: {update_excep}")


def search_for_similarity_in_db(query_embedding: np.ndarray, collection: str) -> Tuple[Optional[str], Optional[str], float]:
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
        with create_db_connection() as conn:
            with conn.cursor() as curs:
                # Query to perform similarity search using pgvector
                search_query = """
                SELECT content, answer, 1 - (embedding <=> %s::vector) AS similarity
                FROM embeddings
                WHERE collection = %s
                ORDER BY similarity DESC
                LIMIT 1;
                """
                # Execute the query with the query_embedding and collection as parameters
                curs.execute(search_query, (query_embedding, collection))
                result = curs.fetchone()

                if result:
                    matched_content, matched_answer, similarity_score = result
                    return matched_content, matched_answer, similarity_score

    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error searching for similarity in the database: {database_exception}")
        raise DatabaseOperationError(f"Failed to search for similarity: {database_exception}")
    
    except Exception as similiarity_search_error:
        logging.error(f"Unexpected error when searching for similarity in the database: {similiarity_search_error}")
        raise DatabaseOperationError(f"Unexpected error when searching for similarity in the database: {similiarity_search_error}")

    return None


def delete_embedding_from_db(content: str, collection: str) -> None:
    """
    Deletes the embedding from the database.

    :param content: The content to delete from the database.
    :param collection: The collection the content belongs to.
    :return: None
    """
    try:
        with create_db_connection() as conn:
            with conn.cursor() as curs:
                curs.execute(
                    "DELETE FROM embeddings WHERE content = %s AND collection = %s",
                    (content, collection)
                )
                conn.commit()
    
    except (DatabaseError, InterfaceError) as database_exception:
        logging.error(f"Error deleting embedding from database: {database_exception}")
        raise DatabaseOperationError(f"Failed to delete embedding: {database_exception}")
    
    except Exception as delete_excep:
        logging.error(f"Unexpected error when deleting embedding from database: {delete_excep}")
        raise DatabaseOperationError(f"Unexpected error when deleting embedding from database: {delete_excep}")
