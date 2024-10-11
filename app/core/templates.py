# Package imports
from fastapi.templating import Jinja2Templates
from pathlib import Path


"""
This module sets up the templates directory for rendering HTML templates in the FastAPI application.

templates: Configures the Jinja2 template renderer for rendering HTML templates.
"""


# Set the base path
BASE_DIR = Path(__file__).resolve().parent.parent

# Set the templates directory for rendering HTML templates
templates = Jinja2Templates(directory=str(Path(BASE_DIR, 'templates')))
