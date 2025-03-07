import chainlit as cl
from .state import PlanExecute
import weaviate
from weaviate.connect import ConnectionParams
import weaviate.classes as wvc
from datetime import datetime
import dotenv
import os
import logging
import asyncio
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
        quote_collection = weaviate_client.collections.get("Quote")
        query_result = quote_collection.query.near_text(
            query=query,
            limit=4,
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=["url", "content", "source", "title"]
        )
        
        docs = query_result.objects
        
        # Filter out empty content and only include quotes or definitions
        retrieved_info = " ".join(f"{doc.properties['url']} ({doc.properties.get('source', 'unbekannt')}): {doc.properties['content']}" 
                                 for doc in docs 
                                 if doc.properties.get('content') and doc.properties['content'].strip())
        
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

@cl.step(name="Parallel Retrieval", type="tool")
async def run_parallel_retrieval_workflow(state: PlanExecute):
    """
    Führt alle drei Retrieval-Methoden parallel aus und kombiniert die Ergebnisse.
    
    Args:
        state: Der aktuelle Zustand der Plan-Ausführung.
    Returns:
        Der aktualisierte Zustand mit den kombinierten Retrieval-Ergebnissen.
    """
    state["curr_state"] = "parallel_retrieval"
    
    # Erstelle Kopien des Zustands für jede Retrieval-Methode
    chunks_state = state.copy()
    summaries_state = state.copy()
    quotes_state = state.copy()
    
    # Führe alle drei Retrieval-Methoden parallel aus
    await cl.Message(content=f"Führe parallele Retrieval-Methoden für die Anfrage aus: '{state['query_to_retrieve_or_answer']}'").send()
    
    retrieval_tasks = [
        run_qualitative_chunks_retrieval_workflow(chunks_state),
        run_qualitative_summaries_retrieval_workflow(summaries_state),
        run_qualitative_quotes_retrieval_workflow(quotes_state)
    ]
    
    # Warte auf alle Retrieval-Ergebnisse
    chunks_result, summaries_result, quotes_result = await asyncio.gather(*retrieval_tasks)
    
    # Extrahiere die Kontexte aus den Ergebnissen
    chunks_context = chunks_result.get("curr_context", "")
    summaries_context = summaries_result.get("curr_context", "")
    quotes_context = quotes_result.get("curr_context", "")
    
    # Kombiniere die Kontexte mit Quellenangaben
    combined_context = ""
    if chunks_context:
        combined_context += f"### Aus Chunks:\n{chunks_context}\n\n"
    if summaries_context:
        combined_context += f"### Aus Zusammenfassungen:\n{summaries_context}\n\n"
    if quotes_context:
        combined_context += f"### Aus Zitaten:\n{quotes_context}\n\n"
    
    # Aktualisiere den Zustand mit dem kombinierten Kontext
    state["curr_context"] = combined_context
    state["aggregated_context"] += combined_context
    
    await cl.Message(content=f"Parallele Retrieval-Methoden abgeschlossen. Kombinierte {len(chunks_context) + len(summaries_context) + len(quotes_context)} Zeichen an Kontext.").send()
    
    return state