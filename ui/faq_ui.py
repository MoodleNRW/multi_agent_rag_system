"""
UI-Komponenten für die FAQ-Verwaltung.
"""

import chainlit as cl
import logging
import datetime
from typing import Dict, Any, Optional
from vector_stores.weaviate_client import create_weaviate_client, ensure_weaviate_connection
import asyncio
import weaviate.classes as wvc

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def show_save_to_faq_option(question: str, answer: str):
    """
    Zeigt eine Schaltfläche zum Speichern der Frage und Antwort als FAQ an.
    
    Args:
        question: Die Frage
        answer: Die Antwort
    """
    logger.info(f"Zeige FAQ-Speicheroption für Frage: {question[:50]}...")
    
    msg = cl.Message(content="💾 **In FAQ speichern**\n\nMöchten Sie diese Frage und Antwort in der FAQ-Datenbank speichern?")
    
    # Erstelle ein Payload mit Frage und Antwort
    payload = {
        "question": question,
        "answer": answer
    }
    
    # Erstelle Aktionen für Speichern und Abbrechen
    actions = [
        cl.Action(name="save_to_faq", payload=payload, label="✅ Als FAQ speichern"),
        cl.Action(name="cancel_save_to_faq", payload={}, label="❌ Nicht speichern")
    ]
    
    msg.actions = actions
    await msg.send()

@cl.action_callback("save_to_faq")
async def on_save_to_faq(action):
    """
    Callback für die Aktion 'Als FAQ speichern'.
    """
    await action.remove()
    
    # Extrahiere Frage und Antwort aus dem Payload
    payload = action.payload
    question = payload.get("question", "")
    answer = payload.get("answer", "")
    
    if not question or not answer:
        await cl.Message(content="⚠️ Fehler: Frage oder Antwort fehlt.").send()
        return
    
    # Speichere die FAQ in der Datenbank
    success = await save_faq_to_database(question, answer)
    
    if success:
        await cl.Message(content="✅ Die Frage und Antwort wurden erfolgreich als FAQ gespeichert.").send()
    else:
        await cl.Message(content="⚠️ Fehler beim Speichern der FAQ. Bitte versuchen Sie es später erneut.").send()

@cl.action_callback("cancel_save_to_faq")
async def on_cancel_save_to_faq(action):
    """
    Callback für die Aktion 'Nicht speichern'.
    """
    await action.remove()
    await cl.Message(content="❌ Die FAQ wurde nicht gespeichert.").send()

