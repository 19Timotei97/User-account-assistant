import os
import logging

# Package imports
from celery import Celery


"""
This script is defining the Celery service for the application's async task processing.
It defines the Celery instance and configures the results backend.
It also autodiscovers the tasks in the database.manage_database module, for async embeddings processing.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve and validate environment variables
broker_url = os.getenv('CELERY_BROKER_URL')
result_backend = os.getenv('CELERY_RESULT_BACKEND')

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
logging.info("Celery application started with broker: %s", broker_url)
