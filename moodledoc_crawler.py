import os
import re
import sys
import time
import json
import logging
import traceback
import threading
import html2text
from datetime import datetime
from queue import Queue
from collections import deque
from urllib.parse import urljoin, urlparse
from pathlib import Path
from bs4 import BeautifulSoup
import requests
import weaviate
from tqdm import tqdm
import dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from weaviate.connect import ConnectionParams
# Aktualisiere den Import für ChatOpenAI
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.text_splitter import CharacterTextSplitter
import weaviate.classes as wvc
from vector_stores import weaviate_client

dotenv.load_dotenv()

# Globals for progress tracking
total_pages = 0
completed_pages = 0
lock = threading.Lock()
API_KEY = os.getenv('OPENAI_API_KEY')

# Weaviate-Client initialisieren
weaviate_instance = weaviate_client.create_weaviate_client()

def ensure_weaviate_connection():
    """Stellt sicher, dass der Weaviate-Client verbunden ist."""
    global weaviate_instance
    try:
        if not weaviate_client.ensure_weaviate_connection(weaviate_instance):
            print("[Weaviate] Client ist geschlossen. Erstelle neuen Client...")
            weaviate_instance = weaviate_client.create_weaviate_client()
            if not weaviate_client.ensure_weaviate_connection(weaviate_instance):
                print("[Weaviate] Fehler beim Verbinden. Bitte stellen Sie sicher, dass Weaviate läuft.")
                return False
        return True
    except Exception as e:
        print(f"[Weaviate] Fehler bei der Verbindung: {str(e)}")
        return False

def create_weaviate_schema():
    """Erstellt die erforderlichen Schemas in Weaviate, falls sie noch nicht existieren."""
    global weaviate_instance
    try:
        print("[Weaviate] Prüfe und erstelle Schemas...")
        if not weaviate_client.create_weaviate_schema(weaviate_instance):
            print("[Weaviate] Fehler beim Erstellen der Schemas. Bitte stellen Sie sicher, dass Weaviate läuft.")
            return False
        return True
    except Exception as e:
        print(f"[Weaviate] Fehler beim Erstellen der Schemas: {str(e)}")
        return False

def extract_metadata_from_page(url, soup):
    """
    Extrahiert Metadaten aus einer Webseite
    
    Args:
        url: URL der Webseite
        soup: BeautifulSoup-Objekt der geparsten Seite
        
    Returns:
        Dictionary mit Metadaten
    """
    metadata = {
        "url": url,
        "title": soup.title.string if soup.title else "",
        "last_updated": "",
        "chapter": "",
        "section": "",
        "importance_score": 0.5
    }
    
    # Versuch, das Änderungsdatum zu extrahieren (speziell für Moodle-Docs)
    date_element = soup.select_one('.lastmod')
    if date_element:
        metadata["last_updated"] = date_element.text.strip()
    
    # Extrahiere Kapitel und Abschnitt aus der Breadcrumb-Navigation
    breadcrumbs = soup.select(".breadcrumb li")
    if len(breadcrumbs) >= 2:
        metadata["chapter"] = breadcrumbs[1].text.strip()
    if len(breadcrumbs) >= 3:
        metadata["section"] = breadcrumbs[2].text.strip()
    
    # Extrahiere Kapitel aus dem Seitentitel, falls keine Breadcrumbs vorhanden
    if not metadata["chapter"] and metadata["title"]:
        parts = metadata["title"].split(" - ")
        if len(parts) > 1:
            metadata["chapter"] = parts[0].strip()
    
    # Berechne einen Wichtigkeits-Score basierend auf URL-Tiefe und Überschriften
    url_depth = url.count('/') - 3  # Normalisiert die Tiefe
    h1_count = len(soup.find_all('h1'))
    h2_count = len(soup.find_all('h2'))
    
    # Je tiefer die URL, desto spezifischer der Inhalt, was oft wichtiger ist
    # Je mehr Überschriften, desto strukturierter und wichtiger ist der Inhalt
    importance = 0.5 + (url_depth * 0.05) + (h1_count * 0.1) + (h2_count * 0.02)
    
    # Clip zwischen 0 und 1
    metadata["importance_score"] = max(0.0, min(1.0, importance))
    
    return metadata

