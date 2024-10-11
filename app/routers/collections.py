# Package imports
from fastapi import APIRouter, Depends, HTTPException
from typing import List

# Local files imports
from dependencies import TokenData, get_token
from schemas.collection_schema import Collection
from database.manage_collections import add_collection_to_db, get_collection_from_db, \
                    get_collections_from_db, update_collection_in_db, delete_collection_from_db


"""
This module defines the FastAPI router for the collections routes.

Methods:
- create_collection: Creates a new collection.
- get_collection_by_name: Retrieves a collection by its name.
- get_collections: Retrieves a list of collections.
- update_collection: Updates a collection.
- delete_collection: Deletes a collection.

Some work could be done in improving the user experience in managing collections.
"""


# Define the FastAPI router to bind collections routes
router = APIRouter()


@router.post("/collections", response_model=Collection)
async def create_collection(collection: Collection, token: TokenData = Depends(get_token)):
    """
    FastAPI router method to create a new collection.

    :param collection: The collection object to be created.
    :return: The created collection object.
    """
    return await add_collection_to_db(collection)


@router.get("/collections/{collection_name}", response_model=Collection)
async def get_collection_by_name(collection_name: str, token: TokenData = Depends(get_token)):
    """
    FastAPI router method to retrieve a collection by its name.

    :param collection_name: The name of the collection to retrieve.
    :return: The retrieved collection object.
    """
    collection = await get_collection_from_db(collection_name)
    
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    return collection


@router.get("/collections", response_model=List[Collection])
async def get_collections(limit: int = 10, token: TokenData = Depends(get_token)):
    """
    FastAPI router method to retrieve a list of collections.

    :param limit: The maximum number of collections to retrieve.
    :param offset: The number of collections to skip.
    :return: A list of collection objects.
    """
    return await get_collections_from_db(limit)


@router.put("/collections", response_model=Collection)
async def update_collection(collection: Collection, token: TokenData = Depends(get_token)):
    """
    FastAPI router method to update a collection.

    :param collection: The collection object to be updated.
    :return: The updated collection object.
    """
    return await update_collection_in_db(collection)


@router.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str, token: TokenData = Depends(get_token)):
    """
    FastAPI router method to delete a collection.

    :param collection_name: The name of the collection to be deleted.
    :return: A success message.
    """
    await delete_collection_from_db(collection_name)
    
    return {"message": "Collection deleted successfully"}
