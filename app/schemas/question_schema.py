# Package imports
from pydantic import BaseModel


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
