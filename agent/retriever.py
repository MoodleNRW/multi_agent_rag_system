import chainlit as cl
from langsmith import traceable
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
from ui.faq_ui import search_faq_database, show_save_to_faq_option
from pydantic import BaseModel, Field
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableParallel

dotenv.load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@traceable(pass_config=False)
@cl.step(name="Check FAQ", type="tool")
async def run_faq_check_workflow(state: PlanExecute):
    """
    Überprüft zuerst die FAQ-Datenbank auf eine passende Antwort.
    
    Args:
        state: Der aktuelle Zustand der Plan-Ausführung.
    Returns:
        Der aktualisierte Zustand mit der FAQ-Antwort, falls gefunden.
    """
    state["curr_state"] = "check_faq"
    query = state["query_to_retrieve_or_answer"]
    
    logger.info(f"Überprüfe FAQ-Datenbank für Anfrage: {query}")
    await cl.Message(content="🔍 Überprüfe FAQ-Datenbank...").send()
    
    try:
        # Suche in der FAQ-Datenbank mit SEHR hohem Ähnlichkeitsschwellenwert
        faqs = await search_faq_database(query, similarity_threshold=0.85, limit=2)
        
        # Filtern und Prüfen auf relevante Inhalte
        relevant_faqs = []
        if faqs:
            for faq in faqs:
                similarity = faq.get('similarity', 0)
                # Zusätzliche Relevanzprüfung mit strengem Schwellenwert
                if similarity >= 0.85:
                    relevant_faqs.append(faq)
                    logger.info(f"Relevante FAQ gefunden mit Ähnlichkeit: {similarity}")
        
        if relevant_faqs:
            # Relevante FAQ gefunden - nehme die mit der höchsten Ähnlichkeit
            best_faq = max(relevant_faqs, key=lambda x: x.get('similarity', 0))
            similarity = best_faq.get('similarity', 0)
            logger.info(f"Beste FAQ gefunden mit Ähnlichkeit: {similarity}")
            
            # Formatiere die Antwort
            response = f"📚 **Aus den FAQs:**\n\n**Frage:** {best_faq['question']}\n\n**Antwort:** {best_faq['answer']}"
            
            # Aktualisiere den Zustand mit relevanten Informationen
            state["curr_context"] = response
            state["aggregated_context"] = response
            
            # Informiere den Benutzer
            await cl.Message(content=f"⚠️ Mögliche passende FAQ gefunden (Ähnlichkeit: {similarity:.2%})").send()
            await cl.Message(content=f"Falls die Antwort nicht hilfreich ist, werde ich auch in der Dokumentation suchen.").send()
            await cl.Message(content=response).send()
            
            try:
                # Zeige FAQ-Speicheroption für die Frage an - fange Fehler ab, falls diese Funktion fehlschlägt
                await show_save_to_faq_option(query, best_faq['answer'])
            except Exception as e:
                logger.error(f"Fehler beim Anzeigen der FAQ-Speicheroption: {str(e)}")
                # Fahre fort, auch wenn die Speicheroption nicht angezeigt werden kann
            
            # Wir gehen nicht direkt zur Antwort, sondern fügen die FAQ-Antwort zum Kontext hinzu
            # und lassen den normalen Workflow weiterlaufen
            state["tool"] = "parallel_retrieval"
            return state
        
        # Keine passende FAQ gefunden
        logger.info("Keine ausreichend relevante FAQ gefunden, fahre mit normaler Suche fort")
        await cl.Message(content="ℹ️ Keine passende FAQ gefunden, suche in der Dokumentation...").send()
        
        # Setze auf paralleles Retrieval als nächsten Schritt
        state["tool"] = "parallel_retrieval"
        return state
        
    except Exception as e:
        logger.error(f"Fehler beim Überprüfen der FAQ-Datenbank: {str(e)}")
        await cl.Message(content="⚠️ Fehler beim Überprüfen der FAQ-Datenbank, fahre mit normaler Suche fort...").send()
        
        # Bei Fehler, fahre mit parallelem Retrieval fort
        state["tool"] = "parallel_retrieval"
        
        # Setze den Fehlerkontext
        state["error"] = f"Fehler bei der FAQ-Suche: {str(e)}"
        
        return state

@traceable(pass_config=False)
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

@traceable(pass_config=False)
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

@traceable(pass_config=False)
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

@traceable(pass_config=False)
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

async def check_content_grounding(distilled_content, original_context):
    """
    Überprüft, ob der gefilterte Inhalt im ursprünglichen Kontext verankert ist.
    
    Args:
        distilled_content: Der gefilterte Inhalt.
        original_context: Der ursprüngliche Kontext.
    
    Returns:
        Boolean: True, wenn der Inhalt verankert ist, sonst False.
    """
    # Falls der Inhalt leer ist, ist er per Definition verankert
    if not distilled_content.strip():
        return True
    
    class IsGrounded(BaseModel):
        grounded: bool = Field(description="Gibt an, ob der gefilterte Inhalt im ursprünglichen Kontext verankert ist.")
        explanation: str = Field(description="Erläuterung, warum der Inhalt verankert ist oder nicht.")
    
    prompt_template = """Du erhältst gefilterten Inhalt: {distilled_content} und den ursprünglichen Kontext: {original_context}.
    Prüfe, ob der gefilterte Inhalt tatsächlich im ursprünglichen Kontext verankert ist.
    Der gefilterte Inhalt sollte keine Informationen enthalten, die nicht zumindest sinngemäß im ursprünglichen Kontext vorhanden sind.
    
    Setze 'grounded' auf true, wenn der Inhalt vollständig im Kontext verankert ist.
    Setze 'grounded' auf false, wenn der Inhalt Informationen enthält, die nicht im Kontext enthalten sind.
    """
    
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["distilled_content", "original_context"],
    )
    
    from models.models_wrapper import get_llm
    llm = get_llm(temperature=0)
    chain = prompt | llm.with_structured_output(
        IsGrounded, 
        method="function_calling",
        strict=True
    )
    
    input_data = {
        "distilled_content": distilled_content,
        "original_context": original_context
    }
    
    result = chain.invoke(input_data)
    return result.grounded