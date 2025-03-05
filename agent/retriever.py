import chainlit as cl
from .state import PlanExecute
import weaviate
from weaviate.connect import ConnectionParams
import weaviate.classes as wvc
from datetime import datetime
import dotenv
import os
import logging
from vector_stores.retriever import ensure_global_client

dotenv.load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@cl.step(name="Retrieve Chunks", type="tool")
async def run_qualitative_chunks_retrieval_workflow(state: PlanExecute):
    """
    Run the qualitative chunks retrieval workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    state["curr_state"] = "retrieve_chunks"

    query = state["query_to_retrieve_or_answer"]
    
    # Verwende den globalen Weaviate-Client
    weaviate_client = ensure_global_client()
    if not weaviate_client:
        state["curr_context"] += "Fehler: Konnte keine Verbindung zum Weaviate-Client herstellen."
        state["aggregated_context"] += state["curr_context"]
        return state
    
    # Stelle sicher, dass der Client verbunden ist
    if not weaviate_client.is_connected():
        logger.info("Der WeaviateClient ist nicht verbunden. Verbinde...")
        try:
            weaviate_client.connect()
        except Exception as e:
            state["curr_context"] += f"Fehler beim Verbinden des Weaviate-Clients: {str(e)}"
            state["aggregated_context"] += state["curr_context"]
            return state

    try:
        # Verwende die korrekte API für die Abfrage (v4)
        content_chunk_collection = weaviate_client.collections.get("Content_chunk")
        query_result = content_chunk_collection.query.near_text(
            query=query,
            limit=4,
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=["url", "content_chunk"]
        )
        
        docs = query_result.objects
        
        # Filter out empty content
        retrieved_info = " ".join(f"{doc.properties['url']}: {doc.properties['content_chunk']}" 
                                 for doc in docs 
                                 if doc.properties.get('content_chunk') and doc.properties['content_chunk'].strip())
        
        state["curr_context"] += f"Retrieved chunk information: {retrieved_info}"
        state["aggregated_context"] += state["curr_context"]
    
    except Exception as e:
        state["curr_context"] += f"Error retrieving chunks: {str(e)}"
        state["aggregated_context"] += state["curr_context"]
        
        # Versuche, den Client neu zu verbinden
        try:
            if weaviate_client and not weaviate_client.is_connected():
                weaviate_client.connect()
                logger.info("Weaviate-Client wurde nach Fehler neu verbunden.")
        except:
            pass

    return state

@cl.step(name="Retrieve Summaries", type="tool")
async def run_qualitative_summaries_retrieval_workflow(state: PlanExecute):
    """
    Run the qualitative summaries retrieval workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    state["curr_state"] = "retrieve_summaries"
    
    query = state["query_to_retrieve_or_answer"]
    
    # Verwende den globalen Weaviate-Client
    weaviate_client = ensure_global_client()
    if not weaviate_client:
        state["curr_context"] += "Fehler: Konnte keine Verbindung zum Weaviate-Client herstellen."
        state["aggregated_context"] += state["curr_context"]
        return state
    
    # Stelle sicher, dass der Client verbunden ist
    if not weaviate_client.is_connected():
        logger.info("Der WeaviateClient ist nicht verbunden. Verbinde...")
        try:
            weaviate_client.connect()
        except Exception as e:
            state["curr_context"] += f"Fehler beim Verbinden des Weaviate-Clients: {str(e)}"
            state["aggregated_context"] += state["curr_context"]
            return state

    try:
        # Verwende die korrekte API für die Abfrage (v4)
        content_summary_collection = weaviate_client.collections.get("Content_summary")
        query_result = content_summary_collection.query.near_text(
            query=query,
            limit=4,
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=["url", "content_summary"]
        )
        
        docs = query_result.objects
        
        # Filter out empty content
        retrieved_info = " ".join(f"{doc.properties['url']}: {doc.properties['content_summary']}" 
                                 for doc in docs 
                                 if doc.properties.get('content_summary') and doc.properties['content_summary'].strip())
        
        state["curr_context"] += f"Retrieved summary information: {retrieved_info}"
        state["aggregated_context"] += state["curr_context"]
    
    except Exception as e:
        state["curr_context"] += f"Error retrieving summaries: {str(e)}"
        state["aggregated_context"] += state["curr_context"]
        
        # Versuche, den Client neu zu verbinden
        try:
            if weaviate_client and not weaviate_client.is_connected():
                weaviate_client.connect()
                logger.info("Weaviate-Client wurde nach Fehler neu verbunden.")
        except:
            pass

    return state

@cl.step(name="Retrieve Quotes", type="tool")
async def run_qualitative_quotes_retrieval_workflow(state: PlanExecute):
    """
    Run the qualitative quotes retrieval workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    state["curr_state"] = "retrieve_quotes"

    query = state["query_to_retrieve_or_answer"]
    
    # Verwende den globalen Weaviate-Client
    weaviate_client = ensure_global_client()
    if not weaviate_client:
        state["curr_context"] += "Fehler: Konnte keine Verbindung zum Weaviate-Client herstellen."
        state["aggregated_context"] += state["curr_context"]
        return state
    
    # Stelle sicher, dass der Client verbunden ist
    if not weaviate_client.is_connected():
        logger.info("Der WeaviateClient ist nicht verbunden. Verbinde...")
        try:
            weaviate_client.connect()
        except Exception as e:
            state["curr_context"] += f"Fehler beim Verbinden des Weaviate-Clients: {str(e)}"
            state["aggregated_context"] += state["curr_context"]
            return state

    try:
        # Verwende die korrekte API für die Abfrage (v4)
        content_chunk_collection = weaviate_client.collections.get("Content_chunk")
        query_result = content_chunk_collection.query.near_text(
            query=query,
            limit=4,
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=["url", "content_chunk"]
        )
        
        docs = query_result.objects
        
        # Filter out empty content and only include quotes or definitions
        retrieved_info = " ".join(f"{doc.properties['url']}: {doc.properties['content_chunk']}" 
                                 for doc in docs 
                                 if doc.properties.get('content_chunk') and doc.properties['content_chunk'].strip())
        
        state["curr_context"] += f"Retrieved quote information: {retrieved_info}"
        state["aggregated_context"] += state["curr_context"]
    
    except Exception as e:
        state["curr_context"] += f"Error retrieving quotes: {str(e)}"
        state["aggregated_context"] += state["curr_context"]
        
        # Versuche, den Client neu zu verbinden
        try:
            if weaviate_client and not weaviate_client.is_connected():
                weaviate_client.connect()
                logger.info("Weaviate-Client wurde nach Fehler neu verbunden.")
        except:
            pass

    return state