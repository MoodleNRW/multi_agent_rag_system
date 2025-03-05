import os
import chainlit as cl
from agent.support_summary_generator import support_summary_step
from config.config_manager import ConfigManager
from agent.state import PlanExecute
from agent.graph import compile_workflow
from vector_stores.retriever import create_retrievers, ensure_global_client
from vector_stores.weaviate_client import create_weaviate_client, ensure_weaviate_connection, check_weaviate_data
from langgraph.pregel import GraphRecursionError
from utils.graph_visualization import display_graph 
import subprocess
import logging
import weaviate
import plotly.express as px
import pandas as pd
import json
import time
import asyncio
import re
import urllib.parse
import dotenv
from datetime import datetime
from chainlit.input_widget import Select
from langchain_core.messages.system import SystemMessage
from langchain_core.messages.human import HumanMessage
from langchain_core.messages.ai import AIMessage
import weaviate.classes as wvc
import uuid
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt
import io
import numpy as np
from langchain.chains.question_answering import load_qa_chain
from models.models_wrapper import get_llm

# Setze die Socket.IO Buffer-Größe, um "Too many packets in payload" zu vermeiden
os.environ["SOCKETIO_MAX_HTTP_BUFFER_SIZE"] = os.getenv("SOCKETIO_MAX_HTTP_BUFFER_SIZE", "1e9")

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize ConfigManager
config_manager = ConfigManager()
API_KEY = os.getenv('OPENAI_API_KEY')

dotenv.load_dotenv()

# Erstelle Weaviate-Client
client = ensure_global_client()

def ensure_weaviate_connection(weaviate_client):
    """Stellt sicher, dass der Weaviate-Client verbunden ist."""
    global client
    
    try:
        if not weaviate_client.is_connected():
            weaviate_client.connect()
        return True
    except Exception as e:
        logger.error(f"Fehler bei der Verbindung mit Weaviate: {str(e)}")
        try:
            # Versuche, den Client zu schließen, falls er existiert
            weaviate_client.close()
        except:
            pass
        # Versuche, einen neuen Client zu erstellen
        client = ensure_global_client()
        return client is not None

@cl.on_chat_start
async def start():
    # Load and send settings
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
        data_status = check_weaviate_data(client)
        
        if not data_status["classes_exist"]:
            # Zeige direkt die Crawler-Option an, wenn die Klassen nicht existieren
            crawler_msg = cl.Message(content="⚠️ **Warnung**: Die Datenbank ist leer. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und Daten zu sammeln.")
            crawler_actions = [
                cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
            ]
            crawler_msg.actions = crawler_actions
            await crawler_msg.send()
            return
        
        if not data_status["has_sufficient_data"]:
            # Zeige Warnung und Crawler-Option an, wenn nicht genügend Daten vorhanden sind
            crawler_msg = cl.Message(content="⚠️ **Warnung**: Es sind nicht ausreichend Daten in der Datenbank vorhanden. Die Suche könnte eingeschränkt sein. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und mehr Daten zu sammeln.")
            crawler_actions = [
                cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
            ]
            crawler_msg.actions = crawler_actions
            await crawler_msg.send()
        
        # Initialize vector store retrievers
        chunks_retriever, summaries_retriever, quotes_retriever = create_retrievers()
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
            crawler_msg = cl.Message(content="⚠️ **Warnung**: Nicht genügend Daten in der Datenbank. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und Daten zu sammeln.")
            crawler_actions = [
                cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
            ]
            crawler_msg.actions = crawler_actions
            await crawler_msg.send()
        else:
            await cl.Message(content=f"⚠️ **Fehler**: Bei der Initialisierung ist ein Problem aufgetreten: {error_message}. Bitte überprüfen Sie die Verbindung zur Vektordatenbank.").send()

