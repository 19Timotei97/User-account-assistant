import logging

# Package imports
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError

# Local files imports
from schemas.error_schema import ValidationErrorDetail, ValidationErrorResponse


"""
This module defines exception handlers for the FastAPI application.

validation_exception_handler: Handles validation errors by logging the error and returning a custom validation error response.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def validation_exception_handler(request: Request, exception: RequestValidationError):
    """
    Exception handler for validation errors.

    :param request: The request object.
    :param exception: The validation exception.
    :return: A validation error response.
    """
    logging.error(f"Validation error: {exception}")
    
    return ValidationErrorResponse(
        code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=[
            ValidationErrorDetail(
                location=error.get("loc"),
                message=error.get("msg"),
                type=error.get("type")
            ) for error in exception.errors()
        ]
    )
