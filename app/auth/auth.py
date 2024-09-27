import os
import logging
import jwt

# Package imports
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel


"""
This script defines the authentication logic for the application.
It includes the creation of access tokens, token verification, and token data management.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# OAuth2 flow for authentication using a bearer token obtained with a password
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates an access token with a given expiration delta.
    It uses a randomly generated SECRET_KEY and specific ALGORITHM from the .env file to encode the token.
    The token is encoded with the provided data and the expiration date.

    :param data: The data to encode in the token.
    :param expires_delta: The expiration delta for the token.
    :return: The encoded access token.
    """
    try:
        to_encode = data.copy()

        # Fetch and validate expiration time from environment or provide a default value
        access_token_expire_minutes = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30))
        
        # We can either use the expiration delta or use the one defined in the .env file
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=access_token_expire_minutes)
        
        #  Set token expiration
        to_encode.update({"exp": expire})
        
        # Generate JWT token
        secret_key = os.getenv('SECRET_KEY')
        algorithm = os.getenv('ALGORITHM')

        if not secret_key or not algorithm:
            raise ValueError("SECRET_KEY or ALGORITHM is not set in the environment")

        encoded_jwt = jwt.encode(
            payload=to_encode, 
            key=secret_key, 
            algorithm=algorithm
        )
        
        return encoded_jwt
    
    except Exception as token_creation_excep:
        logging.error(f"Error creating access token: {token_creation_excep}")
        raise token_creation_excep


def verify_access_token(token: str, credentials_exception: HTTPException) -> TokenData:
    """
    Verifies a token and returns the token data.
    It raises an HTTP exception if the token is invalid.

    :param token: The token to verify.
    :param credentials_exception: The exception to raise if the token is invalid.
    :return: The token data.
    """
    try:
        secret_key = os.getenv('SECRET_KEY')
        algorithm = os.getenv('ALGORITHM')

        if not secret_key or not algorithm:
            logging.error("SECRET_KEY or ALGORITHM is not set in the environment")
            raise credentials_exception

        # Decode the JWT token
        payload = jwt.decode(
            jwt=token, 
            key=secret_key,
            algorithms=[algorithm]
        )
        
        username: str = payload.get("sub")
        
        if username is None:
            logging.warning("Token does not contain a subject ('sub')")
            raise credentials_exception

        return TokenData(username=username)
    
    except jwt.ExpiredSignatureError as expired_signature_excep:
        logging.error(f"Token expired error: {expired_signature_excep}")
        raise HTTPException(status_code=401, detail="Token expired")
    
    except jwt.JWTClaimsError as claims_excep:
        logging.error(f"Invalid claims in the token: {claims_excep}")
        raise HTTPException(status_code=401, detail="Invalid token claims")
    
    except jwt.JWTError as jwt_error:
        logging.error(f"JWT error: {jwt_error}")
        raise credentials_exception


def get_token(request: Request) -> TokenData:
    """
    Retrieves the token from the request header and verifies it.

    :param request: The request object.
    :return: The token data.
    """
    try:
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(status_code=401, detail="Authorization header missing")
        
        scheme, _, token = auth_header.partition(" ")
        
        # Ensure the Authentication header is ok
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        if not token:
            raise HTTPException(status_code=401, detail="Token missing")
        
        return verify_access_token(
            token=token, 
            credentials_exception=HTTPException(status_code=401, detail="Invalid token")
        )
    
    except HTTPException as http_excep:
        logging.error(f"HTTPException during token retrieval: {http_excep.detail}")
        raise

    except Exception as token_retrieval_excep:
        logging.error(f"Unexpected error during token retrieval: {token_retrieval_excep}")
        raise HTTPException(status_code=500, detail="Internal server error")