async def show_crawler_option():
    """Zeigt eine Schaltfläche zum Ausführen des Crawlers an, wenn nicht genügend Daten vorhanden sind."""
    msg = cl.Message(content="📥 **Crawler starten**\n\nDer Crawler sammelt Daten von der Moodle-Dokumentation, um fundierte Antworten auf Ihre Fragen geben zu können. Klicken Sie auf die Schaltfläche unten, um den Prozess zu starten.")
    
    actions = [
        cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
    ]
    
    msg.actions = actions
    await msg.send()

@cl.action_callback("run_crawler")
async def on_run_crawler(action):
    """Callback für den Start des Crawlers."""
    await action.remove()
    
    # Frage nach der Chunking-Strategie
    strategy_actions = [
        cl.Action(name="select_strategy", payload={"strategy": "recursive"}, label="Rekursiv (Standard)"),
        cl.Action(name="select_strategy", payload={"strategy": "semantic"}, label="Semantisch (Überschriften)"),
        cl.Action(name="select_strategy", payload={"strategy": "hierarchical"}, label="Hierarchisch (Kapitel)")
    ]
    
    strategy_msg = cl.Message(content="Bitte wählen Sie eine Chunking-Strategie für die Verarbeitung der Dokumente:")
    strategy_msg.actions = strategy_actions
    await strategy_msg.send()
    
    # Die Antwort wird über select_strategy_callback verarbeitet

