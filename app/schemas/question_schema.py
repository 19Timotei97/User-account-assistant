# Package imports
from pydantic import BaseModel


"""
This module contains the Pydantic models used by the FastAPI endpoint.

It includes two models:
1. Question: Represents the input question from the user.
2. QuestionResponse: Represents the response containing the matched question, source, and answer. 
    This model is used to format the response data.
"""


class Question(BaseModel):
    """
    Question class used by the FastAPI endpoint.
    """
    user_question: str


class QuestionResponse(BaseModel):
    """
    The question response class used by the FastAPI endpoint.
    """
    source: str
    matched_question: str
    answer: str

    class Config:
        from_attributes = True
