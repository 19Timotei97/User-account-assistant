import logging

# Package imports
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.exceptions import RequestValidationError

# Local files imports
from routers import auth, questions, collections
from core.templates import templates
from core.lifespan import lifespan
from core.handlers import validation_exception_handler


"""
The main module of the FastAPI application for the contextual FAQ assistant.

This module sets up the FastAPI app and includes the defined routers for authentication,
    question handling, and collection management. It also configures exception handling for validation.

Also the main route is defined, which serves the login (home) page. 

The app is launched with Uvicorn and served on the specified host and port via the Dockerfile.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Define the FastAPI main app
app = FastAPI(lifespan=lifespan)


# Add an exception handler with a custom method
app.add_exception_handler(
    exc_class_or_status_code=RequestValidationError, 
    handler=validation_exception_handler
)


# Attach the defined routers
app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(collections.router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Route for loading the login (home) page.

    :param request: The request object.
    :return: The rendered HTML template for the homepage.
    """
    # Serve the homepage with the login form
    try:
        return templates.TemplateResponse("login.html", {"request": request})
    
    except Exception as home_render_excep:
        logging.error(f"Error rendering home page: {home_render_excep}")

        raise HTTPException(status_code=500, detail="Error loading the home page")