async def save_faq_to_database(question: str, answer: str) -> bool:
    """
    Speichert eine FAQ in der Weaviate-Datenbank.
    
    Args:
        question: Die Frage
        answer: Die Antwort
        
    Returns:
        bool: True bei erfolgreichem Speichern, False sonst
    """
    client = None
    try:
        # Erstelle einen temporären Weaviate-Client
        client = create_weaviate_client()
        logger.info("Temporärer Weaviate-Client für FAQ-Speicherung erstellt.")
        
        # Stelle explizit sicher, dass der Client verbunden ist
        if not client.is_connected():
            logger.info("Verbinde Weaviate-Client für FAQ-Speicherung explizit...")
            client.connect()
        
        # Stelle sicher, dass der Client verbunden ist
        if not ensure_weaviate_connection(client):
            logger.error("Keine Verbindung zu Weaviate möglich.")
            return False
        
        # Prüfe, ob die FAQ-Collection existiert
        collection_names = client.collections.list_all(simple=True)
        #logger.info(f"Verfügbare Collections: {collection_names}")
        
        if "FAQ" not in collection_names:
            logger.error("FAQ-Collection existiert nicht.")
            # Versuche, die Collection zu erstellen
            logger.info("Versuche, die FAQ-Collection zu erstellen...")
            from vector_stores.weaviate_client import create_weaviate_schema
            if create_weaviate_schema(client):
                logger.info("FAQ-Collection erfolgreich erstellt.")
            else:
                logger.error("Konnte FAQ-Collection nicht erstellen.")
                return False
        
        # Hole die FAQ-Collection
        faq_collection = client.collections.get("FAQ")
        logger.info("FAQ-Collection abgerufen.")
        
        # Erstelle ein neues FAQ-Objekt mit korrekt formatiertem Datum
        # Weaviate erwartet Datumsangaben im ISO 8601-Format: YYYY-MM-DDThh:mm:ss.sssZ
        current_date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        faq_object = {
            "question": question,
            "answer": answer,
            "date": current_date,
            "approved": True  # Standardmäßig genehmigt, da vom Benutzer bestätigt
        }
        logger.info(f"FAQ-Objekt erstellt: Frage={question[:30]}..., Datum={current_date}")
        
        # Füge das Objekt zur Collection hinzu
        try:
            result = faq_collection.data.insert(faq_object)
            logger.info(f"FAQ erfolgreich gespeichert. Ergebnis: {result}")
            
            # Warte explizit auf die Indizierung (mit Timeout)
            success = await wait_for_object_indexing(client, "FAQ", 10)  # 10 Sekunden Timeout
            if not success:
                logger.warning("Timeout beim Warten auf die Indizierung des FAQ-Objekts.")
            
            # Überprüfe, ob das Objekt tatsächlich gespeichert wurde
            count_result = faq_collection.aggregate.over_all()
            obj_count = 0
            if hasattr(count_result, 'total_count'):
                obj_count = count_result.total_count
            logger.info(f"Anzahl der FAQ-Objekte nach dem Speichern: {obj_count}")
            
            # Wenn keine Objekte gefunden wurden, versuche es mit explizitem Commit
            if obj_count == 0:
                logger.warning("Keine FAQ-Objekte nach dem Speichern gefunden. Versuche expliziten Commit...")
                try:
                    # Versuche einen expliziten Datenbankcommit (falls verfügbar)
                    if hasattr(client, 'batch'):
                        client.batch.commit()
                        logger.info("Expliziter Batch-Commit durchgeführt.")
                        
                        # Prüfe erneut nach dem Commit
                        count_result = faq_collection.aggregate.over_all()
                        if hasattr(count_result, 'total_count'):
                            obj_count = count_result.total_count
                        logger.info(f"Anzahl der FAQ-Objekte nach explizitem Commit: {obj_count}")
                except Exception as commit_error:
                    logger.error(f"Fehler beim expliziten Commit: {str(commit_error)}")
            
            return obj_count > 0  # Erfolgreich, wenn mindestens ein Objekt vorhanden ist
        except Exception as e:
            logger.error(f"Fehler beim Einfügen des FAQ-Objekts: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Fehler beim Speichern der FAQ: {str(e)}", exc_info=True)
        return False
    finally:
        # Schließe den Client
        if client:
            try:
                logger.info("Schließe temporären Weaviate-Client für FAQ-Speicherung...")
                client.close()
                logger.info("Temporärer Weaviate-Client für FAQ-Speicherung geschlossen.")
            except Exception as close_error:
                logger.error(f"Fehler beim Schließen des Clients: {str(close_error)}")
                # Hier keine Exception werfen, um den Hauptfehler nicht zu überdecken

async def wait_for_object_indexing(client, collection_name: str, timeout_seconds: int = 10) -> bool:
    """
    Wartet, bis ein Objekt indiziert ist.
    
    Args:
        client: Der Weaviate-Client
        collection_name: Der Name der Collection
        timeout_seconds: Timeout in Sekunden
        
    Returns:
        bool: True, wenn die Indizierung erfolgreich war, sonst False
    """
    start_time = datetime.datetime.now()
    logger.info(f"Warte auf Indizierung von Objekten in Collection {collection_name}...")
    
    while (datetime.datetime.now() - start_time).total_seconds() < timeout_seconds:
        try:
            # Hole die Collection
            collection = client.collections.get(collection_name)
            
            # Prüfe, ob Objekte vorhanden sind
            count_result = collection.aggregate.over_all()
            obj_count = 0
            if hasattr(count_result, 'total_count'):
                obj_count = count_result.total_count
            
            if obj_count > 0:
                logger.info(f"Indizierung abgeschlossen. {obj_count} Objekte gefunden.")
                return True
            
            # Kurze Pause vor dem nächsten Versuch
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"Fehler beim Prüfen der Indizierung: {str(e)}")
            await asyncio.sleep(0.5)
    
    logger.warning(f"Timeout beim Warten auf Indizierung nach {timeout_seconds} Sekunden.")
    return False

