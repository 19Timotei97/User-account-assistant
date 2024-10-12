import logging

# Package imports
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from jwt import PyJWTError

# Local files imports
from auth.auth_utils import create_access_token, authenticate_user
from core.config import get_settings
from schemas.token_schema import Token


"""
This module defines the authentication routes for the FastAPI application.

login_for_access_token: Handles the login process and returns an access token if the credentials are valid.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve the Pydantic settings
settings = get_settings()

# Define the router for binding the routes to the main FastAPI app
router = APIRouter()


class AuthenticationError(Exception):
    """
    Custom exception for authentication errors.
    """
    pass


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint for authenticating the user and returning an access token.
    It uses the OAuth2PasswordRequestForm to authenticate the user and returns an access token.

    :param form_data: The form data containing the username and password.
    :return: The access token if the credentials are valid, otherwise raises an HTTPException.
    """
    try:
        user = authenticate_user(form_data.username, form_data.password)

        if not user:
            logging.error(f"Authentication failed for user: {form_data.username}")
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
