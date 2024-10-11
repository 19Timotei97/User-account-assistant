import logging
import numpy as np

# Package imports
from langchain_community.utils.math import cosine_similarity
from typing import Generator, List, Tuple
from sqlalchemy.orm import Session

# Local files imports
from core.config import get_settings
from database.base import get_db_session
from database.manage_database import add_embeddings_to_db
from .faq_utils import retrieve_locally_stored_FAQ, get_faq_collection_name
from services.llm_service import OpenAI_Responder


"""
This module contains utility functions used throughout the application.

get_openai_responder: Returns an instance of the OpenAI_Responder class with parameters from environment variables.
get_database_session: Provides a database session for FastAPI dependency injection.
search_for_similarity: Finds the most similar embedding to the query embedding in the list of embeddings.
    Computes the cosine similarity between the query embedding and each embedding in the list.
store_initial_embeddings: Stores the initial embeddings of the FAQ database in the database.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve the environment variables as settings
settings = get_settings()


def get_openai_responder() -> OpenAI_Responder:
    """
    Initializes and returns an instance of the OpenAI_Responder class with parameters from environment variables.
    
    :return: An instance of the OpenAI_Responder class.
    """
    model_name = settings.openai_model_name
    max_tokens = int(settings.openai_model_max_tokens)
    n = int(settings.openai_model_n)
    temperature = float(settings.openai_model_temperature)
    
    return OpenAI_Responder(
        model_name=model_name, 
        max_tokens=max_tokens, 
        n=n, 
        temperature=temperature
    )


def get_database_session() -> Generator[Session, None, None]:
    """
    Provides a database session for FastAPI dependency injection.
    Needed without the context manager to ensure proper session handling.
    Uses the already defined get_db_session context manager.

    :return: A database session
    """
    with get_db_session() as db_session:
        yield db_session


def search_for_similarity(query_embedding: np.ndarray, embeddings: List[np.ndarray]) -> Tuple[int, float]:
    """
    Finds the most similar embedding to the query embedding in the list of embeddings.
    Computes the cosine similarity between the query embedding and each embedding in the list.

    :param query_embedding: The embedding to search for.
    :param embeddings: The list of embeddings to search in.
    :return: The index of the most similar embedding and its similarity score.
    """
    if not embeddings:
        logging.warning("No embeddings provided for similarity search!")
        return -1, 0.0
    
    # Normalize the embedding of the prompt
    query_embedding = query_embedding / np.linalg.norm(query_embedding)

    # Normalize all the other embeddings
    normalized_embeddings = [embedding / np.linalg.norm(embedding) for embedding in embeddings]

    # Compute the cosine similarity
    similarities = cosine_similarity([query_embedding], normalized_embeddings)[0]

    most_similar_index = np.argmax(similarities)
    similarity_score = similarities[most_similar_index]

    return most_similar_index, similarity_score


def store_initial_embeddings() -> None:
    """
    Stores the initial embeddings of the FAQ database in the database.
    Uses the OpenAIEmbeddingsService to compute the embeddings.

    :return: None
    """
    faq_local_database = retrieve_locally_stored_FAQ()
    
    faq_embeddings = [(item['question'], item['answer'], get_faq_collection_name()) for item in faq_local_database]
    
    logging.info('Storing initial FAQ embeddings in the database...')

    add_embeddings_to_db(faq_embeddings)
