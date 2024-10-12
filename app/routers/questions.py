import logging

# Package imports
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from requests import RequestException

# Local files imports
from dependencies import get_token
from database.manage_database import search_for_similarity_in_db, add_embeddings_to_db, update_embeddings_in_db
from core.config import get_settings
from core.templates import templates
from sqlalchemy.exc import SQLAlchemyError
from schemas.question_schema import Question, QuestionResponse
from schemas.token_schema import TokenData
from services.embeddings_service import OpenAIEmbeddingsService, EmbeddingComputationError
from services.llm_service import OpenAI_Responder
from utils.utils import get_database_session, get_openai_responder, \
                        get_faq_collection_name


"""
This module defines the routes and functionality for handling user questions and retrieving:

ask_question: Handles the user's question, computes the similarity with the existing embeddings,
              and returns the most similar question and answer.

question_page: Renders the HTML template for the question page.

It also includes error handling and logging mechanisms for better debugging and monitoring.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get a singleton instance of the OpenAI embeddings model
embeddings_service = OpenAIEmbeddingsService()

# Retrieve the environment variables
settings = get_settings()

# Retrieve the similarity threshold
similarity_threshold = float(settings.similarity_threshold)

# Define the router for binding the routes to the main FastAPI app
router = APIRouter()


@router.get("/question-page", response_class=HTMLResponse)
async def ask_question_page(request: Request) -> HTMLResponse:
    """
    Renders the GET request for the question page.

    :param request: The request object.
    :return: The rendered HTML template for the question page.
    """
    try:
        logging.info("Rendering question page")
        return templates.TemplateResponse("question.html", {"request": request})
    
    except Exception as question_render_excep:
        logging.error(f"Error rendering question page: {question_render_excep}")
        raise HTTPException(status_code=500, detail="Error loading the question page")


@router.post("/ask-question", response_model=QuestionResponse)
async def ask_question(
    request: Request,
    user_question: Question,
    token: TokenData = Depends(get_token),
    database_session: Session = Depends(get_database_session),
    openai_responder: OpenAI_Responder = Depends(get_openai_responder),
    ):
    """
    Endpoint to handle the user's question.
    
    :param request: The request object.
    :param user_question: The question provided by the user.
    :param token: The token data for authentication.
    :param database_session: The database SQLAlchemy session.
    :param openai_responder: The OpenAI responder service.
    :return: The response data containing the matched question and answer.
    """
    if not user_question:
        logging.error("No user question provided")
        return HTTPException(status_code=400, detail="No question provided")

    try:
        user_question_str_representation = user_question.user_question

        # Retrieve the initial collection name
        faq_collection_name = get_faq_collection_name()
        logging.info(f"FAQ collection name: {faq_collection_name}")

        # Get an embedding of the user's question
        question_embedding = embeddings_service.compute_embedding(user_question_str_representation)
        logging.info(f"Question embedding computed with dimension {len(question_embedding)}")

        # Perform similarity search in the database using the pgvector extension
        most_similar_embedding, similarity_score = search_for_similarity_in_db(
            database_session,
            question_embedding, 
            faq_collection_name
        )

        if most_similar_embedding:
            # Check to see if the similarity is at least equal to the threshold
            if similarity_score >= similarity_threshold:
                logging.info("Similar content found, using the local FAQ database...")

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
                logging.info(f"Content similar to '{user_question_str_representation}' not found, using the OpenAI responder...")

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