@cl.action_callback("select_strategy")
async def select_strategy_callback(action):
    """Callback für die Auswahl der Chunking-Strategie."""
    chunking_strategy = action.payload["strategy"]
    await action.remove()
    
    strategy_names = {
        "recursive": "Rekursiv",
        "semantic": "Semantisch",
        "hierarchical": "Hierarchisch"
    }
    
    selected_strategy = strategy_names.get(chunking_strategy, 'Unbekannte')
    confirm_msg = cl.Message(content=f"Sie haben die {selected_strategy} Strategie ausgewählt. Der Crawler wird nun gestartet...")
    await confirm_msg.send()
    
    try:
        # Angepasste URL für moodlenrw.de
        url = "https://moodlenrw.de/"
        depth = 5  # Begrenzung der Anzahl der Seiten
        
        # Status-Nachricht
        update_msg = cl.Message(content=f"Der Crawler läuft mit der {selected_strategy} Chunking-Strategie und sammelt Daten von https://moodlenrw.de/... Dies kann einige Minuten dauern.")
        await update_msg.send()
        
        # Führe den Crawler in einem separaten Prozess aus mit der ausgewählten Strategie
        process = subprocess.Popen(
            ["python", "moodledoc_crawler.py", url, str(depth), chunking_strategy],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            bufsize=1  # Zeilenorientiert gepuffert
        )
        
        # Queue für die Sammlung der Ausgaben
        stdout_queue = asyncio.Queue()
        stderr_queue = asyncio.Queue()
        
        # Funktionen zum asynchronen Lesen der Ausgabestreams
        async def read_stream(stream, queue):
            while True:
                line = stream.readline()
                if not line:
                    break
                await queue.put(line)
            await queue.put(None)  # Signal für Ende des Streams
        
        # Starte die Leser für stdout und stderr
        asyncio.create_task(read_stream(process.stdout, stdout_queue))
        asyncio.create_task(read_stream(process.stderr, stderr_queue))
        
        # Sammle die Ausgaben für spätere Verwendung
        all_stdout = []
        all_stderr = []
        
        # Periodic status update function
        async def update_status():
            start_time = time.time()
            count = 0
            last_output_time = time.time()
            output_buffer = []
            progress_pattern = re.compile(r'\[Fortschritt\]\s+(\d+\.\d+)%')
            current_progress = 0
            
            while process.poll() is None:
                count += 1
                
                # Sammle neue Ausgaben und zeige sie an
                while not stdout_queue.empty():
                    line = await stdout_queue.get()
                    if line is None:
                        break
                    all_stdout.append(line)
                    output_buffer.append(line)
                    last_output_time = time.time()
                    
                    # Extrahiere den Fortschritt, wenn die Zeile ein Fortschrittsupdate enthält
                    progress_match = progress_pattern.search(line)
                    if progress_match:
                        try:
                            current_progress = float(progress_match.group(1))
                        except ValueError:
                            pass
                
                # Zeige Ausgaben häufiger an - bei jeder neuen Ausgabe oder alle 3 Sekunden
                if output_buffer and (len(output_buffer) >= 1 or (time.time() - last_output_time) >= 3):
                    # Mehr Zeilen anzeigen
                    output_text = "".join(output_buffer[-15:])  # Zeige maximal die letzten 15 Zeilen
                    log_msg = cl.Message(content=f"📋 Crawler-Aktivität:\n```\n{output_text}\n```")
                    await log_msg.send()
                    output_buffer = []
                
                # Status-Update mit Fortschrittsanzeige
                status_msg = cl.Message(content=f"⏳ Crawler-Status: {current_progress:.1f}% abgeschlossen... (Laufzeit: {int(time.time() - start_time)} Sekunden)")
                await status_msg.send()
                
                # Kürzeres Intervall zwischen den Updates
                await asyncio.sleep(5)
        
        # Starte den Status-Update-Task
        update_task = asyncio.create_task(update_status())
        
        # Prozess mit Timeout überwachen
        try:
            # Warte auf den Prozess-Abschluss oder Timeout
            exit_code = None
            timeout_time = time.time() + 300  # 5 Minuten Timeout
            
            while exit_code is None and time.time() < timeout_time:
                # Prüfe, ob der Prozess beendet ist
                exit_code = process.poll()
                
                # Lese alle verfügbaren stderr Nachrichten
                while not stderr_queue.empty():
                    line = await stderr_queue.get()
                    if line is None:
                        break
                    all_stderr.append(line)
                
                # Kurze Pause, um CPU-Last zu reduzieren
                await asyncio.sleep(0.5)
            
            # Beende den Update-Task
            update_task.cancel()
            
            # Wenn der Prozess immer noch läuft, wurde der Timeout erreicht
            if exit_code is None:
                process.kill()
                timeout_msg = cl.Message(content="⏱️ Timeout: Der Crawler-Prozess wurde wegen Zeitüberschreitung beendet.")
                await timeout_msg.send()
                await cl.Message(content="⚠️ Der Crawler wurde nach 5 Minuten automatisch beendet. Dies kann bei großen Datenmengen normal sein.").send()
                await cl.Message(content="Bitte starten Sie die Anwendung neu, um zu überprüfen, ob Daten erfolgreich geladen wurden.").send()
                return
            
            # Zeige die letzten Ausgaben an
            stdout_text = "".join(all_stdout[-20:])  # Letzte 20 Zeilen
            if stdout_text.strip():
                await cl.Message(content=f"📋 Letzte Crawler-Ausgaben:\n```\n{stdout_text}\n```").send()
            
            # Prüfe, ob der Crawler erfolgreich abgeschlossen wurde
            crawler_complete = False
            error_message = None
            
            # Suche nach dem speziellen Status-Marker
            for line in all_stdout:
                if "[STATUS] CRAWLING_COMPLETE" in line:
                    crawler_complete = True
                    break
                if "[STATUS] CRAWLING_ERROR" in line:
                    error_parts = line.split("[STATUS] CRAWLING_ERROR:")
                    if len(error_parts) > 1:
                        error_message = error_parts[1].strip()
                    break
            
            # Zeige alle Fehler an
            stderr_text = "".join(all_stderr)
            if stderr_text.strip():
                await cl.Message(content=f"⚠️ Crawler-Fehler:\n```\n{stderr_text[:500]}{'...' if len(stderr_text) > 500 else ''}\n```").send()
            
            if exit_code == 0 and crawler_complete:
                completion_msg = cl.Message(content="✅ Crawler-Prozess abgeschlossen. Daten werden in die Datenbank geladen...")
                await completion_msg.send()
                success_msg = cl.Message(content="✅ Der Crawler wurde erfolgreich ausgeführt. Daten wurden in die Vektordatenbank geladen.")
                await success_msg.send()
                
                try:
                    # Initialisiere die Retriever nach dem Crawling
                    chunks_retriever, summaries_retriever, quotes_retriever = create_retrievers()
                    cl.user_session.set("retrievers", {
                        "chunks": chunks_retriever,
                        "summaries": summaries_retriever,
                        "quotes": quotes_retriever
                    })
                    
                    await cl.Message(content="Willkommen! Ich bin bereit, Ihre Fragen über Moodle zu beantworten ✅. Was möchten Sie wissen oder tun?").send()
                except Exception as e:
                    logger.error(f"Fehler beim Neuinitialisieren der Retriever: {str(e)}")
                    await cl.Message(content=f"Der Crawler wurde ausgeführt, aber es gab ein Problem beim Laden der Daten: {str(e)}. Bitte starten Sie die Anwendung neu.").send()
            else:
                error_msg = cl.Message(content=f"❌ Crawler-Prozess mit Fehlercode {exit_code} beendet.")
                await error_msg.send()
                logger.error(f"Crawler-Fehler: {stderr_text}")
                await cl.Message(content=f"⚠️ Bei der Ausführung des Crawlers ist ein Fehler aufgetreten. Bitte überprüfen Sie die Logs.").send()
        
        except Exception as e:
            # Fehlerbehandlung für jegliche andere Ausnahmen
            update_task.cancel()
            if process.poll() is None:
                process.kill()
            
            logger.error(f"Fehler beim Überwachen des Crawler-Prozesses: {str(e)}")
            await cl.Message(content=f"⚠️ Es ist ein Fehler aufgetreten: {str(e)}").send()
    
    except Exception as e:
        logger.error(f"Fehler beim Ausführen des Crawlers: {str(e)}")
        await cl.Message(content=f"⚠️ Bei der Ausführung des Crawlers ist ein Fehler aufgetreten: {str(e)}").send()