@cl.action_callback("list_faqs")
async def on_list_faqs(action):
    """
    Callback für die Aktion 'FAQs anzeigen'.
    """
    await action.remove()
    
    # Hole FAQs aus der Datenbank
    faqs = await get_faqs_from_database()
    
    if not faqs:
        await cl.Message(content="ℹ️ Es sind keine FAQs in der Datenbank vorhanden.").send()
        return
    
    # Zeige FAQs an
    content = "## 📚 FAQ-Liste\n\n"
    
    for i, faq in enumerate(faqs, 1):
        question = faq.get("question", "")
        answer = faq.get("answer", "")
        date = faq.get("date", "")
        
        content += f"### {i}. {question}\n\n"
        content += f"{answer}\n\n"
        content += f"*Hinzugefügt am: {date}*\n\n"
        content += "---\n\n"
    
    await cl.Message(content=content).send()

async def get_faqs_from_database(limit: int = 10) -> list:
    """
    Holt FAQs aus der Weaviate-Datenbank.
    
    Args:
        limit: Maximale Anzahl der abzurufenden FAQs
        
    Returns:
        list: Liste der FAQs
    """
    client = None
    try:
        # Erstelle einen temporären Weaviate-Client
        client = create_weaviate_client()
        logger.info("Temporärer Weaviate-Client für FAQ-Abruf erstellt.")
        
        # Stelle sicher, dass der Client verbunden ist
        if not ensure_weaviate_connection(client):
            logger.error("Keine Verbindung zu Weaviate möglich.")
            return []
        
        # Prüfe, ob die FAQ-Collection existiert
        collection_names = client.collections.list_all(simple=True)
        #logger.info(f"Verfügbare Collections: {collection_names}")
        
        if "FAQ" not in collection_names:
            logger.error("FAQ-Collection existiert nicht.")
            return []
        
        # Hole die FAQ-Collection
        faq_collection = client.collections.get("FAQ")
        logger.info("FAQ-Collection abgerufen.")
        
        # Prüfe, ob die Collection Objekte enthält
        count_result = faq_collection.aggregate.over_all()
        obj_count = 0
        if hasattr(count_result, 'total_count'):
            obj_count = count_result.total_count
        logger.info(f"Anzahl der FAQ-Objekte in der Collection: {obj_count}")
        
        if obj_count == 0:
            logger.warning("Keine FAQ-Objekte in der Collection gefunden.")
            return []
        
        # Hole alle FAQs - versuche verschiedene Abfragemethoden
        logger.info(f"Rufe bis zu {limit} FAQ-Objekte ab...")
        
        # Methode 1: Standardabfrage mit Sortierung
        try:
            logger.info("Versuche Abfrage mit Sortierung...")
            response = faq_collection.query.fetch_objects(
                limit=limit,
                sort=[{"path": ["date"], "order": "desc"}]  # Sortiere nach Datum absteigend
            )
            
            # Extrahiere die Objekte
            faqs = []
            if hasattr(response, 'objects') and response.objects:
                logger.info(f"Anzahl der abgerufenen FAQ-Objekte: {len(response.objects)}")
                for obj in response.objects:
                    if hasattr(obj, 'properties'):
                        faqs.append(obj.properties)
                        logger.info(f"FAQ gefunden: {obj.properties.get('question', '')[:30]}...")
                
                if faqs:
                    return faqs
            else:
                logger.warning("Keine FAQ-Objekte in der Antwort gefunden (Methode 1).")
        except Exception as e:
            logger.error(f"Fehler bei Abfragemethode 1: {str(e)}")
        
        # Methode 2: Einfache Abfrage ohne Sortierung
        try:
            logger.info("Versuche einfache Abfrage ohne Sortierung...")
            response = faq_collection.query.fetch_objects(limit=limit)
            
            # Extrahiere die Objekte
            faqs = []
            if hasattr(response, 'objects') and response.objects:
                logger.info(f"Anzahl der abgerufenen FAQ-Objekte: {len(response.objects)}")
                for obj in response.objects:
                    if hasattr(obj, 'properties'):
                        faqs.append(obj.properties)
                        logger.info(f"FAQ gefunden: {obj.properties.get('question', '')[:30]}...")
                
                if faqs:
                    return faqs
            else:
                logger.warning("Keine FAQ-Objekte in der Antwort gefunden (Methode 2).")
        except Exception as e:
            logger.error(f"Fehler bei Abfragemethode 2: {str(e)}")
        
        # Methode 3: Direkte Abfrage mit where-Filter
        try:
            logger.info("Versuche Abfrage mit where-Filter...")
            response = faq_collection.query.fetch_objects(
                limit=limit,
                filters={"path": ["approved"], "operator": "Equal", "valueBoolean": True}
            )
            
            # Extrahiere die Objekte
            faqs = []
            if hasattr(response, 'objects') and response.objects:
                logger.info(f"Anzahl der abgerufenen FAQ-Objekte: {len(response.objects)}")
                for obj in response.objects:
                    if hasattr(obj, 'properties'):
                        faqs.append(obj.properties)
                        logger.info(f"FAQ gefunden: {obj.properties.get('question', '')[:30]}...")
                
                if faqs:
                    return faqs
            else:
                logger.warning("Keine FAQ-Objekte in der Antwort gefunden (Methode 3).")
        except Exception as e:
            logger.error(f"Fehler bei Abfragemethode 3: {str(e)}")
        
        # Wenn alle Methoden fehlschlagen, gib eine leere Liste zurück
        logger.error("Alle Abfragemethoden sind fehlgeschlagen. Keine FAQs gefunden.")
        return []
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der FAQs: {str(e)}", exc_info=True)
        return []
    finally:
        # Schließe den Client
        if client:
            try:
                client.close()
                logger.info("Temporärer Weaviate-Client für FAQ-Abruf geschlossen.")
            except Exception as e:
                logger.error(f"Fehler beim Schließen des Clients: {str(e)}")
                pass

