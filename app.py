import os
import chainlit as cl
import signal
import sys
import logging
import warnings
import json
import asyncio
from typing import Dict, Any, List, Optional
import dotenv

# Import eigene Module 
from agent.support_summary_generator import support_summary_step
from config.config_manager import ConfigManager
from agent.state import PlanExecute
from agent.graph import compile_workflow
from vector_stores.retriever import create_retrievers, ensure_global_client
from vector_stores.weaviate_client import check_weaviate_data, create_weaviate_client
from langgraph.pregel import GraphRecursionError
from utils.graph_visualization import display_graph 

# Import ausgelagerte Module
from ui.ui_handlers import update_ui
from ui.evaluation_ui import add_evaluation_button, store_conversation_item
from vector_stores.db_manager import reconnect_weaviate_if_needed
from evaluation.realtime_evaluator import start_evaluation, evaluate_step, complete_evaluation

# Setze die Socket.IO Buffer-Größe, um "Too many packets in payload" zu vermeiden
os.environ["SOCKETIO_MAX_HTTP_BUFFER_SIZE"] = os.getenv("SOCKETIO_MAX_HTTP_BUFFER_SIZE", "1e9")

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize ConfigManager
config_manager = ConfigManager()
API_KEY = os.getenv('OPENAI_API_KEY')

# Lade Umgebungsvariablen
dotenv.load_dotenv()

# Globaler Client
client = ensure_global_client()

async def initialize_retrievers_and_check_data(client):
    """
    Überprüft den Datenbankstatus und initialisiert die Retriever.
    
    Args:
        client: Der Weaviate-Client für die Datenbankverbindung
        
    Returns:
        bool: True bei erfolgreicher Initialisierung, False sonst
    """
    try:
        # Überprüfe Daten
        data_status = check_weaviate_data(client)
        
        if not data_status["classes_exist"]:
            # Zeige direkt die Crawler-Option an, wenn die Klassen nicht existieren
            crawler_msg = cl.Message(content="⚠️ **Warnung**: Die Datenbank ist leer. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und Daten zu sammeln.")
            crawler_actions = [
                cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
            ]
            crawler_msg.actions = crawler_actions
            await crawler_msg.send()
            return False
        
        if not data_status["has_sufficient_data"]:
            # Zeige Warnung und Crawler-Option an, wenn nicht genügend Daten vorhanden sind
            crawler_msg = cl.Message(content="⚠️ **Warnung**: Es sind nicht ausreichend Daten in der Datenbank vorhanden. Die Suche könnte eingeschränkt sein. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und mehr Daten zu sammeln.")
            crawler_actions = [
                cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
            ]
            crawler_msg.actions = crawler_actions
            await crawler_msg.send()
        
        # Initialize vector store retrievers mit dem übergebenen Client
        from vector_stores.retriever import create_retrievers_with_client
        chunks_retriever, summaries_retriever, quotes_retriever = create_retrievers_with_client(client)
        cl.user_session.set("retrievers", {
            "chunks": chunks_retriever,
            "summaries": summaries_retriever,
            "quotes": quotes_retriever
        })
        
        # Send welcome message
        await cl.Message(content="Willkommen! Ich bin bereit, Ihre Fragen über Moodle zu beantworten ✅. Was möchten Sie wissen oder tun?").send()
        return True
    except Exception as e:
        error_message = str(e)
        logger_message = f"Fehler beim Initialisieren der Retriever: {error_message}"
        logger.error(logger_message)
        
        if "insufficient data" in error_message.lower():
            crawler_msg = cl.Message(content="⚠️ **Warnung**: Nicht genügend Daten in der Datenbank. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und Daten zu sammeln.")
            crawler_actions = [
                cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
            ]
            crawler_msg.actions = crawler_actions
            await crawler_msg.send()
        else:
            await cl.Message(content=f"⚠️ **Fehler**: Bei der Initialisierung ist ein Problem aufgetreten: {error_message}. Bitte überprüfen Sie die Verbindung zur Vektordatenbank.").send()
        return False

@cl.on_chat_start
async def start():
    """Initialisierung beim Chatstart."""
    # Einstellungen laden und senden
    settings = await config_manager.load_settings()
    chat_settings = cl.ChatSettings(settings)
    await chat_settings.send()
    
    # Füge Admin-Button für Datenbankmanagement hinzu
    actions = [
        cl.Action(name="db_management", payload={"action": "show"}, label="📊 Datenbank-Management")
    ]
    admin_msg = cl.Message(content="")
    admin_msg.actions = actions
    await admin_msg.send()
    
    # Füge Evaluierungsbutton hinzu
    await add_evaluation_button()
    
    # Initialisiere Retriever und überprüfe Daten
    await initialize_retrievers_and_check_data(client)

@cl.on_settings_update
async def update_settings(settings):
    """Callback für Einstellungsänderungen."""
    await config_manager.update_settings(settings)

@cl.on_message
async def on_message(message: cl.Message):
    """Handler für Benutzernachrichten."""
    
    # Stelle sicher, dass der Weaviate-Client verbunden ist
    await reconnect_weaviate_if_needed()
    
    # Hole Retriever aus der User-Session
    retrievers = cl.user_session.get("retrievers")
    if not retrievers:
        await cl.Message(content="⚠️ Die Retriever wurden nicht initialisiert. Starten Sie die Anwendung neu.").send()
        return
    
    openai_api_key = config_manager.get_setting_value("OPENAI_API_KEY")
    
    if not openai_api_key:
        await cl.Message(content="Bitte setzen Sie Ihren OpenAI API-Schlüssel in den Einstellungen.").send()
        return
    
    try:
        await process_message(message.content)
    except Exception as e:
        await cl.Message(content=f"Ein Fehler ist aufgetreten: {str(e)}").send()

