# Package imports
from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    """
    Base class for JWT tokens.
    It defines the token and its type.
    """
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """
    Base class for the token data.
    """
    username: Optional[str] = None
