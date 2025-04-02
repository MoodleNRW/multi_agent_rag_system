import os
import json
import uuid
import time
from datetime import datetime
import weaviate
from weaviate.connect import ConnectionParams
import dotenv
import logging
from typing import Dict, Any, List, Optional, Tuple
from tqdm import tqdm
import concurrent.futures
import multiprocessing

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Lade Umgebungsvariablen
dotenv.load_dotenv(override=True)
API_KEY = os.getenv('OPENAI_API_KEY')

# Weaviate-Konfiguration
WEAVIATE_URL = "http://localhost:8090"
WEAVIATE_GRPC_PORT = 50051

# Parallelisierungseinstellungen
DEFAULT_MAX_WORKERS = max(4, multiprocessing.cpu_count() * 2)  # Default: Anzahl CPUs * 2, mindestens 4
CHUNK_BATCH_SIZE = 100  # Anzahl der Chunks pro Batch

# Globaler Lock für Thread-Sicherheit
import threading
stats_lock = threading.Lock()


def create_weaviate_client() -> weaviate.WeaviateClient:
    """
    Erstellt einen neuen Weaviate-Client mit den konfigurierten Verbindungsparametern.
    
    Returns:
        weaviate.WeaviateClient: Der initialisierte Weaviate-Client
    """
    try:
        connection_params = ConnectionParams.from_url(
            url=WEAVIATE_URL,
            grpc_port=WEAVIATE_GRPC_PORT
        )
        
        # Stelle sicher, dass der API-Key korrekt formatiert ist
        headers = {
            "X-OpenAI-Api-Key": API_KEY,
        }
        
        logger.info("Weaviate-Client wird erstellt mit API-Key-Länge: %d", len(API_KEY) if API_KEY else 0)
        
        client = weaviate.WeaviateClient(
            connection_params=connection_params,
            additional_headers=headers
        )
        
        # Verbinde den Client
        client.connect()
        
        if not client.is_ready():
            logger.error("Weaviate-Client konnte nicht verbunden werden.")
            raise ConnectionError("Weaviate-Client ist nicht bereit")
        
        logger.info("Weaviate-Client erfolgreich verbunden.")
        
        return client
    except Exception as e:
        logger.error(f"Fehler beim Erstellen des Weaviate-Clients: {str(e)}")
        raise


def ensure_weaviate_connection(client: weaviate.WeaviateClient) -> bool:
    """
    Stellt sicher, dass der Weaviate-Client verbunden ist.
    
    Args:
        client: Der Weaviate-Client
        
    Returns:
        bool: True, wenn der Client verbunden ist, sonst False
    """
    try:
        # Prüfe, ob der Client verbunden ist
        is_ready = client.is_ready()
        if is_ready:
            return True
        else:
            logger.error("Weaviate-Client ist nicht bereit.")
            return False
    except Exception as e:
        logger.error(f"Fehler beim Prüfen der Weaviate-Verbindung: {str(e)}")
        return False


def create_weaviate_schema(client: weaviate.WeaviateClient) -> bool:
    """
    Erstellt die erforderlichen Schemas in Weaviate, falls sie noch nicht existieren.
    
    Args:
        client: Der Weaviate-Client
        
    Returns:
        bool: True, wenn die Schemas erstellt wurden, sonst False
    """
    from vector_stores.weaviate_client import create_weaviate_schema
    return create_weaviate_schema(client)


def load_json_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Lädt JSON-Daten aus einer Datei.
    
    Args:
        file_path: Pfad zur JSON-Datei
        
    Returns:
        List[Dict[str, Any]]: Die geladenen Daten
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Daten aus {file_path} erfolgreich geladen: {len(data)} Dokumente")
        return data
    except Exception as e:
        logger.error(f"Fehler beim Laden der JSON-Daten aus {file_path}: {str(e)}")
        raise


