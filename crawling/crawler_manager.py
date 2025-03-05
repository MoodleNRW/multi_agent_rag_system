import logging
import asyncio
import subprocess
from typing import Dict, Any, List, Optional
import os
import time
import uuid
from vector_stores.db_manager import WeaviateManager

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerManager:
    """Manager für Crawler-Operationen."""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(CrawlerManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        self.db_manager = WeaviateManager()
        self.current_process = None
        self.status = {
            "running": False,
            "progress": 0,
            "urls_processed": 0,
            "total_urls": 0,
            "start_time": None,
            "end_time": None,
            "errors": []
        }
        self._initialized = True
    
    def is_running(self) -> bool:
        """Prüft, ob der Crawler gerade läuft."""
        return self.status["running"]
    
    async def run_crawler(self, 
                          url: str, 
                          chunking_strategy: str = "recursive", 
                          depth: int = 3, 
                          max_workers: int = 10) -> Dict[str, Any]:
        """
        Führt den Crawler asynchron aus.
        
        Args:
            url: Die Start-URL für den Crawler
            chunking_strategy: Die Strategie zur Aufteilung der Texte
            depth: Die maximale Tiefe für den Crawler
            max_workers: Die maximale Anzahl paralleler Worker
            
        Returns:
            Dict mit Status und Ergebnis des Crawlers
        """
        if self.is_running():
            return {"status": "error", "message": "Crawler läuft bereits"}
        
        self.status = {
            "running": True,
            "progress": 0,
            "urls_processed": 0,
            "total_urls": 0,
            "start_time": time.time(),
            "end_time": None,
            "errors": []
        }
        
        try:
            # Generiere eine eindeutige ID für diesen Crawler-Lauf
            run_id = str(uuid.uuid4())
            temp_file = f"crawler_output_{run_id}.txt"
            
            # Starten des Crawler-Prozesses
            cmd = [
                "python", "-c",
                f"""
import sys, json, os
sys.path.append('.')
from moodledoc_crawler import scrape_website, save_to_weaviate, create_summaries_for_collected_data

# Aktiviere detaillierten Stdout-Output
print("CRAWLER_START: Starte Crawler mit URL {url}, Strategie {chunking_strategy}")

try:
    # Ausführen des Crawlers
    results = scrape_website(
        '{url}', 
        depth={depth}, 
        max_workers={max_workers}, 
        chunking_strategy='{chunking_strategy}'
    )
    
    # Speichern der Ergebnisse in Weaviate
    print("CRAWLER_SAVE: Speichere Ergebnisse in Weaviate")
    save_to_weaviate(results)
    
    # Erstellen von Zusammenfassungen
    print("CRAWLER_SUMMARIZE: Erstelle Zusammenfassungen")
    create_summaries_for_collected_data(results)
    
    # Ausgabe der Ergebnisse im JSON-Format
    success_msg = {{"status": "success", "url_count": len(results), "strategy": "{chunking_strategy}"}}
    print(f"CRAWLER_RESULT: " + json.dumps(success_msg))
    
except Exception as e:
    # Bei Fehlern, gib eine Fehlermeldung aus
    error_msg = {{"status": "error", "message": str(e)}}
    print(f"CRAWLER_ERROR: " + json.dumps(error_msg))
    sys.exit(1)

sys.exit(0)
                """
            ]
            
            self.logger.info(f"Starte Crawler mit Befehl: {' '.join(cmd)}")
            
            # Starte den Prozess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            self.current_process = process
            
            # Definiere die Stream-Reader-Aufgaben
            async def read_stream(stream, queue):
                while True:
                    line = await asyncio.get_event_loop().run_in_executor(None, stream.readline)
                    if not line:
                        break
                    await queue.put(line)
            
            # Definiere die Status-Update-Aufgabe
            async def update_status():
                while self.is_running():
                    # Aktualisiere den Status (Prozentfortschritt basierend auf verstrichener Zeit)
                    if self.status["start_time"]:
                        elapsed = time.time() - self.status["start_time"]
                        # Schätze den Fortschritt basierend auf der Zeit (maximal 99%)
                        estimated_progress = min(99, elapsed / 300 * 100)  # angenommen, 5 Minuten für 100%
                        self.status["progress"] = estimated_progress
                    await asyncio.sleep(1)
            
            # Erstelle eine Queue für die Stream-Ausgabe
            queue = asyncio.Queue()
            
            # Starte die Stream-Reader-Aufgaben
            read_stdout_task = asyncio.create_task(read_stream(process.stdout, queue))
            read_stderr_task = asyncio.create_task(read_stream(process.stderr, queue))
            update_task = asyncio.create_task(update_status())
            
            # Verarbeite die Queue
            while process.poll() is None or not queue.empty():
                try:
                    line = await asyncio.wait_for(queue.get(), timeout=0.1)
                    
                    # Verarbeite Ausgabe
                    self.logger.info(f"Crawler-Ausgabe: {line.strip()}")
                    
                    if "CRAWLER_START:" in line:
                        self.status["message"] = "Crawler gestartet"
                    
                    if "PROGRESS:" in line:
                        try:
                            progress_info = line.split("PROGRESS:")[1].strip()
                            progress_data = eval(progress_info)
                            self.status.update(progress_data)
                        except:
                            pass
                    
                    if "CRAWLER_SAVE:" in line:
                        self.status["message"] = "Speichere Ergebnisse in Weaviate"
                    
                    if "CRAWLER_SUMMARIZE:" in line:
                        self.status["message"] = "Erstelle Zusammenfassungen"
                    
                    if "CRAWLER_RESULT:" in line:
                        try:
                            result_info = line.split("CRAWLER_RESULT:")[1].strip()
                            result_data = eval(result_info)
                            self.status["result"] = result_data
                            self.status["progress"] = 100
                        except:
                            pass
                    
                    if "CRAWLER_ERROR:" in line:
                        try:
                            error_info = line.split("CRAWLER_ERROR:")[1].strip()
                            error_data = eval(error_info)
                            self.status["errors"].append(error_data.get("message", "Unbekannter Fehler"))
                        except:
                            self.status["errors"].append("Fehler bei der Verarbeitung der Crawler-Ausgabe")
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    self.logger.error(f"Fehler bei der Verarbeitung der Crawler-Ausgabe: {str(e)}")
            
            # Warten auf Prozessende
            exit_code = process.wait()
            
            # Aufgaben abbrechen
            read_stdout_task.cancel()
            read_stderr_task.cancel()
            update_task.cancel()
            
            # Aktualisiere Status
            self.status["running"] = False
            self.status["end_time"] = time.time()
            
            if exit_code != 0:
                self.status["errors"].append(f"Prozess mit Exit-Code {exit_code} beendet")
                return {"status": "error", "message": f"Crawler mit Exit-Code {exit_code} beendet", "details": self.status}
            
            return {"status": "success", "message": "Crawler erfolgreich ausgeführt", "details": self.status}
            
        except Exception as e:
            self.logger.error(f"Fehler beim Ausführen des Crawlers: {str(e)}")
            self.status["running"] = False
            self.status["end_time"] = time.time()
            self.status["errors"].append(str(e))
            return {"status": "error", "message": str(e), "details": self.status}
    
    def cancel_crawler(self):
        """Bricht den laufenden Crawler-Prozess ab."""
        if not self.is_running() or not self.current_process:
            return {"status": "error", "message": "Kein Crawler-Prozess läuft"}
        
        try:
            self.current_process.terminate()
            self.status["running"] = False
            self.status["end_time"] = time.time()
            self.logger.info("Crawler-Prozess abgebrochen")
            return {"status": "success", "message": "Crawler abgebrochen"}
        except Exception as e:
            self.logger.error(f"Fehler beim Abbrechen des Crawlers: {str(e)}")
            return {"status": "error", "message": str(e)} 