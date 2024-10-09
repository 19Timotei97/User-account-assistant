import logging
import asyncio

# Package imports
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Generator
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from jwt import PyJWTError
from pathlib import Path
from requests import RequestException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Local files imports
from auth.auth import create_access_token, get_token
from core.config import get_settings
from database.base import get_db_session
from database.create_database import create_database_if_not_exists, setup_database
from database.manage_database import search_for_similarity_in_db, add_embeddings_to_db, update_embeddings_in_db
from schemas.question_schema import Question, QuestionResponse
from schemas.token_schema import Token, TokenData

from services.llm_service import OpenAI_Responder
from services.embeddings_service import OpenAIEmbeddingsService, EmbeddingComputationError
from utils.utils import get_openai_responder, authenticate_user, get_faq_collection_name, retrieve_locally_stored_FAQ


"""
The main script of the FastAPI application for the contextual FAQ assistant.

This script sets up the FastAPI application, defines the necessary routes and endpoints, and includes 
    functions for storing initial embeddings of the FAQ database in the database.

The script also includes error handling and logging mechanisms for better debugging and monitoring.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve the environment variables
settings = get_settings()

# Set the base path
BASE_DIR = Path(__file__).resolve().parent

# Set the templates directory for rendering HTML templates
templates = Jinja2Templates(directory=str(Path(BASE_DIR, 'templates')))

# Get a singleton instance of the OpenAI embeddings model
embeddings_service = OpenAIEmbeddingsService()

# Retrieve the similarity threshold
similarity_threshold = float(settings.similarity_threshold)

# Find and parse the .env data
load_dotenv()


class AuthenticationError(Exception):
    """
    Custom exception for authentication errors.
    """
    pass


def get_database_session() -> Generator[Session, None, None]:
    """
    Provides a database session for FastAPI dependency injection.
    Needed without the context manager to ensure proper session handling.
    Uses the already defined get_db_session context manager.

    :return: A database session
    """
    with get_db_session() as db_session:
        yield db_session


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


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Exception handler for validation errors.

    :param request: The request object.
    :param exc: The validation exception.
    :return: A JSON response with the validation errors.
    """
    logging.error(f"Validation error: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors()}),
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
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


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    """
    Endpoint for authenticating the user and returning an access token.
    It uses the OAuth2PasswordRequestForm to authenticate the user and returns an access token.

    :param form_data: The form data containing the username and password.
    :return: The access token if the credentials are valid, otherwise raises an HTTPException.
    """
    try:
        user = authenticate_user(form_data.username, form_data.password)

        if not user:
            raise AuthenticationError("Incorrect username or password")
        
        if not user:
            logging.error(f"Authentication failed for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=int(settings.access_token_expire_minutes))

        # Create access token
        access_token = create_access_token(
            data={"sub": user["username"]}, expires_delta=access_token_expires
        )

        # Returns the token
        return {
            "access_token": access_token, 
            "token_type": "bearer"
        }
    
    except PyJWTError as jwt_excep:
        logging.error(f"JWT error during login: {jwt_excep}")
        raise HTTPException(status_code=500, detail="Token creation failed")
    
    except AuthenticationError as auth_excep:
        logging.error(f"Authentication error during login: {auth_excep}")
        raise HTTPException(status_code=401, detail=str(auth_excep))

    except Exception as token_validation_excep:
        logging.error(f"Error during login: {token_validation_excep}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/question-page", response_class=HTMLResponse)
async def ask_question_page(request: Request) -> HTMLResponse:
    """
    Renders the GET request for the question page.

    :param request: The request object.
    :return: The rendered HTML template for the question page.
    """
    try:
        return templates.TemplateResponse("question.html", {"request": request})
    
    except Exception as question_render_excep:
        logging.error(f"Error rendering question page: {question_render_excep}")
        raise HTTPException(status_code=500, detail="Error loading the question page")


@app.post("/ask-question", response_model=QuestionResponse)
async def ask_question(
    request: Request,
    user_question: Question,
    token: TokenData = Depends(get_token),
    database_session: Session = Depends(get_database_session),
    openai_responder: OpenAI_Responder = Depends(get_openai_responder),
    ) -> QuestionResponse:
    """
    Endpoint to handle the user's question.
    
    :param request: The request object.
    :param user_question: The question provided by the user.
    :param token: The token data for authentication.
    :param database_session: The database SQLAlchemy session.
    :param openai_responder: The OpenAI responder service.
    :return: The JSON response containing the matched question and answer or the OpenAI response.
    """
    if not user_question:
        return HTTPException(status_code=400, detail="No question provided")

    try:
        user_question_str_representation = user_question.user_question

        # Retrieve the initial collection name
        faq_collection_name = get_faq_collection_name()

        # Get an embedding of the user's question
        question_embedding = embeddings_service.compute_embedding(user_question_str_representation)

        # Perform similarity search in the database using the pgvector extension
        most_similar_embedding, similarity_score = search_for_similarity_in_db(
            database_session,
            question_embedding, 
            faq_collection_name
        )

        if most_similar_embedding:
            # Check to see if the similarity is at least equal to the threshold
            if similarity_score >= similarity_threshold:
                # Create the required response structure and return it
                response_data = QuestionResponse(
                    source="local",
                    matched_question=most_similar_embedding.content,
                    answer=most_similar_embedding.answer
                )

                # Update the matched embedding for faster retrieval next time
                update_embeddings_in_db.delay( 
                    [(
                        most_similar_embedding.content, 
                        most_similar_embedding.answer, 
                        faq_collection_name
                    )]
                )

            else:
                # If the similarity is below the threshold, return the OpenAI response
                openai_response = openai_responder.get_response(user_question_str_representation)

                response_data = QuestionResponse(
                    source="openai",
                    matched_question="N/A",
                    answer=openai_response
                )
        
                # Add the new embedding to the database
                # Using the multiple embeddings adding method in case the prompt is too large
                add_embeddings_to_db.delay( 
                    [(
                        user_question_str_representation, 
                        openai_response, 
                        faq_collection_name
                    )]
                )
        
        return response_data
    
    # Why such a generic DB error handling?
    # The embedding adding and update methods already catch SPECIFIC exceptions
    # Here I just add an extra layer of error handling
    except SQLAlchemyError as database_excep:
        logging.error(f"Database error in ask-question route: {database_excep}")
        raise HTTPException(status_code=500, detail="Database error occurred while processing the question")
    
    except EmbeddingComputationError as embed_excep:
        logging.error(f"Embedding computation error in ask-question route: {embed_excep}")
        raise HTTPException(status_code=500, detail=str(embed_excep))

    except RequestException as api_excep:
        logging.error(f"OpenAI API request failed in ask-question route: {api_excep}")
        raise HTTPException(status_code=502, detail="Failed to connect to external API!")

    except ValueError as value_excep:
        logging.error(f"Value error while processing the question in ask-question route: {value_excep}")
        raise HTTPException(status_code=400, detail="Invalid input or value error!")

    except Exception as http_excep:
        logging.error(f"Unhandled exception in ask-question route: {http_excep}")
        raise HTTPException(status_code=500, detail="Internal server error!")