def import_document(doc: Dict[str, Any], client: weaviate.WeaviateClient, 
                   content_collection, chunk_collection, summary_collection,
                   current_date: str, stats: Dict[str, int]) -> None:
    """
    Importiert ein einzelnes Dokument und seine Abschnitte in Weaviate.
    
    Args:
        doc: Das zu importierende Dokument
        client: Der Weaviate-Client
        content_collection: Die Content-Collection
        chunk_collection: Die Content_chunk-Collection
        summary_collection: Die Content_summary-Collection
        current_date: Das aktuelle Datum im RFC3339-Format
        stats: Dictionary für Statistiken
    """
    try:
        doc_id = doc.get("id")
        doc_title = doc.get("title", "Unbekannter Titel")
        
        # Hauptdokument erstellen
        doc_content = ""
        for section in doc.get("sections", []):
            doc_content += section.get("text", "") + "\n\n"
        
        # URL aus dem ersten Abschnitt verwenden oder Fallback-URL
        doc_url = ""
        if doc.get("sections") and len(doc.get("sections")) > 0:
            doc_url = doc.get("sections")[0].get("source", f"https://docs.moodle.org/doc/{doc_id}")
        else:
            doc_url = f"https://docs.moodle.org/doc/{doc_id}"
        
        doc_object = {
            "url": doc_url,
            "content": doc_content,
            "date": current_date,
            "title": doc_title,
            "chapter": "",
            "section": "",
            "last_updated": "",
            "importance_score": 0.7
        }
        
        try:
            content_collection.data.insert(doc_object)
            with stats_lock:
                stats["success_content"] += 1
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Dokuments {doc_id}: {str(e)}")
            with stats_lock:
                stats["failed_content"] += 1
        
        # Verarbeite die Abschnitte parallel in Batches
        process_sections_parallel(doc, doc_id, doc_url, chunk_collection, current_date, stats)
        
        # Generiere auch eine Zusammenfassung für das Dokument
        summary = f"Zusammenfassung des Dokuments '{doc_title}'. Dieses Dokument enthält {len(doc.get('sections', []))} Abschnitte."
        summary_object = {
            "url": doc_url,
            "content_summary": summary,
            "date": current_date
        }
        
        try:
            summary_collection.data.insert(summary_object)
            with stats_lock:
                stats["success_summaries"] += 1
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Zusammenfassung für Dokument {doc_id}: {str(e)}")
            with stats_lock:
                stats["failed_summaries"] += 1
        
        with stats_lock:
            stats["documents_processed"] += 1
            stats["sections_processed"] += len(doc.get("sections", []))
    except Exception as e:
        logger.error(f"Fehler bei der Verarbeitung des Dokuments: {str(e)}")


def process_section(section: Dict[str, Any], section_idx: int, doc_id: str, 
                   doc_url: str, chunk_collection, current_date: str) -> Tuple[bool, str]:
    """
    Verarbeitet einen einzelnen Abschnitt und importiert ihn in die Weaviate Datenbank.
    
    Args:
        section: Der zu verarbeitende Abschnitt
        section_idx: Der Index des Abschnitts
        doc_id: Die ID des übergeordneten Dokuments
        doc_url: Die URL des übergeordneten Dokuments
        chunk_collection: Die Content_chunk-Collection
        current_date: Das aktuelle Datum im RFC3339-Format
        
    Returns:
        Tuple[bool, str]: (Erfolg, Fehlermeldung falls relevant)
    """
    try:
        section_id = section.get("id", str(uuid.uuid4()))
        section_text = section.get("text", "")
        section_url = section.get("source", doc_url)
        
        # Überspringen leerer Abschnitte
        if not section_text.strip():
            return (True, "")
        
        # Chunk-Objekt erstellen
        chunk_object = {
            "url": section_url,
            "content_chunk": section_text,
            "chunk_nr": section_idx,
            "chunk_type": "section",
            "date": current_date
        }
        
        # In Weaviate speichern
        chunk_collection.data.insert(chunk_object)
        return (True, "")
    except Exception as e:
        error_msg = f"Fehler beim Speichern des Abschnitts {section_id if 'section_id' in locals() else 'unbekannt'}: {str(e)}"
        return (False, error_msg)


