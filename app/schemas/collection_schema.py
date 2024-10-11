# Package imports
from pydantic import BaseModel


"""
This module defines the Collection Pydantic model, which is used by the FastAPI endpoint
"""


class Collection(BaseModel):
    """
    The collection class used by the FastAPI endpoint.
    """
    name: str

    class Config:
        from_attributes = True