@cl.on_settings_update
async def update_settings(settings):
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
        await cl.Message(content="Please set your OpenAI API key in the settings.").send()
        return
    
    try:
        await process_message(message.content)
    except Exception as e:
        await cl.Message(content=f"An error occurred: {str(e)}").send()

@cl.step(name="Process Message", type="process")
async def process_message(message_content: str):
    # Compile the workflow
    workflow = await compile_workflow()
    # Visualize the workflow
    display_graph(workflow)
    # Initialize the state
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
    
    # Execute the workflow
    config = {"recursion_limit": 25}
    try:
   
        async for step_output in workflow.astream(initial_state, config=config):
            last_key = next(iter(step_output))
            await update_ui(step_output[last_key])
    except GraphRecursionError:
        res = await support_summary_step(step_output[last_key])
        print(res)
        await cl.Message(content="The workflow has reached the recursion limit.").send()
        await cl.Message(content=res).send()

        
        return

        
    
    # Send the final response
    final_response = step_output[last_key].get("response", "I couldn't generate a response. Please try rephrasing your question.")
    await cl.Message(content=final_response).send()

async def update_ui(step_output):
    current_state = step_output.get("curr_state", "")
    print("UPDATE UI", step_output)
    if current_state in ["retrieve_chunks", "retrieve_summaries", "retrieve_quotes"]:
        await cl.Message(content=f"Retrieving information: {current_state}").send()
    elif current_state == "answer":
        await cl.Message(content="Generating answer based on retrieved information...").send()
    elif current_state == "planner":
        await cl.Message(content="Planning next steps...").send()
    elif current_state == "anonymize_question":
        await cl.Message(content="Anonymizing the question...").send()
    elif current_state == "de_anonymize_plan":
        await cl.Message(content="De-anonymizing the plan...").send()
    elif current_state == "break_down_plan":
        await cl.Message(content="Breaking down the plan into smaller steps...").send()
    elif current_state == "task_handler":
        await cl.Message(content="Deciding on the next action...").send()
    elif current_state == "replan":
        await cl.Message(content="Adjusting the plan based on new information...").send()
    elif current_state == "get_final_answer":
        await cl.Message(content="Preparing the final answer...").send()

    # You can add more detailed logging here if needed
    cl.Task(title=current_state, status=cl.TaskStatus.RUNNING)