def process_sections_parallel(doc: Dict[str, Any], doc_id: str, doc_url: str, 
                              chunk_collection, current_date: str, stats: Dict[str, int]) -> None:
    """
    Verarbeitet Abschnitte eines Dokuments parallel in Batches.
    
    Args:
        doc: Das übergeordnete Dokument
        doc_id: Die ID des Dokuments
        doc_url: Die URL des Dokuments
        chunk_collection: Die Content_chunk-Collection
        current_date: Das aktuelle Datum im RFC3339-Format
        stats: Dictionary für Statistiken
    """
    sections = doc.get("sections", [])
    
    # Verwende einen Thread-Pool für die parallele Verarbeitung
    with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS) as executor:
        # Reiche alle Abschnitte in den Thread-Pool ein
        future_to_section = {
            executor.submit(
                process_section, section, section_idx, doc_id, doc_url, chunk_collection, current_date
            ): section_idx
            for section_idx, section in enumerate(sections)
            if section.get("text", "").strip()  # Überspringe leere Abschnitte
        }
        
        # Verarbeite die Ergebnisse, wenn sie eintreffen
        for future in concurrent.futures.as_completed(future_to_section):
            section_idx = future_to_section[future]
            try:
                success, error_msg = future.result()
                with stats_lock:
                    if success:
                        stats["success_chunks"] += 1
                    else:
                        stats["failed_chunks"] += 1
                        logger.error(error_msg)
            except Exception as e:
                with stats_lock:
                    stats["failed_chunks"] += 1
                logger.error(f"Ausnahme bei der Verarbeitung von Abschnitt {section_idx}: {str(e)}")


