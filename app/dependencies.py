import logging

# Package imports
from fastapi import HTTPException, Request

# Local files imports
from auth.auth_utils import verify_access_token
from schemas.token_schema import TokenData


"""
This module defines the dependencies for the FastAPI application, such as the token retrieval function.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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