async def debug_weaviate_database() -> str:
    """
    Debuggt die Weaviate-Datenbank und gibt Informationen zurück.
    
    Returns:
        str: Debug-Informationen
    """
    client = None
    try:
        # Erstelle einen temporären Weaviate-Client
        client = create_weaviate_client()
        
        # Stelle explizit sicher, dass der Client verbunden ist
        if not client.is_connected():
            logger.info("Verbinde Weaviate-Client für Debug explizit...")
            client.connect()
        
        # Stelle sicher, dass der Client verbunden ist
        if not ensure_weaviate_connection(client):
            return "⚠️ Keine Verbindung zu Weaviate möglich."
        
        # Sammle Debug-Informationen
        debug_info = "## 🔍 Weaviate-Datenbank Debug\n\n"
        
        # Prüfe, ob die Collections existieren
        collection_names = client.collections.list_all(simple=True)
        debug_info += f"### Collections\n\n"
        debug_info += f"Gefundene Collections: {', '.join(collection_names) if collection_names else 'Keine'}\n\n"
        
        # Prüfe jede Collection
        for collection_name in collection_names:
            debug_info += f"### Collection: {collection_name}\n\n"
            
            try:
                collection = client.collections.get(collection_name)
                
                # Prüfe Vektorisierer-Konfiguration
                vectorizer_info = None
                
                # Versuche verschiedene Möglichkeiten, die Vektorisierer-Konfiguration zu erhalten
                try:
                    # Option 1: Über Konfigurationsattribute
                    if hasattr(collection.config, 'vectorizer_config'):
                        vectorizer_info = collection.config.vectorizer_config.vectorizer
                    # Option 2: Über vectorizers
                    elif hasattr(collection.config, 'vectorizers'):
                        vectorizers = collection.config.vectorizers
                        if vectorizers and len(vectorizers) > 0:
                            vectorizer_info = vectorizers[0]
                    # Option 3: Direktes Attribut (ältere Versionen)
                    elif hasattr(collection.config, 'vectorizer'):
                        vectorizer_info = collection.config.vectorizer
                        
                    logger.info(f"FAQ-Collection Vektorisierer: {vectorizer_info}")
                
                    if not vectorizer_info or vectorizer_info != "text2vec-openai":
                        # Anstatt einen Fehler zu loggen, informieren wir nur
                        logger.info("Collection verwendet vermutlich 'text2vec-openai', auch wenn die API None zurückgibt")
                        debug_info += f"Vektorisierer: {vectorizer_info} (Anmerkung: Die API gibt möglicherweise None zurück, auch wenn text2vec-openai verwendet wird)\n\n"
                        # Keine Neuerststellung nötig
                        faq_needs_recreation = False
                except Exception as e:
                    logger.error(f"Fehler beim Überprüfen des Vektorisierers: {str(e)}")
                    # faq_needs_recreation bleibt auf False
                
                # Prüfe Eigenschaften
                properties = collection.properties.get()
                debug_info += f"Eigenschaften:\n"
                for prop in properties:
                    debug_info += f"- {prop.name} ({prop.data_type})\n"
                debug_info += "\n"
                
                # Zähle Objekte
                count_result = collection.aggregate.over_all()
                obj_count = 0
                if hasattr(count_result, 'total_count'):
                    obj_count = count_result.total_count
                debug_info += f"Anzahl der Objekte: {obj_count}\n\n"
                
                # Wenn es sich um die FAQ-Collection handelt, zeige ein Beispiel
                if collection_name == "FAQ" and obj_count > 0:
                    debug_info += "#### Beispiel-FAQ\n\n"
                    try:
                        example = collection.query.fetch_objects(limit=1)
                        if hasattr(example, 'objects') and example.objects:
                            obj = example.objects[0]
                            properties = obj.properties
                            debug_info += f"Frage: {properties.get('question', 'N/A')}\n\n"
                            debug_info += f"Antwort: {properties.get('answer', 'N/A')}\n\n"
                            debug_info += f"Datum: {properties.get('date', 'N/A')}\n\n"
                            
                            # Teste eine semantische Suche
                            debug_info += "#### Test der semantischen Suche\n\n"
                            try:
                                query = properties.get('question', 'test')[:20]  # Verwende den Anfang der Frage als Testabfrage
                                debug_info += f"Testabfrage: '{query}'\n\n"
                                
                                results = (
                                    collection.query
                                    .near_text(query=query)
                                    .with_additional(["certainty"])
                                    .with_limit(1)
                                    .do()
                                )
                                
                                if hasattr(results, 'objects') and results.objects:
                                    debug_info += "✅ Semantische Suche erfolgreich\n\n"
                                    obj = results.objects[0]
                                    certainty = obj.certainty if hasattr(obj, 'certainty') else "N/A"
                                    debug_info += f"Gefundene Ähnlichkeit: {certainty}\n\n"
                                else:
                                    debug_info += "⚠️ Semantische Suche ergab keine Ergebnisse\n\n"
                            except Exception as e:
                                debug_info += f"⚠️ Fehler bei der semantischen Suche: {str(e)}\n\n"
                                
                                # Wenn die semantische Suche fehlschlägt, versuche eine textbasierte Suche
                                debug_info += "#### Test der textbasierten Suche\n\n"
                                try:
                                    query = properties.get('question', 'test')[:20]
                                    debug_info += f"Testabfrage: '{query}'\n\n"
                                    
                                    results = (
                                        collection.query
                                        .get("question", "answer")
                                        .with_where({
                                            "path": ["question"],
                                            "operator": "Like",
                                            "valueText": f"*{query}*"
                                        })
                                        .with_limit(1)
                                        .do()
                                    )
                                    
                                    if hasattr(results, 'objects') and results.objects:
                                        debug_info += "✅ Textbasierte Suche erfolgreich\n\n"
                                    else:
                                        debug_info += "⚠️ Textbasierte Suche ergab keine Ergebnisse\n\n"
                                except Exception as e2:
                                    debug_info += f"⚠️ Fehler bei der textbasierten Suche: {str(e2)}\n\n"
                    except Exception as e:
                        debug_info += f"⚠️ Fehler beim Abrufen eines Beispiels: {str(e)}\n\n"
            except Exception as e:
                debug_info += f"⚠️ Fehler beim Abrufen von Informationen: {str(e)}\n\n"
        
        return debug_info
    except Exception as e:
        return f"⚠️ Fehler beim Debugging der Weaviate-Datenbank: {str(e)}"
    finally:
        # Schließe den Client
        if client:
            try:
                logger.info("Schließe temporären Weaviate-Client für Debug...")
                client.close()
                logger.info("Temporärer Weaviate-Client für Debug geschlossen.")
            except Exception as close_error:
                logger.error(f"Fehler beim Schließen des Debug-Clients: {str(close_error)}")
                # Hier keine Exception werfen, um den Hauptfehler nicht zu überdecken

