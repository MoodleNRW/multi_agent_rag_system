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
from queue import Queue, Empty
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse
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

def extract_quotes_from_page(url, soup):
    """
    Extrahiert Zitate und wichtige Definitionen aus einer Webseite
    
    Args:
        url: URL der Webseite
        soup: BeautifulSoup-Objekt der geparsten Seite
        
    Returns:
        Liste von Dictionaries mit Zitaten und Definitionen
    """
    quotes = []
    
    # Extrahiere Blockquotes
    blockquotes = soup.find_all('blockquote')
    print(f"[DEBUG] Gefundene Blockquotes auf {url}: {len(blockquotes)}")
    for i, quote in enumerate(blockquotes):
        quote_text = quote.get_text().strip()
        if quote_text:
            quotes.append({
                "content": quote_text,
                "source": "blockquote",
                "url": url,
                "title": soup.title.string if soup.title else ""
            })
    
    # Extrahiere Definitionen (oft in <dl>, <dt>, <dd> Tags)
    definition_lists = soup.find_all('dl')
    print(f"[DEBUG] Gefundene Definition Lists auf {url}: {len(definition_lists)}")
    for dl in definition_lists:
        terms = dl.find_all('dt')
        descriptions = dl.find_all('dd')
        
        for i, term in enumerate(terms):
            if i < len(descriptions):
                term_text = term.get_text().strip()
                desc_text = descriptions[i].get_text().strip()
                if term_text and desc_text:
                    quotes.append({
                        "content": f"{term_text}: {desc_text}",
                        "source": "definition",
                        "url": url,
                        "title": soup.title.string if soup.title else ""
                    })
    
    # Extrahiere hervorgehobenen Text (oft in <em>, <strong>, <b>, <i> Tags innerhalb von <p>)
    paragraphs = soup.find_all('p')
    emphasized_count = 0
    for p in paragraphs:
        # Suche nach hervorgehobenem Text
        emphasized = p.find_all(['em', 'strong', 'b', 'i'])
        for em in emphasized:
            # Prüfe, ob der hervorgehobene Text lang genug ist, um relevant zu sein
            em_text = em.get_text().strip()
            if len(em_text) > 15:  # Mindestlänge für relevante Hervorhebungen
                emphasized_count += 1
                # Hole den umgebenden Absatz für Kontext
                context = p.get_text().strip()
                quotes.append({
                    "content": f"Hervorgehoben: {em_text} (Kontext: {context})",
                    "source": "emphasis",
                    "url": url,
                    "title": soup.title.string if soup.title else ""
                })
    print(f"[DEBUG] Gefundene hervorgehobene Texte auf {url}: {emphasized_count}")
    
    # Extrahiere Text aus Infoboxen oder Hinweisen (oft in <div class="note">, <div class="info">, etc.)
    info_boxes = soup.select('div.note, div.info, div.warning, div.tip, div.important')
    print(f"[DEBUG] Gefundene Infoboxen auf {url}: {len(info_boxes)}")
    for box in info_boxes:
        box_text = box.get_text().strip()
        if box_text:
            box_class = box.get('class', [''])[0]
            quotes.append({
                "content": f"{box_class.capitalize()}: {box_text}",
                "source": f"infobox_{box_class}",
                "url": url,
                "title": soup.title.string if soup.title else ""
            })
    
    print(f"[DEBUG] Insgesamt extrahierte Quotes auf {url}: {len(quotes)}")
    return quotes