def import_moodle_data(data: List[Dict[str, Any]], client: weaviate.WeaviateClient, max_workers: int = DEFAULT_MAX_WORKERS) -> bool:
    """
    Importiert Moodle-Dokumentationsdaten parallel in die Weaviate-Datenbank.
    
    Args:
        data: Die zu importierenden Daten
        client: Der Weaviate-Client
        max_workers: Maximale Anzahl von Worker-Threads
        
    Returns:
        bool: True, wenn der Import erfolgreich war, sonst False
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starte parallelen Import von {len(data)} Moodle-Dokumenten mit {max_workers} Workern...")
        
        # Stelle sicher, dass die Schemas existieren
        if not create_weaviate_schema(client):
            logger.error("Fehler beim Erstellen der Schemas. Import wird abgebrochen.")
            return False
        
        # Collections für den Import holen
        content_collection = client.collections.get("Content")
        chunk_collection = client.collections.get("Content_chunk")
        summary_collection = client.collections.get("Content_summary")
        
        # Aktuelles Datum für den Import
        current_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Statistiken für den Import
        stats = {
            "documents_processed": 0,
            "sections_processed": 0,
            "success_content": 0,
            "failed_content": 0,
            "success_chunks": 0,
            "failed_chunks": 0,
            "success_summaries": 0,
            "failed_summaries": 0
        }
        
        # Erstelle einen Progress-Bar
        pbar = tqdm(total=len(data), desc="Importiere Dokumente", unit="dok")
        
        # Verwende einen Thread-Pool für die parallele Verarbeitung der Dokumente
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Reiche alle Dokumente an den Thread-Pool ein
            futures = []
            for doc in data:
                future = executor.submit(
                    import_document, doc, client, content_collection, 
                    chunk_collection, summary_collection, current_date, stats
                )
                futures.append(future)
                
            # Verarbeite die Ergebnisse und aktualisiere die Fortschrittsanzeige
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()  # Fange Fehler von import_document
                    pbar.update(1)
                except Exception as e:
                    logger.error(f"Unbehandelte Ausnahme bei der Dokumentverarbeitung: {str(e)}")
                    pbar.update(1)
        
        pbar.close()
        
        # Berechnete Gesamtzeit
        elapsed_time = time.time() - start_time
        docs_per_sec = stats["documents_processed"] / elapsed_time if elapsed_time > 0 else 0
        chunks_per_sec = stats["success_chunks"] / elapsed_time if elapsed_time > 0 else 0
        
        # Gib Statistiken aus
        logger.info(f"Import abgeschlossen in {elapsed_time:.2f} Sekunden:")
        logger.info(f"  Verarbeitete Dokumente: {stats['documents_processed']} ({docs_per_sec:.2f} Dokumente/s)")
        logger.info(f"  Verarbeitete Abschnitte: {stats['sections_processed']}")
        logger.info(f"  Erfolgreiche Content-Einträge: {stats['success_content']}")
        logger.info(f"  Fehlgeschlagene Content-Einträge: {stats['failed_content']}")
        logger.info(f"  Erfolgreiche Chunks: {stats['success_chunks']} ({chunks_per_sec:.2f} Chunks/s)")
        logger.info(f"  Fehlgeschlagene Chunks: {stats['failed_chunks']}")
        logger.info(f"  Erfolgreiche Zusammenfassungen: {stats['success_summaries']}")
        logger.info(f"  Fehlgeschlagene Zusammenfassungen: {stats['failed_summaries']}")
        
        return stats["failed_content"] == 0 and stats["failed_chunks"] == 0
    except Exception as e:
        logger.error(f"Fehler beim Import der Moodle-Daten: {str(e)}")
        return False


def main(json_file_path: str, max_workers: int = None):
    """
    Hauptfunktion zum Importieren von Moodle-Daten in Weaviate.
    
    Args:
        json_file_path: Pfad zur JSON-Datei mit den Moodle-Daten
        max_workers: Maximale Anzahl von Worker-Threads (Optional)
    """
    start_time = time.time()
    
    # Verwende Standardwert, wenn nicht angegeben
    if max_workers is None:
        max_workers = DEFAULT_MAX_WORKERS
    
    try:
        # Weaviate-Client erstellen
        client = create_weaviate_client()
        
        # Verbindung sicherstellen
        if not ensure_weaviate_connection(client):
            logger.error("Keine Verbindung zu Weaviate möglich. Import wird abgebrochen.")
            return
        
        # JSON-Daten laden
        logger.info(f"Lade Daten aus {json_file_path}...")
        data = load_json_data(json_file_path)
        
        # Daten importieren
        logger.info(f"Starte Import von {len(data)} Dokumenten mit {max_workers} parallelen Threads...")
        success = import_moodle_data(data, client, max_workers)
        
        # Gesamtlaufzeit berechnen
        total_elapsed = time.time() - start_time
        
        if success:
            logger.info(f"Moodle-Daten wurden erfolgreich in Weaviate importiert (Gesamtzeit: {total_elapsed:.2f} Sekunden).")
        else:
            logger.warning(f"Moodle-Daten wurden mit einigen Fehlern importiert (Gesamtzeit: {total_elapsed:.2f} Sekunden).")
    except Exception as e:
        logger.error(f"Unerwarteter Fehler bei der Ausführung: {str(e)}")
    finally:
        # Client schließen
        if 'client' in locals():
            try:
                client.close()
                logger.info("Weaviate-Client geschlossen.")
            except Exception as e:
                logger.error(f"Fehler beim Schließen des Weaviate-Clients: {str(e)}")


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Importiere Moodle-Dokumentationsdaten in Weaviate")
    parser.add_argument("json_file", help="Pfad zur JSON-Datei mit den Moodle-Daten")
    parser.add_argument("--workers", type=int, help=f"Anzahl der parallelen Worker-Threads (Standard: {DEFAULT_MAX_WORKERS})")
    
    args = parser.parse_args()
    
    main(args.json_file, args.workers) 