@cl.step(name="Process Message", type="process")
async def process_message(message_content: str):
    """
    Verarbeitet eine Nachricht und führt den Workflow aus.
    
    Args:
        message_content: Der Inhalt der Nachricht
    """
    # Kompiliere den Workflow
    workflow = await compile_workflow()
    # Visualisiere den Workflow
    display_graph(workflow)
    # Initialisiere den Zustand
    initial_state = PlanExecute(
        question=message_content,
        anonymized_question="",
        query_to_retrieve_or_answer="",
        plan=[],
        past_steps=[],
        mapping={},
        curr_context="",
        aggregated_context="",
        tool="",
        response="",
        curr_state=""
    )
    
    # Starte die Echtzeit-Evaluierung
    await start_evaluation(message_content)
    
    # Führe den Workflow aus
    config = {"recursion_limit": 25}
    step_output = None
    astream_generator = None
    
    try:
        # Speichere den Generator in einer Variablen, damit wir ihn später schließen können
        astream_generator = workflow.astream(initial_state, config=config)
        
        async for current_output in astream_generator:
            step_output = current_output
            last_key = next(iter(step_output))
            current_state = step_output[last_key]
            
            # Aktualisiere die UI
            await update_ui(current_state)
            
            # Evaluiere den aktuellen Schritt
            if "curr_state" in current_state:
                # Extrahiere den aktuellen Schrittnamen
                curr_state = current_state["curr_state"]
                logger.info(f"Aktueller Schritt: {curr_state}")
                
                # Evaluiere den Schritt
                await evaluate_step(current_state, curr_state)
            
    except GraphRecursionError as e:
        if step_output:
            last_key = next(iter(step_output))
            res = await support_summary_step(step_output[last_key])
            logger.warning("Der Workflow hat das Rekursionslimit erreicht.")
            await cl.Message(content="Der Workflow hat das Rekursionslimit erreicht.").send()
            await cl.Message(content=res).send()
        else:
            logger.error(f"Rekursionsfehler ohne gültigen Ausgabezustand: {str(e)}")
            await cl.Message(content="Ein Fehler ist aufgetreten: Der Workflow hat das Rekursionslimit erreicht, konnte aber keine Zusammenfassung erstellen.").send()
        return
    except Exception as e:
        logger.error(f"Fehler bei der Ausführung des Workflows: {str(e)}", exc_info=True)
        await cl.Message(content=f"Ein Fehler ist aufgetreten: {str(e)}").send()
        return
    finally:
        # Stelle sicher, dass der Generator ordnungsgemäß geschlossen wird
        if astream_generator:
            try:
                await astream_generator.aclose()
            except Exception as close_error:
                logger.error(f"Fehler beim Schließen des Generators: {str(close_error)}")
    
    # Sende die endgültige Antwort, nur wenn step_output existiert
    if step_output:
        last_key = next(iter(step_output))
        final_state = step_output[last_key]
        final_response = final_state.get("response", "Ich konnte keine Antwort generieren. Bitte formulieren Sie Ihre Frage um.")
        await cl.Message(content=final_response).send()
        
        # Speichere das Frage-Antwort-Paar für die Evaluierung
        store_conversation_item(
            question=message_content,
            answer=final_response,
            context=final_state.get("aggregated_context", "")
        )
        
        # Schließe die Echtzeit-Evaluierung ab
        await complete_evaluation()
    else:
        await cl.Message(content="Ich konnte keine Antwort generieren. Bitte formulieren Sie Ihre Frage um.").send()

@cl.action_callback("confirm_crawl")
async def on_confirm_crawl(action):
    """Startet den Web-Crawling-Prozess mit den angegebenen Parametern."""
    # Extrahiere Parameter aus dem JSON-Wert
    params = json.loads(action.value)
    await action.remove()
    
    temp_client = None
    try:
        # Erstelle Weaviate-Client zum Prüfen der Datenbank
        temp_client = create_weaviate_client()
        
        # Initialisiere Retriever und überprüfe Daten mit dem temporären Client
        await initialize_retrievers_and_check_data(temp_client)
    finally:
        # Stelle sicher, dass der temporäre Client geschlossen wird
        if temp_client:
            try:
                temp_client.close()
                logger.info("Temporärer Weaviate-Client in confirm_crawl geschlossen.")
            except Exception as close_error:
                logger.error(f"Fehler beim Schließen des temporären Weaviate-Clients in confirm_crawl: {str(close_error)}")

# Signal-Handler zum Schließen der Weaviate-Verbindung beim Beenden der Anwendung
def signal_handler(sig, frame):
    """Schließt die Weaviate-Verbindung beim Beenden der Anwendung."""
    print("\nAnwendung wird beendet, schließe Verbindungen...")
    try:
        client.close()
        print("Weaviate-Verbindung geschlossen.")
    except Exception as e:
        print(f"Fehler beim Schließen der Weaviate-Verbindung: {str(e)}")
    sys.exit(0)

# Registriere Signal-Handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    cl.run()