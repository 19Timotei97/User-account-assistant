import logging
import asyncio

# Package imports
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Local files imports
from database.create_database import create_database_if_not_exists, setup_database
from utils.utils import store_initial_embeddings


"""
This module defines the lifespan context manager for the FastAPI application.

lifespan: Sets up the database and initial embeddings when the application starts up.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for setting up the database and initial embeddings.

    :param app: The FastAPI application instance.
    """
    logging.info("Starting database setup...")
    loop = asyncio.get_running_loop()
    
    try:
        await loop.run_in_executor(None, create_database_if_not_exists)
        logging.info("Database creation check completed.")
        
        await loop.run_in_executor(None, setup_database)
        logging.info("Database setup completed successfully!")

        await loop.run_in_executor(None, store_initial_embeddings)
        logging.info('Stored initial FAQ embeddings in the database.')
    
    except Exception as setup_excep:
        logging.error(f"Error during database setup: {setup_excep}")
        raise
    
    yield
