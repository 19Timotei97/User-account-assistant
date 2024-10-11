# Package imports
from pydantic import BaseModel
from typing import Optional


"""
This module defines the Pydantic models used for token data.

It includes two models:
1. Token: Represents the JWT token.
2. TokenData: Represents the token data, including the username (optional).
"""


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
