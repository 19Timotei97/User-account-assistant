import os
import logging
import numpy as np

# Package imports
from abc import ABC, abstractmethod
from typing import List
from langchain_openai import OpenAIEmbeddings

# Local files imports
from utils.utils import limit_token_length


"""
This script implements the EmbeddingsService class and its subclasses.
The EmbeddingsService class is a base class for embeddings services, and it defines the compute_embedding method.
The OpenAIEmbeddingsService class is a subclass of EmbeddingsService that uses OpenAI's Embeddings model to generate embeddings for text.
It is implemented as a singleton to avoid re-initialization of the embeddings model.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class EmbeddingComputationError(Exception):
    """Exception raised when there is an error computing embeddings."""
    pass


class EmbeddingsService(ABC):
    """
    Base class for embeddings services.
    This class is not meant to be instantiated directly.
    """
    @abstractmethod
    def compute_embedding(self, text: str) -> np.ndarray:
        """
        Computes the embedding for the given text.

        :param text: The text to compute the embedding for.
        :return: The embedding for the given text.
        """
        raise NotImplementedError("Subclasses must implement this method")


class OpenAIEmbeddingsService(EmbeddingsService):
    """
    Uses OpenAI's Embeddings model to generate embeddings for text.
    It is implemented as a singleton to avoid re-initialization of the embeddings model.
    """
    _instance = None


    def __new__(cls, model: str = "text-embedding-3-small"):
        """
        Implements the singleton pattern for the OpenAIEmbeddingsService.

        :param model: The model to use for the embeddings.
        :return: The instance of the OpenAIEmbeddingsService.
        """
        if cls._instance is None:
            cls._instance = super(OpenAIEmbeddingsService, cls).__new__(cls)
            cls._instance.__init__(model=model)

        return cls._instance


    def __init__(self, model: str = "text-embedding-3-small") -> None:
        """
        Initializes the OpenAIEmbeddingsService with an instance of OpenAIEmbeddings if it hasn't been initialized yet.

        :param model: The model to use for the embeddings.
        :return: None
        """
        if not hasattr(self, 'initialized'):
            # Retrieve and ensure the API key is correctly set
            openai_api_key = os.getenv('OPENAI_API_KEY')

            if not openai_api_key:
                raise EnvironmentError("OPENAI_API_KEY environment variable is not set!")

            # Catch errors that may occur during OpenAI embeddings model init
            try:
                self.embeddings_model = OpenAIEmbeddings(
                    model=model,
                    api_key=openai_api_key
                )
            except Exception as embeddings_excep:
                logging.error(f"Error while initializing OpenAIEmbeddingsService: {embeddings_excep}")
                raise embeddings_excep
        
        self.cache = {}
        self.initialized = True


    def compute_embedding(self, text: str) -> list:
        """
        Computes the embedding for the given text.
        It's cached to avoid recomputing the same embedding for the same text.
        It ensures that the text is limited to a maximum number of tokens before computing the embedding.
        
        :param text: The text to compute the embedding for.
        :return: The embedding for the given text.
        """
        if text in self.cache:
            return self.cache[text]
        
        # Ensure the text is not over a certain limit length
        text = limit_token_length(text)

        try:
            # Embed the text if not found in the cache
            text_embedding = self.embeddings_model.embed_query(text)
        
        except Exception as embedding_excep:
            logging.error(f"Error while computing embedding for text {text}: {embedding_excep}")
            raise EmbeddingComputationError(f"Failed to compute embedding for text: {text}") from embedding_excep

        # Save it for future usage
        self.cache[text] = text_embedding

        return np.array(
            self.cache[text]
        ).tolist()


    def compute_batch_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Computes embeddings for a batch of texts.

        :param texts: The list of texts to compute embeddings for.
        :return: A list of embeddings for the given texts.
        """
        try:
            return [np.array(embedding) for embedding in self.embeddings_model.embed_documents(texts)]
        
        except Exception as batch_embedding_excep:
            logging.error(f"Error while computing batch embeddings: {batch_embedding_excep}")
            raise EmbeddingComputationError("Failed to compute batch embeddings") from batch_embedding_excep


    def clear_cache(self) -> None:
        """
        Clears the cache of computed embeddings.
        """
        self.cache.clear()