@cl.action_callback("db_management")
async def on_db_management(action):
    """Handler für Datenbank-Management-Aktionen."""
    await action.remove()
    
    # Erstelle temporären Weaviate-Client für die Inspektion
    temp_client = None
    try:
        # Erstelle temporären Weaviate-Client für die Inspektion
        temp_client = create_weaviate_client()
        
        # Überprüfe Daten
        data_status = check_weaviate_data(temp_client)
        
        # Erstelle Aktionsschaltflächen
        actions = []
        
        # Visualisierungsaktion
        actions.append(cl.Action(name="db_visualize", payload={"action": "visualize"}, label="📊 Daten visualisieren"))
        
        # Reinigungsaktionen
        if data_status["classes_exist"] and data_status["has_sufficient_data"]:
            actions.append(cl.Action(name="db_clear", payload={"action": "clear"}, label="🗑️ Ausgewählte Daten löschen"))
            actions.append(cl.Action(name="db_clear_all", payload={"action": "clear_all"}, label="💥 Alle Daten löschen"))
        
        # Nachricht mit Status und Aktionen
        status_message = ""
        
        # Status für jede Klasse
        for class_name, count in data_status["details"].items():
            status_message += f"- **{class_name}**: {count} Objekte\n"
        
        msg = cl.Message(content=f"## Datenbank-Status\n\n{status_message}\n\nWählen Sie eine Aktion aus:")
        msg.actions = actions
        await msg.send()
        
    except Exception as e:
        logger.error(f"Fehler beim Datenbank-Management: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler beim Zugriff auf die Datenbank: {str(e)}").send()

@cl.action_callback("db_visualize")
async def on_db_visualize(action):
    """Visualisiert die Daten in der Datenbank."""
    await action.remove()
    
    # Erstelle temporären Weaviate-Client
    temp_client = None
    try:
        # Erstelle Weaviate-Client
        temp_client = create_weaviate_client()
        
        # Sicherstellen, dass der Client verbunden ist
        if not ensure_weaviate_connection(temp_client):
            await cl.Message(content="⚠️ Fehler bei der Verbindung mit der Weaviate-Datenbank.").send()
            return
        
        # Daten abrufen
        collection_names = temp_client.collections.list_all(simple=True)  # Verwende simple=True für eine Liste von Strings
        
        if not collection_names:
            await cl.Message(content="❌ Keine Datenklassen in Weaviate gefunden.").send()
            return
        
        # Daten für den Plot sammeln
        data = {"Klasse": [], "Anzahl": []}
        
        for class_name in collection_names:
            try:
                collection = temp_client.collections.get(class_name)
                count = collection.aggregate.over_all().with_meta_count().do()
                obj_count = count.total_count
                
                data["Klasse"].append(class_name)
                data["Anzahl"].append(obj_count)
            except Exception as e:
                logger.error(f"Fehler beim Abrufen von Daten für Klasse {class_name}: {str(e)}")
        
        # Plot erstellen
        df = pd.DataFrame(data)
        fig = px.bar(df, x="Klasse", y="Anzahl", title="Objekte pro Klasse in Weaviate")
        
        # Plot anzeigen
        await cl.Message(content="### Datenvisualisierung").send()
        await cl.Message(content=fig).send()
        
    except Exception as e:
        logger.error(f"Fehler bei der Datenvisualisierung: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler bei der Datenvisualisierung: {str(e)}").send()