def scrape_text(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return "", None
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    
    text = soup.get_text()
    
    # Clean the text
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    return text, soup

def get_subpages(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    subpages = []

    for link in soup.find_all('a'):
        href = link.get('href')
        if href:
            absolute_url = urljoin(url, href)
            if urlparse(absolute_url).netloc == urlparse(url).netloc:
                subpages.append(absolute_url)

    return list(set(subpages))  # Remove duplicates

def update_progress():
    global completed_pages, total_pages
    with lock:
        progress = (completed_pages / total_pages) * 100 if total_pages > 0 else 100
        # Klare separate Zeile für jeden Fortschrittsschritt, damit die Ausgabe besser von Chainlit erkannt wird
        print(f"[Fortschritt] {progress:.2f}% ({completed_pages}/{total_pages} Seiten verarbeitet)")
        
        # Zusätzlich neue Zeile für bessere Protokollierung
        if completed_pages % 5 == 0 or completed_pages == total_pages:
            print(f"[Zwischenstand] {completed_pages} von {total_pages} Seiten verarbeitet ({progress:.2f}%)")
            
            # Bei bestimmten Meilensteinen mehr Informationen ausgeben
            if completed_pages > 0 and (completed_pages % 10 == 0 or completed_pages == total_pages):
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"[{current_time}] [Crawling-Status] Bisher {completed_pages} Seiten verarbeitet.")
                if completed_pages == total_pages:
                    print("[Abschluss] Crawling der Seiten abgeschlossen. Beginne mit der Verarbeitung der gesammelten Daten.")

def scrape_and_collect(url):
    text, soup = scrape_text(url)
    subpages = get_subpages(url)
    metadata = {}
    
    if soup is not None:
        metadata = extract_metadata_from_page(url, soup)
    
    return subpages, text, metadata

def scrape_website(url, visited=None, max_workers=10, depth=10, chunking_strategy="semantic"):
    global total_pages, completed_pages
    if visited is None:
        visited = set()  # Keep track of visited URLs

    pages_to_scrape = [url]
    results = []
    
    while pages_to_scrape:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for page in pages_to_scrape:
                if page not in visited:
                    visited.add(page)
                    futures[executor.submit(scrape_and_collect, page)] = page

            # Update total pages to reflect the new pages that need to be scraped
            total_pages += len(futures)

            pages_to_scrape = []
            for future in as_completed(futures):
                if depth==0:
                    break
                subpages, text, metadata = future.result()
                depth = depth - 1;
                results.append((futures[future], text, metadata))
                completed_pages += 1  # Mark this page as completed
                update_progress()
                for subpage in subpages:
                    if subpage not in visited:
                        pages_to_scrape.append(subpage)
            else:
                continue
            break
    
    # Hier werden die Daten für die Verarbeitung in Chunks aufgeteilt
    all_data = []
    chunk_count = 0
    
    print(f"[Verarbeitung] Verarbeite {len(results)} gesammelte Seiten...")
    
    # Verarbeite jede gesammelte Seite
    for url, text, metadata in results:
        if not text.strip():  # Überspringe leere Texte
            continue
            
        # Teile den Text gemäß der gewählten Strategie
        chunks = split_text_with_strategy(text, strategy=chunking_strategy)
        
        # Bereite die Daten für die Speicherung vor
        for chunk in chunks:
            # Kombiniere Metadaten mit den grundlegenden Eigenschaften
            properties = {
                "url": url,
                "content": chunk,
                "date": datetime.now().isoformat(),
            }
            
            # Füge Metadaten hinzu, wenn vorhanden
            if metadata:
                properties.update({
                    "title": metadata.get("title", ""),
                    "chapter": metadata.get("chapter", ""),
                    "section": metadata.get("section", ""),
                    "last_updated": metadata.get("last_updated", ""),
                    "importance_score": metadata.get("importance_score", 0.5)
                })
                
            all_data.append(properties)
            chunk_count += 1
    
    print(f"[Verarbeitung] {chunk_count} Chunks aus {len(results)} Seiten erstellt.")
    
    return all_data

def generate_output_filename(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace("www.", "")
    path = parsed_url.path.replace("/", "_").strip("_")
    filename = f"{domain}_{path}.md" if path else f"{domain}.md"
    return filename

def split_text_with_strategy(text, strategy="recursive", chunk_size=1000, chunk_overlap=200):
    """Teilt den Text in Chunks basierend auf der angegebenen Strategie.
    
    Strategien:
    - recursive: Rekursives Splitting an Absätzen, Sätzen, etc.
    - semantic: Semantisches Splitting an Überschriften und Abschnitten
    - hierarchical: Hierarchisches Splitting an Kapiteln und Abschnitten
    """
    chunks_with_metadata = []
    
    # Für die vereinfachte Version geben wir nur die Textchunks zurück, nicht die komplexe Struktur
    
    if strategy == "recursive":
        # Rekursives Splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        chunks = text_splitter.split_text(text)
        return chunks
    
    # Für die anderen Strategien verwenden wir einen ähnlichen Ansatz, geben aber nur die Textchunks zurück
    elif strategy in ["semantic", "hierarchical"]:
        # Behalte den bestehenden Code für diese Strategien bei
        
        # ... Vorhandener Code für semantisches/hierarchisches Splitting ...
        
        # Aber am Ende nur die Textchunks zurückgeben
        result_chunks = []
        
        if strategy == "semantic":
            # Semantisches Splitting basierend auf Überschriften
            header_pattern = r'(#{1,6}\s+.+?|<h[1-6]>.+?</h[1-6]>)'
            sections = re.split(header_pattern, text, flags=re.DOTALL)
            
            current_header = "Einführung"
            current_text = ""
            
            for i, section in enumerate(sections):
                if re.match(header_pattern, section):
                    # Dies ist eine Überschrift
                    if current_text.strip():
                        # Wenn bereits Text gesammelt wurde, füge ihn der Liste hinzu
                        result_chunks.append(current_text.strip())
                    
                    # Setze den aktuellen Header und beginne mit neuem Text
                    current_header = re.sub(r'[#<h1-6>/]', '', section).strip()
                    current_text = current_header + ":\n"
                else:
                    # Dies ist Inhalt
                    if section.strip():
                        current_text += section
            
            # Füge den letzten Abschnitt hinzu
            if current_text.strip():
                result_chunks.append(current_text.strip())
        
        elif strategy == "hierarchical":
            # Hierarchisches Splitting basierend auf Kapiteln und Abschnitten
            chapter_pattern = r'(#{1,2}\s+.+?|<h[1-2]>.+?</h[1-2]>)'
            chapters = re.split(chapter_pattern, text, flags=re.DOTALL)
            
            for i, chapter in enumerate(chapters):
                if re.match(chapter_pattern, chapter):
                    # Dies ist eine Kapitelüberschrift
                    result_chunks.append(chapter.strip())
                else:
                    # Dies ist Kapitelinhalt - teile ihn in kleinere Chunks
                    if chapter.strip():
                        # Teile nach Absätzen
                        paragraphs = re.split(r'\n{2,}', chapter)
                        for paragraph in paragraphs:
                            if paragraph.strip() and len(paragraph) > 50:
                                result_chunks.append(paragraph.strip())
        
        # Wenn keine Chunks gefunden wurden, verwende rekursives Splitting
        if not result_chunks:
            return split_text_with_strategy(text, "recursive", chunk_size, chunk_overlap)
        
        return result_chunks
    
    else:
        # Unbekannte Strategie - Fallback zur rekursiven Strategie
        print(f"Unbekannte Strategie: {strategy}. Verwende rekursives Splitting als Fallback.")
        return split_text_with_strategy(text, "recursive", chunk_size, chunk_overlap)

def save_to_weaviate(collected_data):
    """
    Speichert die gesammelten Daten in Weaviate.
    
    Args:
        collected_data: Die gesammelten Daten, die gespeichert werden sollen.
                       Kann eine Liste oder ein Dictionary sein.
    
    Returns:
        None
    """
    global weaviate_instance
    
    # Stelle sicher, dass eine Verbindung zu Weaviate besteht
    if not ensure_weaviate_connection():
        print("[FEHLER] Keine Verbindung zu Weaviate möglich. Daten können nicht gespeichert werden.")
        return
    
    # Erstelle Schemas, falls sie nicht existieren
    if not create_weaviate_schema():
        print("[FEHLER] Fehler beim Erstellen der Schemas. Daten können nicht gespeichert werden.")
        return
    
    # Wenn collected_data eine Liste ist, konvertiere sie in ein Dictionary mit URL als Schlüssel
    if isinstance(collected_data, list):
        # Sammle alle Daten pro URL
        data_dict = {}
        for item in collected_data:
            if 'url' in item:
                url = item['url']
                if url not in data_dict:
                    data_dict[url] = {
                        'url': url,
                        'content': item.get('content', ''),
                        'chunks': [],
                        'title': item.get('title', ''),
                        'chapter': item.get('chapter', ''),
                        'section': item.get('section', ''),
                        'last_updated': item.get('last_updated', ''),
                        'importance_score': item.get('importance_score', 0.5)
                    }
                # Füge jedes Item als Chunk hinzu
                data_dict[url]['chunks'].append({
                    'content': item.get('content', ''),
                    'type': 'text'
                })
        collected_data = data_dict
    
    # Initialisiere Zähler für erfolgreiche und fehlgeschlagene Speicheroperationen
    successful_chunks = 0
    failed_chunks = 0
    all_failed_objects = []
    
    # Berechne die Gesamtzahl der Chunks für den Fortschrittsbalken
    total_chunks = 0
    for url, data in collected_data.items():
        if 'chunks' in data:
            total_chunks += len(data['chunks'])
    
    print(f"[Weaviate] Beginne mit dem Speichern von {total_chunks} Chunks in Weaviate...")
    
    # Aktuelles Datum abrufen
    current_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Content Collection holen
    content_collection = None
    try:
        content_collection = weaviate_instance.collections.get("Content")
    except Exception as e:
        print(f"[FEHLER] Konnte Collection 'Content' nicht abrufen: {str(e)}")
    
    # Content_chunk Collection holen
    chunk_collection = None
    try:
        chunk_collection = weaviate_instance.collections.get("Content_chunk")
    except Exception as e:
        print(f"[FEHLER] Konnte Collection 'Content_chunk' nicht abrufen: {str(e)}")
        return
    
    for url, data in collected_data.items():
        try:
            # Speichere das vollständige Dokument in Content
            if content_collection and 'content' in data:
                content_properties = {
                    "url": url,
                    "content": data['content'],
                    "date": current_date,
                    "title": data.get('title', ''),
                    "chapter": data.get('chapter', ''),
                    "section": data.get('section', ''),
                    "last_updated": data.get('last_updated', ''),
                    "importance_score": data.get('importance_score', 0.5)
                }
                
                try:
                    content_collection.data.insert(content_properties)
                    print(f"Vollständiges Dokument für URL '{url}' erfolgreich gespeichert.")
                except Exception as e:
                    print(f"[FEHLER] Speichern des vollständigen Dokuments für URL '{url}' fehlgeschlagen: {str(e)}")
        except Exception as e:
            print(f"[FEHLER] Problem beim Verarbeiten der URL '{url}': {str(e)}")
            continue
        
        # Prüfe, ob 'chunks' in den Daten vorhanden ist
        if 'chunks' not in data:
            print(f"[WARNUNG] Keine Chunks für URL '{url}' gefunden. Überspringe...")
            continue
        
        for i, chunk in enumerate(data['chunks']):
            try:
                # Erstelle die Eigenschaften für den Chunk
                chunk_properties = {
                    "url": url,
                    "content_chunk": chunk['content'],
                    "chunk_nr": i,
                    "date": current_date,
                    "title": data.get('title', ''),
                    "chapter": data.get('chapter', ''),
                    "section": data.get('section', ''),
                    "last_updated": data.get('last_updated', ''),
                    "importance_score": data.get('importance_score', 0.5),
                    "chunk_type": chunk.get('type', 'text')
                }
                
                # Direktes Speichern ohne Batch
                chunk_collection.data.insert(chunk_properties)
                successful_chunks += 1
                print(f"Chunk {i} für URL '{url}' erfolgreich gespeichert.")
            except Exception as e:
                failed_chunks += 1
                error_info = {
                    "url": url,
                    "chunk_nr": i,
                    "error": str(e)
                }
                all_failed_objects.append(error_info)
                print(f"[FEHLER] Direktes Speichern von Chunk {i} für URL '{url}' fehlgeschlagen: {str(e)}")
            
            # Zeige den Fortschritt an
            progress = (successful_chunks + failed_chunks) / total_chunks * 100 if total_chunks > 0 else 100
            print(f"[Weaviate-Speicher] {progress:.2f}% ({successful_chunks + failed_chunks}/{total_chunks} Chunks gespeichert)")
    
    # Zeige eine Zusammenfassung der Ergebnisse an
    print(f"[Weaviate] {successful_chunks} von {total_chunks} Chunks wurden erfolgreich in Weaviate gespeichert.")
    if failed_chunks > 0:
        print(f"[Weaviate] {failed_chunks} Chunks konnten nicht gespeichert werden.")
        for failure in all_failed_objects[:5]:  # Zeige die ersten 5 Fehler an
            print(f"  - URL: {failure['url']}, Chunk: {failure['chunk_nr']}, Fehler: {failure['error']}")
        if len(all_failed_objects) > 5:
            print(f"  - ... und {len(all_failed_objects) - 5} weitere Fehler.")

def create_summaries_for_collected_data(collected_data):
    """
    Erstellt Zusammenfassungen für die gesammelten Daten und speichert sie in Weaviate.
    
    Args:
        collected_data: Die gesammelten Daten, für die Zusammenfassungen erstellt werden sollen.
    
    Returns:
        None
    """
    global weaviate_instance
    
    print("[Weaviate] Erstelle Zusammenfassungen...")
    
    # Stelle sicher, dass eine Verbindung zu Weaviate besteht
    ensure_weaviate_connection()
    
    try:
        # Initialisiere den OpenAI-Client
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("[FEHLER] OPENAI_API_KEY nicht gefunden. Überspringe Zusammenfassungen.")
            return
        
        # Initialisiere den LLM
        llm = ChatOpenAI(api_key=openai_api_key, model_name="gpt-3.5-turbo")
        
        # Initialisiere Zähler für erfolgreiche und fehlgeschlagene Speicheroperationen
        successful_summaries = 0
        failed_summaries = 0
        all_failed_summaries = []
        
        # Hole die Collection für Zusammenfassungen
        summary_collection = None
        try:
            summary_collection = weaviate_instance.collections.get("Content_summary")
        except Exception as e:
            print(f"[FEHLER] Konnte Collection 'Content_summary' nicht abrufen: {str(e)}")
            return
        
        # Wenn collected_data eine Liste ist, konvertiere sie in ein Dictionary mit URL als Schlüssel
        if isinstance(collected_data, list):
            data_dict = {}
            for item in collected_data:
                if 'url' in item:
                    data_dict[item['url']] = item
            collected_data = data_dict
        
        # Erstelle Zusammenfassungen für jede URL
        total_urls = len(collected_data)
        processed_urls = 0
        
        for url, data in collected_data.items():
            try:
                # Extrahiere den Inhalt
                content = data.get('content', '')
                if not content:
                    print(f"[WARNUNG] Kein Inhalt für URL '{url}' gefunden. Überspringe...")
                    continue
                
                # Erstelle eine Zusammenfassung mit dem LLM
                prompt = f"""
                Bitte erstelle eine kurze Zusammenfassung des folgenden Textes. 
                Die Zusammenfassung sollte die wichtigsten Punkte enthalten und nicht länger als 3-4 Sätze sein.
                
                Text: {content}
                
                Zusammenfassung:
                """
                
                messages = [{"role": "user", "content": prompt}]
                response = llm.invoke(messages)
                summary = response.content.strip()
                
                # Formatiere das Datum im RFC3339-Format
                current_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                
                # Speichere die Zusammenfassung in Weaviate
                properties = {
                    "url": url,
                    "content_summary": summary,
                    "date": current_date,
                    "title": data.get('title', ''),
                    "chapter": data.get('chapter', ''),
                    "section": data.get('section', ''),
                    "last_updated": data.get('last_updated', ''),
                    "importance_score": data.get('importance_score', 0.5)
                }
                
                # Direktes Speichern ohne Batch
                summary_collection.data.insert(properties)
                successful_summaries += 1
                print(f"Zusammenfassung für URL '{url}' erfolgreich gespeichert.")
            except Exception as e:
                failed_summaries += 1
                error_info = {
                    "url": url,
                    "error": str(e)
                }
                all_failed_summaries.append(error_info)
                print(f"[FEHLER] Direktes Speichern der Zusammenfassung für URL '{url}' fehlgeschlagen: {str(e)}")
            
            # Aktualisiere den Fortschritt
            processed_urls += 1
            progress = processed_urls / total_urls * 100
            print(f"[Zusammenfassungen] {progress:.2f}% ({processed_urls}/{total_urls})")
        
        # Zeige eine Zusammenfassung der Ergebnisse an
        print(f"[Weaviate] {successful_summaries} von {total_urls} Zusammenfassungen wurden erfolgreich in Weaviate gespeichert.")
        
        # Wenn es Fehler gab, zeige Details an
        if failed_summaries > 0:
            print(f"[WARNUNG] {failed_summaries} Zusammenfassungen konnten nicht gespeichert werden.")
            for i, error_info in enumerate(all_failed_summaries, 1):
                print(f"  Fehler {i}: URL: {error_info['url']}, Fehler: {error_info['error']}")
    except Exception as e:
        print(f"[FEHLER] Fehler beim Erstellen von Zusammenfassungen: {str(e)}")
    finally:
        # Stelle sicher, dass die Weaviate-Verbindung nicht geschlossen wird, da sie in der main-Funktion geschlossen wird
        # Wir loggen nur, dass wir hier fertig sind
        print("[Weaviate] Zusammenfassungen erstellt, Verbindung bleibt offen für weitere Operationen.")

def get_llm():
    """
    Initialisiert und gibt das LLM für Zusammenfassungen zurück.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY Umgebungsvariable ist nicht gesetzt")
    
    # Initialisiere das Chat-Modell
    llm = ChatOpenAI(api_key=openai_api_key, model_name="gpt-3.5-turbo")
    return llm

def create_summary_for_content(content):
    """
    Erstellt eine Zusammenfassung für den gegebenen Inhalt mit dem Sprachmodell.
    
    Args:
        content (str): Der Inhalt, der zusammengefasst werden soll.
        
    Returns:
        str: Die erstellte Zusammenfassung.
    """
    if not content or not content.strip():
        return "Kein Inhalt zum Zusammenfassen verfügbar."
    
    # Initialisiere das LLM
    llm = get_llm()
    
    # Erstelle die Zusammenfassung
    prompt_template = "Fasse den folgenden Inhalt zusammen: {context}"
    prompt = ChatPromptTemplate.from_template(prompt_template)
    
    # Erstelle die Chain für die Dokumentenverarbeitung
    stuff_chain = create_stuff_documents_chain(llm, prompt)
    
    # Erstelle ein Document-Objekt
    docs = [Document(page_content=content)]
    
    # Rufe die Chain auf
    try:
        summary = stuff_chain.invoke({"context": docs})
        return summary
    except Exception as e:
        error_message = str(e)
        print(f"[FEHLER] Fehler bei der Erstellung der Zusammenfassung: {error_message}")
        return f"Zusammenfassung konnte nicht erstellt werden. Fehler: {error_message}"

def main():
    """
    Hauptfunktion, die den Crawler-Prozess startet.
    
    Die Funktion verarbeitet Befehlszeilenargumente:
    - sys.argv[1]: Website-URL zum Crawlen
    - sys.argv[2] (optional): Maximale Anzahl von Seiten (Tiefe)
    - sys.argv[3] (optional): Chunking-Strategie ("recursive", "semantic", "hierarchical")
    
    Wenn keine Befehlszeilenargumente übergeben werden, fragt sie den Benutzer nach Eingaben.
    """
    global weaviate_instance
    
    if len(sys.argv) > 1:
        website_url = sys.argv[1]
        
        # Wenn ein zweites Argument vorhanden ist, verwende es als Tiefenwert
        depth = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        
        # Wenn ein drittes Argument vorhanden ist, verwende es als Chunking-Strategie
        chunking_strategy = sys.argv[3] if len(sys.argv) > 3 else "semantic"
        
        # Überprüfe, ob die angegebene Strategie gültig ist
        if chunking_strategy not in ["recursive", "semantic", "hierarchical"]:
            print(f"Ungültige Chunking-Strategie: {chunking_strategy}. Verwende 'semantic' als Standard.")
            chunking_strategy = "semantic"
    else:
        website_url = input("Geben Sie eine Webseite ein, um das Scraping zu beginnen: ")
        depth = int(input("Geben Sie eine maximale Anzahl an Seiten an die ausgelesen werden soll: "))
        
        # Frage nach der Chunking-Strategie
        strategy_input = input("Wählen Sie eine Chunking-Strategie (recursive/semantic/hierarchical) [semantic]: ").lower()
        chunking_strategy = strategy_input if strategy_input in ["recursive", "semantic", "hierarchical"] else "semantic"

    print(f"[Start] Starte Crawling von {website_url} mit Strategie: {chunking_strategy}")
    print(f"[Konfiguration] Max. Seiten: {depth}, Chunking-Strategie: {chunking_strategy}")
    
    try:
        # Prüfe Weaviate-Verbindung und erstelle Schemas
        if not ensure_weaviate_connection():
            print("[FEHLER] Keine Verbindung zu Weaviate möglich. Bitte stellen Sie sicher, dass Weaviate läuft.")
            print("[STATUS] CRAWLING_ERROR")
            sys.exit(1)
            
        if not create_weaviate_schema():
            print("[FEHLER] Fehler beim Erstellen der Schemas. Bitte stellen Sie sicher, dass Weaviate läuft.")
            print("[STATUS] CRAWLING_ERROR")
            sys.exit(1)
        
        visited = set()
        data = scrape_website(website_url, visited=visited, max_workers=10, depth=depth, chunking_strategy=chunking_strategy)
        
        # Dateinamen generieren
        output_filename = generate_output_filename(website_url)
        
        # Speichern der gesammelten Daten in die Weaviate-Datenbank
        print(f"[Daten] Es wurden insgesamt {len(data)} Dokumente gesammelt und verarbeitet.")
        
        # Speichern der chunks in Weaviate
        print(f"[Weaviate] Speichere Daten in die Weaviate-Datenbank...")
        save_to_weaviate(data)
        
        # Erstelle Zusammenfassungen für die gesammelten Daten
        create_summaries_for_collected_data(data)
        
        print(f"[Abschluss] Crawling und Datenverarbeitung vollständig abgeschlossen.")
        print(f"[Zusammenfassung] {len(data)} Dokumente wurden erfolgreich in die Weaviate-Datenbank gespeichert.")
        print(f"[STATUS] CRAWLING_COMPLETE")
        
        # Schließe die Weaviate-Verbindung
        try:
            weaviate_instance.close()
            print("[Weaviate] Verbindung geschlossen.")
        except Exception as close_error:
            print(f"[Weaviate] Fehler beim Schließen der Verbindung: {close_error}")
            
    except Exception as e:
        print(f"[FEHLER] Ein Fehler ist aufgetreten: {str(e)}")
        traceback.print_exc()
        print(f"[STATUS] CRAWLING_ERROR")
        
        # Versuche, die Weaviate-Verbindung zu schließen
        try:
            weaviate_instance.close()
        except:
            pass
        
        sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())