import os
import asyncio
import logging
import chainlit as cl
from config.config_manager import ConfigManager
from agent.graph import compile_workflow
from agent.state import PlanExecute
from langgraph.pregel import GraphRecursionError
from utils.graph_visualization import display_graph
from agent.support_summary_generator import support_summary_step
from vector_stores.db_manager import WeaviateManager
from vector_stores.retriever import RetrieverFactory
from crawling.crawler_manager import CrawlerManager
from ui.chainlit_manager import ChainlitUIManager
import signal
import dotenv

# Lade Umgebungsvariablen
dotenv.load_dotenv()

# Setze die Socket.IO Buffer-Größe, um "Too many packets in payload" zu vermeiden
os.environ["SOCKETIO_MAX_HTTP_BUFFER_SIZE"] = os.getenv("SOCKETIO_MAX_HTTP_BUFFER_SIZE", "1e9")

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialisiere Manager
config_manager = ConfigManager()
db_manager = WeaviateManager()
crawler_manager = CrawlerManager()
ui_manager = ChainlitUIManager()

@cl.on_chat_start
async def start():
    """Initialisiert den Chat beim Start."""
    # Lade und sende Einstellungen
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
    
    # Überprüfe Weaviate-Verbindung und Daten
    try:
        # Überprüfe Daten
        data_status = db_manager.check_data()
        
        if not data_status["classes_exist"]:
            # Zeige direkt die Crawler-Option an, wenn die Klassen nicht existieren
            await ui_manager.show_crawler_options(
                "⚠️ **Warnung**: Die Datenbank ist leer. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und Daten zu sammeln."
            )
            return
        
        if not data_status["has_sufficient_data"]:
            # Zeige Warnung und Crawler-Option an, wenn nicht genügend Daten vorhanden sind
            await ui_manager.show_crawler_options(
                "⚠️ **Warnung**: Es sind nicht ausreichend Daten in der Datenbank vorhanden. Die Suche könnte eingeschränkt sein. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und mehr Daten zu sammeln."
            )
        
        # Initialize vector store retrievers
        retriever_factory = RetrieverFactory(config_manager.get_setting_value("OPENAI_API_KEY"))
        chunks_retriever, summaries_retriever, quotes_retriever = retriever_factory.create_retrievers()
        cl.user_session.set("retrievers", {
            "chunks": chunks_retriever,
            "summaries": summaries_retriever,
            "quotes": quotes_retriever
        })
        
        # Send welcome message
        await cl.Message(content="Willkommen! Ich bin bereit, Ihre Fragen über Moodle zu beantworten ✅. Was möchten Sie wissen oder tun?").send()
    except Exception as e:
        error_message = str(e)
        logger_message = f"Fehler beim Initialisieren der Retriever: {error_message}"
        logger.error(logger_message)
        
        if "insufficient data" in error_message.lower():
            await ui_manager.show_crawler_options(
                "⚠️ **Warnung**: Nicht genügend Daten in der Datenbank. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und Daten zu sammeln."
            )
        else:
            await cl.Message(content=f"⚠️ **Fehler**: Bei der Initialisierung ist ein Problem aufgetreten: {error_message}. Bitte überprüfen Sie die Verbindung zur Vektordatenbank.").send()

@cl.on_settings_update
async def update_settings(settings):
    """Handler für Einstellungsänderungen."""
    await config_manager.update_settings(settings)

@cl.action_callback("run_crawler")
async def on_run_crawler(action):
    """Callback für den Start des Crawlers."""
    await action.remove()
    await ui_manager.show_chunking_strategies()

@cl.action_callback("select_strategy")
async def select_strategy_callback(action):
    """Callback für die Auswahl der Chunking-Strategie."""
    chunking_strategy = action.payload["strategy"]
    await action.remove()
    
    strategy_names = {
        "recursive": "Rekursive Aufteilung",
        "semantic": "Semantische Aufteilung (nach Überschriften)",
        "hierarchical": "Hierarchische Aufteilung (nach Kapiteln)"
    }
    
    confirm_msg = cl.Message(content=f"Sie haben die **{strategy_names.get(chunking_strategy, chunking_strategy)}** gewählt. Möchten Sie mit dem Crawling beginnen?")
    
    confirm_actions = [
        cl.Action(name="confirm_crawl", payload={"strategy": chunking_strategy}, label="✅ Ja, starten"),
        cl.Action(name="cancel_crawl", payload={}, label="❌ Abbrechen")
    ]
    
    confirm_msg.actions = confirm_actions
    await confirm_msg.send()

