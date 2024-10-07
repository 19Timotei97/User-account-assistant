from pydantic import BaseModel


class Question(BaseModel):
    """
    Question class used by the FastAPI endpoint.
    """
    user_question: str