@cl.action_callback("db_clear")
async def on_db_clear(action):
    """Zeigt Optionen zum Löschen von Daten an."""
    await action.remove()
    
    temp_client = None
    try:
        # Erstelle Weaviate-Client
        temp_client = create_weaviate_client()
        
        # Sicherstellen, dass der Client verbunden ist
        if not ensure_weaviate_connection(temp_client):
            await cl.Message(content="⚠️ Fehler bei der Verbindung mit der Weaviate-Datenbank.").send()
            return
        
        # Klassen abrufen
        collection_names = []
        collections = temp_client.collections.list_all(simple=True)
        for collection in collections:
            collection_names.append(collection)  # Jetzt ist collection ein String, kein Objekt mit name-Attribut
        
        if not collection_names:
            await cl.Message(content="❌ Keine Datenklassen in Weaviate gefunden.").send()
            return
        
        # Erstelle Aktionen für jede Klasse
        actions = []
        
        for class_name in collection_names:
            try:
                collection = temp_client.collections.get(class_name)
                count = collection.aggregate.over_all().with_meta_count().do()
                obj_count = count.total_count
                
                actions.append(
                    cl.Action(
                        name="db_clear_class", 
                        payload={"class_name": class_name}, 
                        label=f"🗑️ {class_name} ({obj_count} Objekte)"
                    )
                )
            except Exception as e:
                logger.error(f"Fehler beim Abfragen der Klasse {class_name}: {str(e)}")
        
        # Abbrechen-Aktion
        actions.append(cl.Action(name="db_clear_cancel", payload={"action": "cancel"}, label="❌ Abbrechen"))
        
        # Nachricht mit Auswahl senden
        msg = cl.Message(content="## 🗑️ Daten löschen\n\nWählen Sie die Klasse, deren Daten Sie löschen möchten:")
        msg.actions = actions
        await msg.send()
        
    except Exception as e:
        logger.error(f"Fehler beim Anzeigen der Löschoptionen: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler beim Laden der Löschoptionen: {str(e)}").send()

@cl.action_callback("db_clear_all")
async def on_db_clear_all(action):
    """Löscht alle Daten aus der Datenbank."""
    await action.remove()
    
    temp_client = None
    try:
        # Erstelle Weaviate-Client
        temp_client = create_weaviate_client()
        
        # Klassen abrufen
        schema = temp_client.schema.get()
        collection_names = [collection.name for collection in schema.collections]
        
        if not collection_names:
            await cl.Message(content="Keine Klassen zum Löschen gefunden.").send()
            return
        
        # Lösche alle Objekte aus jeder Klasse
        for class_name in collection_names:
            try:
                collection = temp_client.collections.get(class_name)
                collection.data.delete_all()
                await cl.Message(content=f"✅ Alle Objekte aus **{class_name}** wurden gelöscht.").send()
            except Exception as e:
                logger.error(f"Fehler beim Löschen von Objekten aus {class_name}: {str(e)}")
                await cl.Message(content=f"⚠️ Fehler beim Löschen von {class_name}: {str(e)}").send()
        
        await cl.Message(content="🧹 Bereinigung abgeschlossen. Die Anwendung muss neu gestartet werden, um die Änderungen zu übernehmen.").send()
        restart_msg = cl.Message(content="Die Anwendung benötigt einen Neustart, um die Änderungen zu übernehmen. Klicken Sie auf die Schaltfläche, um die Anwendung neu zu starten.")
        restart_msg.actions = [cl.Action(name="app_restart", payload={"action": "restart"}, label="🔄 Anwendung neu starten")]
        await restart_msg.send()
        
    except Exception as e:
        logger.error(f"Fehler beim Löschen aller Daten: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler beim Löschen der Daten: {str(e)}").send()