@cl.action_callback("confirm_crawl")
async def on_confirm_crawl(action):
    """Callback für die Bestätigung des Crawlings."""
    chunking_strategy = action.payload.get("strategy", "recursive")
    await action.remove()
    
    # Starte den Crawler-Prozess
    status_msg = cl.Message(content="🔄 Der Crawler wird gestartet... Bitte warten Sie.")
    await status_msg.send()
    
    # Crawl-URL
    url = "https://docs.moodle.org/dev/Main_Page"
    
    # Starten des Crawlers asynchron
    result = await crawler_manager.run_crawler(
        url=url,
        chunking_strategy=chunking_strategy,
        depth=3
    )
    
    if result["status"] == "success":
        await cl.Message(content="✅ Der Crawler wurde erfolgreich ausgeführt. Die gesammelten Daten wurden in der Datenbank gespeichert.").send()
        
        # Initialisiere die Retriever neu
        retriever_factory = RetrieverFactory(config_manager.get_setting_value("OPENAI_API_KEY"))
        chunks_retriever, summaries_retriever, quotes_retriever = retriever_factory.create_retrievers()
        cl.user_session.set("retrievers", {
            "chunks": chunks_retriever,
            "summaries": summaries_retriever,
            "quotes": quotes_retriever
        })
        
        await cl.Message(content="🔄 Die Retriever wurden neu initialisiert. Ich bin bereit, Ihre Fragen zu beantworten.").send()
    else:
        await cl.Message(content=f"⚠️ Bei der Ausführung des Crawlers ist ein Fehler aufgetreten: {result.get('message', 'Unbekannter Fehler')}").send()

@cl.action_callback("db_management")
async def on_db_management(action):
    """Handler für Datenbank-Management-Aktionen."""
    await action.remove()
    await ui_manager.show_db_management()

@cl.action_callback("db_visualize")
async def on_db_visualize(action):
    """Handler für Datenbank-Visualisierung."""
    await action.remove()
    await ui_manager.show_db_visualization()

@cl.action_callback("db_clear")
async def on_db_clear(action):
    """Handler für das Löschen ausgewählter Daten."""
    await action.remove()
    
    # Zeige Optionen für das Löschen von Datenklassen an
    try:
        data_status = db_manager.check_data()
        
        if not data_status["classes_exist"]:
            await cl.Message(content="⚠️ Es sind keine Klassen in der Datenbank vorhanden, die gelöscht werden können.").send()
            return
        
        actions = []
        
        # Erstelle Aktionen für jede Klasse
        for class_name, count in data_status["details"].items():
            if count > 0:
                actions.append(cl.Action(
                    name="db_clear_class", 
                    payload={"class": class_name}, 
                    label=f"{class_name} ({count} Objekte)"
                ))
        
        # Abbrechen-Aktion
        actions.append(cl.Action(name="db_clear_cancel", payload={}, label="❌ Abbrechen"))
        
        # Nachricht mit Optionen
        msg = cl.Message(content="Bitte wählen Sie die Klassen, die Sie löschen möchten:")
        msg.actions = actions
        await msg.send()
        
    except Exception as e:
        logger.error(f"Fehler beim Anzeigen der Löschoptionen: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler beim Laden der Löschoptionen: {str(e)}").send()

@cl.action_callback("db_clear_all")
async def on_db_clear_all(action):
    """Handler für das Löschen aller Daten."""
    await action.remove()
    
    # Bestätigung anfordern
    confirm_msg = cl.Message(content="⚠️ **Warnung**: Sie sind dabei, ALLE Daten aus der Datenbank zu löschen. Diese Aktion kann nicht rückgängig gemacht werden. Möchten Sie fortfahren?")
    
    confirm_actions = [
        cl.Action(name="db_clear_all_confirm", payload={}, label="⚠️ Ja, ALLE Daten löschen"),
        cl.Action(name="db_clear_cancel", payload={}, label="❌ Abbrechen")
    ]
    
    confirm_msg.actions = confirm_actions
    await confirm_msg.send()

@cl.action_callback("db_clear_all_confirm")
async def on_db_clear_all_confirm(action):
    """Handler für die Bestätigung des Löschens aller Daten."""
    await action.remove()
    
    try:
        # Löschen aller Klassen
        for class_name in ["Document", "Chunk", "Summary", "Quote"]:
            try:
                if db_manager.client.collections.exists(class_name):
                    db_manager.client.collections.delete(class_name)
                    await cl.Message(content=f"✅ Klasse '{class_name}' erfolgreich gelöscht.").send()
            except Exception as e:
                logger.error(f"Fehler beim Löschen der Klasse '{class_name}': {str(e)}")
                await cl.Message(content=f"⚠️ Fehler beim Löschen der Klasse '{class_name}': {str(e)}").send()
        
        # Erstelle das Schema neu
        success = db_manager.create_schema()
        
        if success:
            await cl.Message(content="✅ Alle Daten wurden gelöscht und das Schema wurde neu erstellt.").send()
        else:
            await cl.Message(content="⚠️ Alle Daten wurden gelöscht, aber es gab ein Problem beim Neuerstellen des Schemas.").send()
            
        # Aktualisiere die Datenbank-Ansicht
        await ui_manager.show_db_management()
        
    except Exception as e:
        logger.error(f"Fehler beim Löschen aller Daten: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler beim Löschen aller Daten: {str(e)}").send()

