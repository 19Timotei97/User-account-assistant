import logging
import jwt

# Package imports
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer

# Local files imports
from core.config import get_settings
from schemas.token_schema import TokenData


"""
This module defines the authentication logic for the application.
It includes functions for creating access tokens and verifying them, as well as defining the OAuth2 scheme for authentication.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve environment variables in a Pydantic way
settings = get_settings()

# OAuth2 flow for authentication using a bearer token obtained with a password
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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
        
        # We can either use the expiration delta or use the one defined in the .env file
        if expires_delta:
            logging.info("Using the provided expiration delta")
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            logging.info("Using the default expiration delta from the environment")
            expire = datetime.now(timezone.utc) + timedelta(minutes=int(settings.access_token_expire_minutes))
        
        #  Set token expiration
        to_encode.update({"exp": expire})
        
        # Generate JWT token
        secret_key = settings.secret_key
        algorithm = settings.algorithm

        if not secret_key or not algorithm:
            logging.error("SECRET_KEY or ALGORITHM is not set in the environment")
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
        secret_key = settings.secret_key
        algorithm = settings.algorithm

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


def authenticate_user(username: str, password: str) -> dict:
    """
    Dummy authentication function.

    :param username: The username to authenticate.
    :param password: The password to authenticate.
    :return: A dictionary containing the username if the credentials are valid, otherwise an empty dictionary.
    """
    if username == "user" and password == "test":
        return {"username": username}
    
    return {}