@cl.action_callback("db_clear_class")
async def on_db_clear_class(action):
    """Bestätigung für das Löschen einer Klasse."""
    class_name = action.payload["class_name"]
    await action.remove()
    
    # Erstelle Weaviate-Client für die Abfrage der Objektanzahl
    temp_client = None
    try:
        temp_client = create_weaviate_client()
        
        collection = temp_client.collections.get(class_name)
        count = collection.aggregate.over_all().with_meta_count().do()
        obj_count = count.total_count
        
        msg = cl.Message(content=f"⚠️ Sie sind dabei, alle {obj_count} Objekte aus der Klasse **{class_name}** zu löschen. Dieser Vorgang kann nicht rückgängig gemacht werden!\n\nMöchten Sie fortfahren?")
        msg.actions = [
            cl.Action(name="db_clear_class_confirm", payload={"class_name": class_name}, label="⚠️ Ja, Klasse löschen"),
            cl.Action(name="db_clear_cancel", payload={"action": "cancel"}, label="Abbrechen")
        ]
        await msg.send()
    except Exception as e:
        logger.error(f"Fehler beim Vorbereiten des Löschvorgangs für {class_name}: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler: {str(e)}").send()

@cl.action_callback("db_clear_class_confirm")
async def on_db_clear_class_confirm(action):
    """Löscht alle Objekte einer bestimmten Klasse."""
    class_name = action.payload["class_name"]
    await action.remove()
    
    status_msg = cl.Message(content=f"⏳ Lösche alle Objekte aus **{class_name}**...")
    await status_msg.send()
    
    temp_client = None
    try:
        # Erstelle Weaviate-Client
        temp_client = create_weaviate_client()
        
        # Lösche alle Objekte der Klasse
        collection = temp_client.collections.get(class_name)
        collection.data.delete_all()
        
        await cl.Message(content=f"✅ Alle Objekte aus **{class_name}** wurden erfolgreich gelöscht.").send()
        await cl.Message(content="Die Anwendung sollte neu gestartet werden, um die Änderungen zu übernehmen.").send()
        
        restart_msg = cl.Message(content="Anwendung muss neu gestartet werden, um die Änderungen zu übernehmen.")
        restart_msg.actions = [cl.Action(name="app_restart", payload={"action": "restart"}, label="🔄 Anwendung neu starten")]
        await restart_msg.send()
        
    except Exception as e:
        logger.error(f"Fehler beim Löschen von Objekten aus {class_name}: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler beim Löschen der Daten: {str(e)}\n\nEs ist empfehlenswert, die Anwendung neu zu starten oder den Crawler auszuführen, um die Schemas neu zu erstellen.").send()

@cl.action_callback("db_clear_cancel")
async def on_db_clear_cancel(action):
    """Callback für das Abbrechen des Löschvorgangs."""
    await action.remove()
    
    cancel_msg = cl.Message(content="✓ Löschvorgang abgebrochen.")
    await cancel_msg.send()

@cl.action_callback("app_restart")
async def on_app_restart(action):
    """Callback für den Neustart der Anwendung."""
    await action.remove()
    
    restart_msg = cl.Message(content="Starte Anwendung neu...")
    await restart_msg.send()
    
    # Schließe die Weaviate-Verbindung vor dem Neustart
    try:
        client.close()
        logger.info("Weaviate-Verbindung vor dem Neustart geschlossen.")
    except Exception as e:
        logger.error(f"Fehler beim Schließen der Weaviate-Verbindung: {str(e)}")
    
    # Starte die Anwendung neu (im Hintergrund)
    subprocess.Popen(["chainlit", "run", "app.py"])
    
    # Beende die aktuelle Instanz
    import sys
    sys.exit(0)

