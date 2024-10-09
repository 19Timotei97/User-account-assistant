# Package imports
from sqlalchemy import Column, Integer, Text, String
from pgvector.sqlalchemy import Vector

# Local files imports
from .base import Base


"""
This script defines the table models for the contextual FAQ assistant.
It includes the Embedding class, which represents the embeddings table in the database and the columns for the table, 
    including the content, embedding, answer, and collection.
The Embedding class also includes a relationship with the Collection class, which is not used in this implementation.
"""


# TODO: check if this could be a feature, a different table 'collections'
# Collection table definition
class Collection(Base):
    """
    The Collection class defines the ORM model and represents the collections table in the database.
    It inherits from the Base class and defines the columns for the table.
    This table is not used in this implementation, but it could be used to store collection names.
    """
    __tablename__ = 'collections'

    id = Column(
        Integer, 
        primary_key=True,
        autoincrement=True
    )

    name = Column(
        String(255), 
        unique=True
    )


class Embedding(Base):
    """
    The Emedding class defines the ORM model and represents the embeddings table in the database.
    It inherits from the Base class and defines the columns for the table.
    """
    __tablename__ = 'embeddings'

    # Define the table columns
    id = Column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    
    content = Column(
        Text, 
        nullable=False
    )

    embedding = Column(
        Vector(1536), 
        nullable=False
    )

    answer = Column(
        Text, 
        nullable=False
    )

    collection = Column(
        String(255), 
        nullable=False
    )


    """
    # For the collections table to be included, the 'embeddings' table would need a foreign key relationship
    # So the following definition should be used instead of the previous one
    __tablename__ = 'embeddings'

    id = Column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )

    content = Column(
        Text, 
        nullable=False
    )

    embedding = Column(
        Vector(1536), 
        nullable=False
    )

    answer = Column(
        Text, 
        nullable=False
    )

    collection_id = Column(
        Integer, 
        ForeignKey('collections.id')
    )

    # Optional relationship for accessing collection data
    collection = relationship("Collection")
    """
