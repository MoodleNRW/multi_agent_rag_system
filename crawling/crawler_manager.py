import chainlit as cl
import subprocess
import os
import asyncio
import time
import re
import logging
from vector_stores.retriever import create_retrievers

# Konfiguriere Logger
logger = logging.getLogger(__name__)

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
        depth = 50  # Begrenzung der Anzahl der Seiten
        
        # Status-Nachricht
        update_msg = cl.Message(content=f"Der Crawler läuft mit der {selected_strategy} Chunking-Strategie und sammelt Daten von https://moodlenrw.de/... Dies kann einige Minuten dauern.")
        await update_msg.send()
        
        # Führe den Crawler in einem separaten Prozess aus mit der ausgewählten Strategie
        process = subprocess.Popen(
            ["python", "moodledoc_crawler.py", url, str(depth), chunking_strategy],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # Ein Level höher, da wir jetzt in einem Unterverzeichnis sind
            bufsize=1  # Zeilenorientiert gepuffert
        )
        
        await run_crawler_process(process)
    
    except Exception as e:
        logger.error(f"Fehler beim Ausführen des Crawlers: {str(e)}")
        await cl.Message(content=f"⚠️ Bei der Ausführung des Crawlers ist ein Fehler aufgetreten: {str(e)}").send()

async def run_crawler_process(process):
    """Führt den Crawler-Prozess aus und überwacht ihn."""
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
                chunks_retriever, summaries_retriever, quotes_retriever, faq_retriever = create_retrievers()
                cl.user_session.set("retrievers", {
                    "chunks": chunks_retriever,
                    "summaries": summaries_retriever,
                    "quotes": quotes_retriever,
                    "faq": faq_retriever
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