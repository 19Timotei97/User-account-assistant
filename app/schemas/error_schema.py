# Package imports
from pydantic import BaseModel
from typing import List


"""
This module defines the Pydantic models for validation errors.

It includes two models:
1. ValidationErrorDetail: Represents the details of a validation error, including the location, message, and type.
2. ValidationErrorResponse: Represents the validation error response, including the code and a list of ValidationErrorDetail objects.

These models can be used to validate and handle validation errors in the FastAPI application.
"""


class ValidationErrorDetail(BaseModel):
    """
    Defines the error details model for validation errors.

    :param location: A list of strings representing the location of the error.
    :param message: A string representing the error message.
    :param type: A string representing the error type.
    """
    location: List[str]
    message: str
    type: str


class ValidationErrorResponse(BaseModel):
    """
    Defines the validation error response model.

    :param code: An integer representing the error code.
    :param detail: A list of ValidationErrorDetail objects representing the validation errors.
    """
    code: int
    detail: List[ValidationErrorDetail]