def normalize_url(url):
        parsed = urlparse(url)
        
        # 1) Fragment entfernen (Anchor)
        parsed = parsed._replace(fragment="")
        
        # 2) http vs. https ignorieren – wir setzen alles auf https:
        #    (Du kannst es auch leer lassen, s. weiter unten.)
        scheme = parsed.scheme.lower()
        if scheme in ["http", "https"]:
            scheme = "https"
        else:
            # Andere Protokolle (ftp, mailto etc.) ggf. erhalten oder filtern
            # Hier vereinfachter Fall: einfach beibehalten
            pass

        # 3) Trailing Slash entfernen, falls es nicht die komplette Root-URL ist
        path = parsed.path
        if path.endswith("/") and path != "/":
            path = path[:-1]
        
        # Optional: Netloc in Kleinschreibung
        netloc = parsed.netloc.lower()
        
        # 4) Zusammenbauen
        #    Wenn du das Scheme komplett entfernen willst, setz `scheme = ""`
        new_url = urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))
        return new_url

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
    
    # Get the domain of the original URL
    original_domain = urlparse(url).netloc

    for link in soup.find_all('a'):
        href = link.get('href')
        if href:
            # Skip mailto links
            if href.startswith('mailto:'):
                continue
                
            absolute_url = urljoin(url, href)
            # Only include URLs from the same domain
            if urlparse(absolute_url).netloc == original_domain:
                subpages.append(normalize_url(absolute_url))

    return list(set(subpages))  # Remove duplicates

def update_progress():
    global completed_pages, total_pages
    with lock:
        # Ensure total_pages is at least 1 to avoid division by zero
        if not hasattr(update_progress, 'total_pages_initialized'):
            total_pages = 1
            update_progress.total_pages_initialized = True
        progress = (completed_pages / total_pages) * 100 if total_pages > 0 else 0
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
    quotes = []
    
    if soup is not None:
        metadata = extract_metadata_from_page(url, soup)
        quotes = extract_quotes_from_page(url, soup)
    
    return subpages, text, metadata, quotes

