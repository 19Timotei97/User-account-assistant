import logging
import json
import os

# Package imports
from typing import Optional

# Local files imports
from core.config import get_settings


"""
This module defines methods for retrieving locally stored FAQ data and managing the collection name
    for the FAQs in the environment variables.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve the pydantic settings
settings = get_settings()


def get_faq_collection_name() -> str:
    """
    Retrieves the collection name for the provided FAQs from the environment variable.
    
    :return: The collection name as a string.
    """
    return settings.faq_collection_name


def retrieve_locally_stored_FAQ() -> list:
    """
    Retrieves the locally stored FAQ database.

    :return: A list of dictionaries containing the FAQ data or an empty list if an error occurs.
    """
    faq_local_database = []

    logging.info("Retrieving locally stored FAQ database...")

    faq_json_file = os.path.join(os.path.dirname(__file__), 'FAQ_database.json')
    
    faq_local_database_loader = FAQ_Loader(faq_json_file=faq_json_file, limit=100)
    faq_local_database = faq_local_database_loader.load_faq_database()
    
    return faq_local_database


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
                logging.info(f"Loading up to {self.limit} FAQ entries...")
                faqs = faqs['faqs'][:self.limit]

            else:
                logging.info("Loading all FAQ entries...")
                faqs = faqs['faqs']

            return faqs

        except FileNotFoundError as file_not_found_excep:
            logging.error(f"FAQ file not found: {self.faq_json_file}")
            raise file_not_found_excep

        except json.JSONDecodeError as json_decode_excep:
            logging.error(f"Error decoding JSON from file: {self.faq_json_file}")
            raise json_decode_excep