async def search_faq_database(query: str, similarity_threshold: float = 0.7, limit: int = 3) -> list:
    """
    Sucht in der FAQ-Datenbank nach ähnlichen Fragen.
    
    Args:
        query: Die Suchanfrage
        similarity_threshold: Schwellenwert für die Ähnlichkeit (0-1)
        limit: Maximale Anzahl der Ergebnisse
        
    Returns:
        list: Liste der gefundenen FAQs
    """
    # Vereinfachte Implementierung, die dem Muster von Chunks, Summaries und Quotes folgt
    try:
        # Verwende den globalen Weaviate-Client
        from vector_stores.retriever import ensure_global_client
        weaviate_client = ensure_global_client()
        if not weaviate_client:
            logger.error("Fehler: Konnte keine Verbindung zum Weaviate-Client herstellen.")
            return []
        
        # Stelle sicher, dass der Client verbunden ist
        if not weaviate_client.is_connected():
            logger.info("Der WeaviateClient ist nicht verbunden. Verbinde...")
            try:
                weaviate_client.connect()
            except Exception as e:
                logger.error(f"Fehler beim Verbinden des Weaviate-Clients: {str(e)}")
                return []

        # Prüfe, ob die FAQ-Collection existiert
        collection_names = weaviate_client.collections.list_all(simple=True)
        if "FAQ" not in collection_names:
            logger.error("FAQ-Collection existiert nicht.")
            return []

        # Führe semantische Suche durch
        try:
            logger.info(f"Führe semantische Suche nach '{query[:50]}...' durch")
            
            # Hole die FAQ-Collection
            faq_collection = weaviate_client.collections.get("FAQ")
            
            # Führe semantische Suche durch - genau wie bei Chunks/Summaries/Quotes
            results = faq_collection.query.near_text(
                query=query,
                limit=limit,
                return_metadata=wvc.query.MetadataQuery(distance=True),
                return_properties=["question", "answer", "date"]
            )
            
            # Extrahiere die Ergebnisse
            faqs = []
            if hasattr(results, 'objects') and results.objects:
                for obj in results.objects:
                    # Berechne Ähnlichkeit aus Distanz
                    similarity = 0
                    if hasattr(obj, 'metadata') and hasattr(obj.metadata, 'distance'):
                        distance = obj.metadata.distance
                        if distance is not None:
                            similarity = 1.0 - distance
                    
                    # Nur Ergebnisse mit ausreichender Ähnlichkeit verwenden
                    if similarity >= similarity_threshold:
                        faq = {
                            "question": obj.properties.get("question", ""),
                            "answer": obj.properties.get("answer", ""),
                            "date": obj.properties.get("date", ""),
                            "similarity": similarity
                        }
                        faqs.append(faq)
                        logger.info(f"FAQ gefunden mit Ähnlichkeit: {similarity}")
            
            logger.info(f"Semantische Suche ergab {len(faqs)} Ergebnisse.")
            return faqs
            
        except Exception as e:
            logger.error(f"Fehler bei der semantischen Suche: {str(e)}")
            return []
            
    except Exception as e:
        logger.error(f"Fehler bei der FAQ-Suche: {str(e)}", exc_info=True)
        return [] 