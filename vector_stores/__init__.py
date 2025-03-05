# Vector Stores Package
from vector_stores.db_manager import WeaviateManager, ensure_global_client
from vector_stores.retriever import RetrieverFactory, create_retrievers, KeepAliveWeaviateVectorStore
from .weaviate_client import (
    create_weaviate_client,
    ensure_weaviate_connection, 
    check_weaviate_data,
    create_weaviate_schema
)

# Exportiere wichtige Funktionen
__all__ = [
    'WeaviateManager',
    'ensure_global_client',
    'RetrieverFactory',
    'create_retrievers',
    'KeepAliveWeaviateVectorStore',
    'create_weaviate_client',
    'ensure_weaviate_connection',
    'check_weaviate_data',
    'create_weaviate_schema'
]
