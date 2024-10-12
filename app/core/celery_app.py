import logging

# Package imports
from celery import Celery
from celery.signals import worker_ready

# Local files imports
from .config import get_settings


"""
This module is defining the Celery service for the application's async task processing.
It defines the Celery instance and configures the results backend.
It also autodiscovers the tasks in the database.manage_database module, for async embeddings processing.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get the environment variables from the config file
settings = get_settings()

# Retrieve and validate environment variables
broker_url = settings.celery_broker_url
result_backend = settings.celery_result_backend

if not broker_url:
    raise EnvironmentError("CELERY_BROKER_URL environment variable is not set!")
if not result_backend:
    raise EnvironmentError("CELERY_RESULT_BACKEND environment variable is not set!")


# Set up the Celery application
celery = Celery('tasks', broker=broker_url)

# Configure results backend
celery.conf.update(
    result_backend=result_backend,
    broker_connection_retry_on_startup=True
)

# Autodiscover the database embeddings tasks
celery.autodiscover_tasks(['database.manage_database'])

# Log the Celery initialization
logging.info(f"Celery application started with broker '{broker_url}'...")


# Log when the worker is fully connected and ready
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    logging.info("Celery worker is fully connected and ready to process tasks.")