def scrape_website(url, visited=None, max_workers=10, depth=10, chunking_strategy="semantic"):
    """
    Crawlt eine Website und extrahiert Inhalte, Metadaten und Zitate.
    
    Args:
        url: Start-URL für den Crawler
        visited: Set von bereits besuchten URLs (optional)
        max_workers: Anzahl der parallelen Worker-Threads
        depth: Maximale Anzahl der zu crawlenden Seiten
        chunking_strategy: Strategie für das Aufteilen des Textes
        
    Returns:
        Dictionary mit verarbeiteten Daten
    """
    global total_pages, completed_pages
    
    # Initialisiere das Set der besuchten URLs, falls nicht übergeben
    if visited is None:
        visited = set()
    
    # Verwende ein Thread-sicheres Set für besuchte URLs
    visited_lock = threading.Lock()
    
    # Initialisiere die Ergebnislisten
    results = []
    all_quotes = []
    results_lock = threading.Lock()
    
    # Initialisiere die Queue für zu crawlende URLs
    url_queue = Queue()
    url_queue.put(url)
    
    # Setze den Zähler für die Gesamtanzahl der Seiten
    with lock:
        total_pages = 1  # Starte mit der ersten URL
        completed_pages = 0  # Setze completed_pages zurück

    
    # Funktion zum sicheren Hinzufügen einer URL zur Queue
    def add_url_to_queue(new_url):
        global total_pages  # Deklariere total_pages als global
        
        with visited_lock:
            if new_url not in visited and len(visited) < depth:
                visited.add(new_url)
                url_queue.put(new_url)
                with lock:
                    total_pages += 1
    
    # Initialisiere die erste URL
    with visited_lock:
        visited.add(url)
    
    # Funktion für Worker-Threads
    def worker():
        global completed_pages
        while True:
            try:
                # Hole die nächste URL aus der Queue mit Timeout
                try:
                    current_url = url_queue.get(timeout=2)
                except Empty:
                    # Keine URLs mehr in der Queue
                    break
                
                try:
                    # Crawle die Seite
                    subpages, text, metadata, quotes = scrape_and_collect(current_url)
                    # Füge das Ergebnis zur Liste hinzu
                    with results_lock:
                        result = {
                            "url": current_url,
                            "content": text,
                            **metadata
                        }
                        results.append(result)
                        all_quotes.extend(quotes)
                    
                    # Aktualisiere den Fortschritt
                    with lock:
                        completed_pages += 1
                    update_progress()
                    
                    # Füge neue Subpages zur Queue hinzu
                    for subpage in subpages:
                        add_url_to_queue(subpage)
                
                except Exception as e:
                    print(f"Fehler beim Verarbeiten von {current_url}: {str(e)}")
                    traceback.print_exc()
                
                finally:
                    # Markiere die Aufgabe als erledigt
                    url_queue.task_done()
            
            except Exception as e:
                print(f"Unerwarteter Fehler im Worker-Thread: {str(e)}")
                traceback.print_exc()
    
    # Starte die Worker-Threads
    threads = []
    for _ in range(max_workers):
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        threads.append(thread)
    
    # Warte, bis alle URLs verarbeitet wurden oder die maximale Tiefe erreicht ist
    try:
        # Warte auf die Verarbeitung aller URLs mit Timeout
        url_queue.join()
        
        # Zusätzliche Sicherheit: Warte auf leere Queue
        timeout = 30  # 30 Sekunden Timeout
        start_time = time.time()
        while not url_queue.empty() and time.time() - start_time < timeout:
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("Crawling wurde vom Benutzer unterbrochen.")
    
    # Verarbeite die gesammelten Daten
    processed_data = {}
    
    # Debug: Alle URLs ausgeben
    print("\n[DEBUG] Alle gesammelten URLs:")
    for i, url in enumerate(results):
        print(f"  {i+1}. {url['url']}")
    print(f"Insgesamt {len(results)} URLs gefunden.\n")
    
    # Verarbeite die Ergebnisse
    for result in results:
        url = result["url"]
        content = result["content"]
        
        # Teile den Text in Chunks auf
        chunks = split_text_with_strategy(content, chunking_strategy)
        
        # Konvertiere Chunks in das richtige Format
        formatted_chunks = []
        for chunk in chunks:
            if isinstance(chunk, str):
                formatted_chunks.append({"content": chunk, "type": "text"})
            else:
                formatted_chunks.append(chunk)
        
        # Speichere die Daten im Dictionary
        processed_data[url] = {
            "url": url,
            "content": content,
            "chunks": formatted_chunks,
            "title": result.get("title", ""),
            "chapter": result.get("chapter", ""),
            "section": result.get("section", ""),
            "last_updated": result.get("last_updated", ""),
            "importance_score": result.get("importance_score", 0.5)
        }
    
    # Speichere die Quotes separat
    processed_data["quotes"] = all_quotes
    
    print(f"Crawling abgeschlossen. {len(processed_data) - 1} Seiten verarbeitet, {len(all_quotes)} Zitate extrahiert.")
    
    return processed_data

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
    
    # Debug: Alle URLs ausgeben
    print("\n[DEBUG] Alle gesammelten URLs:")
    if isinstance(collected_data, dict):
        urls = [url for url in collected_data.keys() if url != "quotes"]
        for i, url in enumerate(urls):
            print(f"  {i+1}. {url}")
        print(f"Insgesamt {len(urls)} URLs gefunden.\n")
    elif isinstance(collected_data, list):
        urls = [item.get('url', 'No URL') for item in collected_data if isinstance(item, dict)]
        for i, url in enumerate(urls):
            print(f"  {i+1}. {url}")
        print(f"Insgesamt {len(urls)} URLs gefunden.\n")
    
    # Stelle sicher, dass eine Verbindung zu Weaviate besteht
    if not ensure_weaviate_connection():
        print("[FEHLER] Keine Verbindung zu Weaviate möglich. Daten können nicht gespeichert werden.")
        return
    
    # Erstelle Schemas, falls sie nicht existieren
    if not create_weaviate_schema():
        print("[FEHLER] Fehler beim Erstellen der Schemas. Daten können nicht gespeichert werden.")
        return
    
    # Extrahiere Quotes, falls vorhanden
    quotes = []
    if isinstance(collected_data, dict) and "quotes" in collected_data:
        quotes = collected_data.pop("quotes")
        print(f"[DEBUG] Extrahierte {len(quotes)} Quotes aus den gesammelten Daten.")
        for i, quote in enumerate(quotes):
            print(f"[DEBUG] Quote {i+1}: {quote.get('content', 'Kein Inhalt')[:50]}...")
    
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
    successful_quotes = 0
    failed_quotes = 0
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
                # Stelle sicher, dass chunk ein Dictionary ist
                if isinstance(chunk, dict):
                    chunk_content = chunk.get('content', '')
                else:
                    chunk_content = str(chunk)
                
                # Erstelle die Eigenschaften für den Chunk
                chunk_properties = {
                    "url": url,
                    "content_chunk": chunk_content,
                    "chunk_nr": i,
                    "date": current_date,
                    "title": data.get('title', ''),
                    "chapter": data.get('chapter', ''),
                    "section": data.get('section', ''),
                    "last_updated": data.get('last_updated', ''),
                    "importance_score": data.get('importance_score', 0.5),
                    "chunk_type": chunk.get('type', 'text') if isinstance(chunk, dict) else 'text'
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
    
    # Speichere die Quotes in der Quote-Collection
    if quotes:
        print(f"[Weaviate] Beginne mit dem Speichern von {len(quotes)} Quotes in Weaviate...")
        
        # Stelle sicher, dass die Quote-Collection existiert
        try:
            # Versuche, die Quote-Collection zu holen
            quote_collection = weaviate_instance.collections.get("Quote")
            print(f"[DEBUG] Quote-Collection erfolgreich abgerufen.")
        except Exception as e:
            print(f"[WARNUNG] Konnte Collection 'Quote' nicht abrufen: {str(e)}")
            print(f"[INFO] Versuche, die Quote-Collection zu erstellen...")
            
            try:
                # Erstelle die Quote-Collection
                quote_properties = [
                    wvc.config.Property(name="url", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="source", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="date", data_type=wvc.config.DataType.DATE),
                    wvc.config.Property(name="title", data_type=wvc.config.DataType.TEXT)
                ]
                
                quote_collection = weaviate_instance.collections.create(
                    name="Quote",
                    properties=quote_properties,
                    vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_openai()
                )
                print(f"[INFO] Quote-Collection erfolgreich erstellt.")
            except Exception as create_error:
                print(f"[FEHLER] Konnte Collection 'Quote' nicht erstellen: {str(create_error)}")
                return
        
        # Speichere jedes Quote einzeln
        for i, quote in enumerate(quotes):
            try:
                print(f"[DEBUG] Speichere Quote {i+1}: {quote.get('content', 'Kein Inhalt')[:50]}...")
                
                # Erstelle die Eigenschaften für das Quote
                quote_properties = {
                    "url": quote.get("url", ""),
                    "content": quote.get("content", ""),
                    "source": quote.get("source", ""),
                    "date": current_date,
                    "title": quote.get("title", "")
                }
                
                # Direktes Speichern ohne Batch
                try:
                    # Stelle sicher, dass die Quote-Collection noch existiert
                    quote_collection = weaviate_instance.collections.get("Quote")
                    
                    # Füge das Quote ein
                    quote_collection.data.insert(quote_properties)
                    successful_quotes += 1
                    print(f"Quote {i+1} erfolgreich gespeichert.")
                except Exception as insert_error:
                    print(f"[FEHLER] Speichern von Quote {i+1} fehlgeschlagen: {str(insert_error)}")
                    failed_quotes += 1
            except Exception as e:
                failed_quotes += 1
                print(f"[FEHLER] Speichern von Quote {i+1} fehlgeschlagen: {str(e)}")
        
        print(f"[Weaviate] {successful_quotes} von {len(quotes)} Quotes wurden erfolgreich in Weaviate gespeichert.")
        if failed_quotes > 0:
            print(f"[Weaviate] {failed_quotes} Quotes konnten nicht gespeichert werden.")
    else:
        print("[WARNUNG] Keine Quotes zum Speichern gefunden.")
    
    # Zeige eine Zusammenfassung der Ergebnisse an
    print(f"[Weaviate] {successful_chunks} von {total_chunks} Chunks wurden erfolgreich in Weaviate gespeichert.")
    if failed_chunks > 0:
        print(f"[Weaviate] {failed_chunks} Chunks konnten nicht gespeichert werden.")
    if failed_quotes > 0:
        print(f"[Weaviate] {failed_quotes} Quotes konnten nicht gespeichert werden.")
    if len(all_failed_objects) > 0:
        print(f"[Weaviate] {len(all_failed_objects)} Objekte konnten nicht gespeichert werden.")
        for failure in all_failed_objects[:5]:  # Zeige die ersten 5 Fehler an
            print(f"  - URL: {failure['url']}, Chunk: {failure['chunk_nr']}, Fehler: {failure['error']}")
        if len(all_failed_objects) > 5:
            print(f"  - ... und {len(all_failed_objects) - 5} weitere Fehler.")

def create_summaries_for_collected_data(collected_data):
    """
    Erstellt Zusammenfassungen für die gesammelten Daten.
    
    Args:
        collected_data: Die gesammelten Daten, für die Zusammenfassungen erstellt werden sollen.
                       Kann eine Liste oder ein Dictionary sein.
    
    Returns:
        None
    """
    global weaviate_instance
    
    # Debug: Alle URLs ausgeben
    print("\n[DEBUG] Alle URLs für Zusammenfassungen:")
    if isinstance(collected_data, dict):
        urls = [url for url in collected_data.keys() if url != "quotes"]
        for i, url in enumerate(urls):
            print(f"  {i+1}. {url}")
        print(f"Insgesamt {len(urls)} URLs für Zusammenfassungen gefunden.\n")
    elif isinstance(collected_data, list):
        urls = [item.get('url', 'No URL') for item in collected_data if isinstance(item, dict)]
        for i, url in enumerate(urls):
            print(f"  {i+1}. {url}")
        print(f"Insgesamt {len(urls)} URLs für Zusammenfassungen gefunden.\n")
    
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
    Hauptfunktion zum Ausführen des Crawlers.
    """
    try:
        # Prüfe, ob Befehlszeilenargumente übergeben wurden
        if len(sys.argv) > 1:
            url = sys.argv[1]
            depth = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            strategy = sys.argv[3] if len(sys.argv) > 3 else "recursive"
            
            # Entferne das '@' am Anfang der URL, falls vorhanden
            if url.startswith('@'):
                url = url[1:]
            
            print(f"Starte Crawling von {url} mit Tiefe {depth} und Strategie {strategy}...")
        else:
            # Interaktiver Modus
            url = input("Geben Sie eine Webseite ein, um das Scraping zu beginnen: ")
            depth_input = input("Geben Sie die maximale Tiefe ein (Standard: 5): ")
            depth = int(depth_input) if depth_input.strip() else 5
            
            strategy_input = input("Geben Sie die Chunking-Strategie ein (recursive, semantic, paragraph, Standard: recursive): ")
            strategy = strategy_input.strip() if strategy_input.strip() else "recursive"
        
        # Starte den Crawler
        print(f"Starte Crawling von {url} mit Tiefe {depth} und Strategie {strategy}...")
        data = scrape_website(url, depth=depth, chunking_strategy=strategy)
        
        # Speichere die Daten in Weaviate
        print("Speichere Daten in Weaviate...")
        save_to_weaviate(data)
        
        # Erstelle Zusammenfassungen
        print("Erstelle Zusammenfassungen...")
        create_summaries_for_collected_data(data)
        
        print("[STATUS] CRAWLING_COMPLETE")
    except Exception as e:
        print(f"[FEHLER] Ein Fehler ist aufgetreten: {str(e)}")
        traceback.print_exc()
        print("[STATUS] CRAWLING_ERROR")

if __name__ == "__main__":
    main()