@cl.action_callback("db_clear_collection")
async def on_db_clear_collection(action):
    """Löscht die angegebene Sammlung."""
    collection_name = action.value
    await action.remove()
    
    temp_client = None
    try:
        # Erstelle Weaviate-Client
        temp_client = create_weaviate_client()
        
        # Lösche die Sammlung
        temp_client.collections.delete(collection_name)
        
        await cl.Message(content=f"✅ Sammlung **{collection_name}** wurde erfolgreich gelöscht.").send()
    except Exception as e:
        logger.error(f"Fehler beim Löschen der Sammlung {collection_name}: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler beim Löschen der Sammlung: {str(e)}").send()

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
        
        # Überprüfe Daten
        data_status = check_weaviate_data(temp_client)
        
        if not data_status["classes_exist"]:
            # Zeige direkt die Crawler-Option an, wenn die Klassen nicht existieren
            crawler_msg = cl.Message(content="⚠️ **Warnung**: Die Datenbank ist leer. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und Daten zu sammeln.")
            crawler_actions = [
                cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
            ]
            crawler_msg.actions = crawler_actions
            await crawler_msg.send()
            return
        
        if not data_status["has_sufficient_data"]:
            # Zeige Warnung und Crawler-Option an, wenn nicht genügend Daten vorhanden sind
            crawler_msg = cl.Message(content="⚠️ **Warnung**: Es sind nicht ausreichend Daten in der Datenbank vorhanden. Die Suche könnte eingeschränkt sein. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und mehr Daten zu sammeln.")
            crawler_actions = [
                cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
            ]
            crawler_msg.actions = crawler_actions
            await crawler_msg.send()
        
        # Initialize vector store retrievers
        chunks_retriever, summaries_retriever, quotes_retriever = create_retrievers()
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
            crawler_msg = cl.Message(content="⚠️ **Warnung**: Nicht genügend Daten in der Datenbank. Klicken Sie auf die Schaltfläche unten, um den Crawler zu starten und Daten zu sammeln.")
            crawler_actions = [
                cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
            ]
            crawler_msg.actions = crawler_actions
            await crawler_msg.send()
        else:
            await cl.Message(content=f"⚠️ **Fehler**: Bei der Initialisierung ist ein Problem aufgetreten: {error_message}. Bitte überprüfen Sie die Verbindung zur Vektordatenbank.").send()
    finally:
        # Stelle sicher, dass der temporäre Client geschlossen wird
        if temp_client:
            try:
                temp_client.close()
                logger.info("Temporärer Weaviate-Client in confirm_crawl geschlossen.")
            except Exception as close_error:
                logger.error(f"Fehler beim Schließen des temporären Weaviate-Clients in confirm_crawl: {str(close_error)}")

# Signal-Handler zum Schließen der Weaviate-Verbindung beim Beenden der Anwendung
import signal
import sys

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

async def reconnect_weaviate_if_needed():
    """Stellt sicher, dass der Weaviate-Client verbunden ist und stellt die Verbindung bei Bedarf wieder her."""
    try:
        global client
        if not client.is_connected():
            logger.info("Weaviate-Client ist nicht verbunden. Stelle Verbindung wieder her...")
            client.connect()
            logger.info("Weaviate-Verbindung wiederhergestellt.")
            
            # Aktualisiere auch die Retriever, da sie möglicherweise auf den alten Client verweisen
            chunks_retriever, summaries_retriever, quotes_retriever = create_retrievers()
            if chunks_retriever and summaries_retriever and quotes_retriever:
                cl.user_session.set("retrievers", {
                    "chunks": chunks_retriever,
                    "summaries": summaries_retriever,
                    "quotes": quotes_retriever
                })
                logger.info("Retriever wurden aktualisiert.")
            else:
                logger.error("Konnte die Retriever nicht aktualisieren, da mindestens einer null ist.")
                return False
        return True
    except Exception as e:
        logger.error(f"Fehler beim Wiederherstellen der Weaviate-Verbindung: {str(e)}")
        # Versuche, einen neuen Client zu erstellen
        client = ensure_global_client()
        if client:
            # Aktualisiere die Retriever mit dem neuen Client
            try:
                chunks_retriever, summaries_retriever, quotes_retriever = create_retrievers()
                if chunks_retriever and summaries_retriever and quotes_retriever:
                    cl.user_session.set("retrievers", {
                        "chunks": chunks_retriever,
                        "summaries": summaries_retriever,
                        "quotes": quotes_retriever
                    })
                    logger.info("Retriever wurden mit neuem Client aktualisiert.")
                    return True
            except Exception as e2:
                logger.error(f"Fehler beim Aktualisieren der Retriever: {str(e2)}")
        return False

if __name__ == "__main__":
    cl.run()