import os
import logging
import psycopg2
import tiktoken
import json
import numpy as np

# Package imports
from typing import List, Optional, Tuple
from langchain_community.utils.math import cosine_similarity

# Local files imports
from core.config import get_settings
from services.llm_service import OpenAI_Responder


"""
This script defines utility functions for the application, such as database connection creation, 
    token truncation, OpenAI responder initialization, similarity searching and FAQ collection management.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve the environment variables as settings
settings = get_settings()

# Database connection parameters, used to connect to the PostgreSQL database.
DB_PARAMS = {
    'dbname': settings.postgres_db,
    'user': settings.postgres_user,
    'password': settings.postgres_password,
    'host': settings.postgres_host,
    'port': settings.postgres_port
}


def create_db_connection() -> psycopg2.extensions.connection:
    """
    Creates a connection to the PostgreSQL database.
    It uses the pre-defined database parameters from the DB_PARAMS dictionary.

    :return: The connection object.
    """
    try:
        for key in ['dbname', 'user', 'password']:
            if not DB_PARAMS.get(key):
                raise ValueError(f"Missing required database parameter: {key}")

        return psycopg2.connect(**DB_PARAMS)
    
    except psycopg2.OperationalError as operational_excep:
        logging.error(f"Encountered operational error when trying to connect to the database: {operational_excep}")
        raise operational_excep
    
    except Exception as connection_excep:
        logging.error(f"Unexpected error occurred: {connection_excep}")
        raise connection_excep


def limit_token_length(text: str, max_tokens: int = 2000) -> str:
    """
    Limits the number of tokens in the given text to the specified maximum for token-efficient embedding generation.
    It uses the tiktoken encoding to count the tokens and truncates the text accordingly.

    :param text: The text to limit the tokens for.
    :param max_tokens: The maximum number of tokens to keep.
    :return: The text with the limited number of tokens.
    """
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)

    if len(tokens) > max_tokens:
        logging.warning("The provided text exceeds 2000 tokens!")
        
        logging.info(f"Truncating text to {max_tokens} tokens.")

        limited_tokens = tokens[:max_tokens]
        limited_text = encoding.decode(limited_tokens)

        return limited_text
    
    return text


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


def get_faq_collection_name() -> str:
    """
    Retrieves the collection name for the provided FAQs from the environment variable.
    
    :return: The collection name as a string.
    """
    return settings.faq_collection_name


def retrieve_locally_stored_FAQ() -> list:
    """
    Retrieves the locally stored FAQ database.

    :return: A list of dictionaries containing the FAQ data.
    """    
    faq_json_file = os.path.join(os.path.dirname(__file__), 'FAQ_database.json')
    
    faq_local_database_loader = FAQ_Loader(faq_json_file=faq_json_file, limit=100)
    faq_local_database = faq_local_database_loader.load_faq_database()
    
    return faq_local_database


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


def authenticate_user(username: str, password: str) -> dict:
    """
    Dummy authentication function.

    :param username: The username to authenticate.
    :param password: The password to authenticate.
    :return: A dictionary containing the username if the credentials are valid, otherwise an empty dictionary.
    """
    if username == "user" and password == "test":
        return {"username": username}
    
    return {}


class FAQ_Loader:
    """
    Reads and retrieves the local FAQ database stored as JSON.
    """
    def __init__(self, faq_json_file: str, limit: Optional[int]) -> None:
        """
        Initializes the FAQ local reader.

        :param faq_json_file (str): The path to the JSON file containing the FAQ database.
        :param limit (Optional[Int]): Optional, the maximum number of FAQ entries to load.
        :return: None
        """
        self.limit = limit
        self.faq_json_file = faq_json_file


    def load_faq_database(self) -> list:
        """
        Loads the FAQ database from the JSON file up until the specified limit.

        :return: A list of dictionaries representing the FAQ entries.
        """
        try:
            with open(self.faq_json_file, "r") as faq_data:
                faqs = json.load(faq_data)

            if self.limit is not None:
                faqs = faqs['faqs'][:self.limit]
            else:
                faqs = faqs['faqs']

            return faqs

        except FileNotFoundError as file_not_found_excep:
            logging.error(f"FAQ file not found: {self.faq_json_file}")
            raise file_not_found_excep

        except json.JSONDecodeError as json_decode_excep:
            logging.error(f"Error decoding JSON from file: {self.faq_json_file}")
            raise json_decode_excep