@cl.action_callback("db_clear_class")
async def on_db_clear_class(action):
    """Handler für das Löschen einer bestimmten Klasse."""
    class_name = action.payload.get("class")
    await action.remove()
    
    # Bestätigung anfordern
    confirm_msg = cl.Message(content=f"⚠️ **Warnung**: Sie sind dabei, alle Daten aus der Klasse '{class_name}' zu löschen. Diese Aktion kann nicht rückgängig gemacht werden. Möchten Sie fortfahren?")
    
    confirm_actions = [
        cl.Action(name="db_clear_class_confirm", payload={"class": class_name}, label=f"⚠️ Ja, '{class_name}' löschen"),
        cl.Action(name="db_clear_cancel", payload={}, label="❌ Abbrechen")
    ]
    
    confirm_msg.actions = confirm_actions
    await confirm_msg.send()

@cl.action_callback("db_clear_class_confirm")
async def on_db_clear_class_confirm(action):
    """Handler für die Bestätigung des Löschens einer Klasse."""
    class_name = action.payload.get("class")
    await action.remove()
    
    try:
        # Löschen der Klasse
        if db_manager.client.collections.exists(class_name):
            # Lösche alle Objekte in der Klasse
            db_manager.client.collections.get(class_name).objects.delete_many(
                where={"path": ["id"], "operator": "NotEqual", "valueText": "dummy"}
            )
            await cl.Message(content=f"✅ Alle Objekte in der Klasse '{class_name}' wurden gelöscht.").send()
        else:
            await cl.Message(content=f"⚠️ Die Klasse '{class_name}' existiert nicht.").send()
            
        # Aktualisiere die Datenbank-Ansicht
        await ui_manager.show_db_management()
        
    except Exception as e:
        logger.error(f"Fehler beim Löschen der Klasse '{class_name}': {str(e)}")
        await cl.Message(content=f"⚠️ Fehler beim Löschen der Klasse '{class_name}': {str(e)}").send()

@cl.action_callback("db_clear_cancel")
async def on_db_clear_cancel(action):
    """Handler für das Abbrechen des Löschvorgangs."""
    await action.remove()
    await cl.Message(content="❌ Löschvorgang abgebrochen.").send()
    await ui_manager.show_db_management()

@cl.action_callback("app_restart")
async def on_app_restart(action):
    """Handler für den Neustart der Anwendung."""
    await action.remove()
    
    await cl.Message(content="🔄 Die Anwendung wird neu gestartet...").send()
    
    try:
        # Schließe Weaviate-Client
        db_manager.close()
        
        # Initialisiere neu
        cl.user_session.set("retrievers", None)
        
        # Starte die Chat-Sitzung neu
        await start()
        
        await cl.Message(content="✅ Die Anwendung wurde erfolgreich neu gestartet.").send()
    except Exception as e:
        logger.error(f"Fehler beim Neustart der Anwendung: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler beim Neustart der Anwendung: {str(e)}").send()

@cl.on_message
async def on_message(message: cl.Message):
    """Handler für Benutzernachrichten."""
    
    # Stelle sicher, dass der Weaviate-Client verbunden ist
    if not db_manager.is_connected():
        db_manager.connect()
    
    # Hole Retriever aus der User-Session
    retrievers = cl.user_session.get("retrievers")
    if not retrievers:
        await cl.Message(content="⚠️ Die Retriever wurden nicht initialisiert. Starten Sie die Anwendung neu.").send()
        return
    
    openai_api_key = config_manager.get_setting_value("OPENAI_API_KEY")
    
    if not openai_api_key:
        await cl.Message(content="Please set your OpenAI API key in the settings.").send()
        return
    
    try:
        await process_message(message.content)
    except Exception as e:
        await cl.Message(content=f"An error occurred: {str(e)}").send()

@cl.step(name="Process Message", type="process")
async def process_message(message_content: str):
    """Verarbeitet eine Nachricht und führt den Workflow aus."""
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
        response=""
    )
    
    # Führe den Workflow aus
    config = {"recursion_limit": 25}
    try:
        async for step_output in workflow.astream(initial_state, config=config):
            last_key = next(iter(step_output))
            await ui_manager.update_workflow_step(step_output[last_key])
    except GraphRecursionError:
        res = await support_summary_step(step_output[last_key])
        await cl.Message(content="The workflow has reached the recursion limit.").send()
        await cl.Message(content=res).send()
        return
    
    # Sende die finale Antwort
    final_response = step_output[last_key].get("response", "I couldn't generate a response. Please try rephrasing your question.")
    await cl.Message(content=final_response).send()

def signal_handler(sig, frame):
    """Signal-Handler für sauberes Beenden."""
    logger.info("Signal erhalten. Beende Anwendung...")
    # Schließe Weaviate-Verbindung
    db_manager.close()
    exit(0)

# Main-Ausführung
if __name__ == "__main__":
    # Registriere Signal-Handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)