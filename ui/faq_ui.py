"""
UI-Komponenten für die FAQ-Verwaltung.
"""

import chainlit as cl
import logging
import datetime
from typing import Dict, Any, Optional
from vector_stores.weaviate_client import create_weaviate_client, ensure_weaviate_connection

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
        
        # Stelle sicher, dass der Client verbunden ist
        if not ensure_weaviate_connection(client):
            logger.error("Keine Verbindung zu Weaviate möglich.")
            return False
        
        # Prüfe, ob die FAQ-Collection existiert
        collection_names = client.collections.list_all(simple=True)
        logger.info(f"Verfügbare Collections: {collection_names}")
        
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
            
            # Überprüfe, ob das Objekt tatsächlich gespeichert wurde
            count_result = faq_collection.aggregate.over_all()
            obj_count = 0
            if hasattr(count_result, 'total_count'):
                obj_count = count_result.total_count
            logger.info(f"Anzahl der FAQ-Objekte nach dem Speichern: {obj_count}")
            
            return True
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
                client.close()
                logger.info("Temporärer Weaviate-Client für FAQ-Speicherung geschlossen.")
            except Exception as e:
                logger.error(f"Fehler beim Schließen des Clients: {str(e)}")
                pass

async def add_faq_management_button():
    """
    Fügt einen FAQ-Management-Button zur UI hinzu.
    """
    faq_button = cl.Action(
        name="show_faq_management",
        payload={"action": "show"},
        label="📚 FAQ-Verwaltung"
    )
    
    msg = cl.Message(content="")
    msg.actions = [faq_button]
    await msg.send()

@cl.action_callback("show_faq_management")
async def on_show_faq_management(action):
    """
    Callback für die Aktion 'FAQ-Verwaltung anzeigen'.
    """
    await action.remove()
    
    # Zeige FAQ-Management-Optionen an
    msg = cl.Message(content="📚 **FAQ-Verwaltung**\n\nVerwalten Sie die FAQ-Datenbank.")
    
    actions = [
        cl.Action(name="list_faqs", payload={}, label="📋 FAQs anzeigen"),
        cl.Action(name="search_faqs", payload={}, label="🔍 FAQs durchsuchen"),
        cl.Action(name="debug_faq_db", payload={}, label="🛠️ FAQ-Datenbank prüfen"),
        cl.Action(name="create_test_faq", payload={}, label="🧪 Test-FAQ erstellen")
    ]
    
    msg.actions = actions
    await msg.send()

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
        logger.info(f"Verfügbare Collections: {collection_names}")
        
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

@cl.action_callback("debug_faq_db")
async def on_debug_faq_db(action):
    """
    Callback für die Aktion 'FAQ-Datenbank prüfen'.
    """
    await action.remove()
    
    # Prüfe die Weaviate-Datenbank direkt
    result = await debug_weaviate_database()
    
    # Zeige das Ergebnis an
    await cl.Message(content=f"## 🛠️ Weaviate-Datenbankprüfung\n\n```json\n{result}\n```").send()

async def debug_weaviate_database() -> str:
    """
    Prüft die Weaviate-Datenbank direkt und gibt Informationen zurück.
    
    Returns:
        str: JSON-String mit Informationen über die Datenbank
    """
    import json
    
    client = None
    result = {
        "collections": [],
        "faq_collection": {
            "exists": False,
            "properties": [],
            "count": 0,
            "objects": []
        },
        "error": None
    }
    
    try:
        # Erstelle einen temporären Weaviate-Client
        client = create_weaviate_client()
        logger.info("Temporärer Weaviate-Client für Debugging erstellt.")
        
        # Stelle sicher, dass der Client verbunden ist
        if not ensure_weaviate_connection(client):
            result["error"] = "Keine Verbindung zu Weaviate möglich."
            return json.dumps(result, indent=2)
        
        # Hole alle Collections
        collection_names = client.collections.list_all(simple=True)
        result["collections"] = collection_names
        
        # Prüfe, ob die FAQ-Collection existiert
        if "FAQ" in collection_names:
            result["faq_collection"]["exists"] = True
            
            # Hole die FAQ-Collection
            faq_collection = client.collections.get("FAQ")
            
            # Hole das Schema
            schema = faq_collection.config.get()
            if schema and "properties" in schema:
                result["faq_collection"]["properties"] = [prop["name"] for prop in schema["properties"]]
            
            # Zähle die Objekte
            try:
                count_result = faq_collection.aggregate.over_all()
                if hasattr(count_result, 'total_count'):
                    result["faq_collection"]["count"] = count_result.total_count
            except Exception as e:
                result["faq_collection"]["count_error"] = str(e)
            
            # Hole alle Objekte
            try:
                response = faq_collection.query.fetch_objects(limit=10)
                if hasattr(response, 'objects') and response.objects:
                    for obj in response.objects:
                        if hasattr(obj, 'properties'):
                            result["faq_collection"]["objects"].append(obj.properties)
                        else:
                            result["faq_collection"]["objects"].append({"error": "Objekt hat keine properties"})
            except Exception as e:
                result["faq_collection"]["fetch_error"] = str(e)
            
            # Versuche, ein Testobjekt zu erstellen
            try:
                test_object = {
                    "question": "DEBUG: Ist dies ein Test?",
                    "answer": "Ja, dies ist ein Testobjekt zur Diagnose der FAQ-Datenbank.",
                    "date": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "approved": True
                }
                
                insert_result = faq_collection.data.insert(test_object)
                result["faq_collection"]["test_insert"] = "Erfolgreich"
                result["faq_collection"]["test_insert_result"] = str(insert_result)
            except Exception as e:
                result["faq_collection"]["test_insert_error"] = str(e)
        
        return json.dumps(result, indent=2)
    except Exception as e:
        result["error"] = str(e)
        return json.dumps(result, indent=2)
    finally:
        # Schließe den Client
        if client:
            try:
                client.close()
                logger.info("Temporärer Weaviate-Client für Debugging geschlossen.")
            except Exception as e:
                logger.error(f"Fehler beim Schließen des Clients: {str(e)}") 

@cl.action_callback("create_test_faq")
async def on_create_test_faq(action):
    """
    Callback für die Aktion 'Test-FAQ erstellen'.
    """
    await action.remove()
    
    # Erstelle ein Test-FAQ
    success = await create_test_faq()
    
    if success:
        await cl.Message(content="✅ Test-FAQ wurde erfolgreich erstellt. Versuchen Sie jetzt, die FAQs anzuzeigen.").send()
    else:
        await cl.Message(content="⚠️ Fehler beim Erstellen des Test-FAQs.").send()

async def create_test_faq() -> bool:
    """
    Erstellt ein Test-FAQ in der Datenbank.
    
    Returns:
        bool: True bei erfolgreichem Erstellen, False sonst
    """
    # Erstelle ein Test-FAQ mit einer eindeutigen Frage
    import time
    timestamp = int(time.time())
    
    question = f"Test-Frage {timestamp}: Wie funktioniert das FAQ-System?"
    answer = f"Dies ist eine Test-Antwort {timestamp}. Das FAQ-System speichert Fragen und Antworten in der Weaviate-Datenbank."
    
    return await save_faq_to_database(question, answer)

async def search_faq_database(query: str, similarity_threshold: float = 0.7, limit: int = 3) -> list:
    """
    Sucht in der FAQ-Datenbank nach ähnlichen Fragen.
    
    Args:
        query: Die Suchanfrage
        similarity_threshold: Schwellenwert für die Ähnlichkeit (0-1)
        limit: Maximale Anzahl der Ergebnisse
        
    Returns:
        list: Liste der gefundenen FAQs, sortiert nach Ähnlichkeit
    """
    client = None
    try:
        # Erstelle einen temporären Weaviate-Client
        client = create_weaviate_client()
        logger.info(f"Temporärer Weaviate-Client für FAQ-Suche erstellt. Anfrage: {query[:50]}...")
        
        # Stelle sicher, dass der Client verbunden ist
        if not ensure_weaviate_connection(client):
            logger.error("Keine Verbindung zu Weaviate möglich.")
            return []
        
        # Prüfe, ob die FAQ-Collection existiert
        collection_names = client.collections.list_all(simple=True)
        logger.info(f"Verfügbare Collections: {collection_names}")
        
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
        
        # Führe eine semantische Suche durch
        logger.info(f"Führe semantische Suche nach '{query[:50]}...' durch")
        try:
            # Verwende near_text für die semantische Suche
            response = faq_collection.query.near_text(
                query=query,
                limit=limit
            )
            
            # Extrahiere die Objekte und ihre Ähnlichkeitswerte
            results = []
            if hasattr(response, 'objects') and response.objects:
                logger.info(f"Anzahl der gefundenen FAQ-Objekte: {len(response.objects)}")
                
                for obj in response.objects:
                    if hasattr(obj, 'properties') and hasattr(obj, 'metadata'):
                        # Extrahiere Ähnlichkeitswert
                        similarity = obj.metadata.certainty if hasattr(obj.metadata, 'certainty') else 0
                        
                        # Prüfe, ob die Ähnlichkeit über dem Schwellenwert liegt
                        if similarity >= similarity_threshold:
                            result = obj.properties
                            result['similarity'] = similarity
                            results.append(result)
                            logger.info(f"FAQ gefunden: {result.get('question', '')[:30]}... (Ähnlichkeit: {similarity:.2f})")
                
                if results:
                    # Sortiere nach Ähnlichkeit (absteigend)
                    results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
                    return results
                else:
                    logger.info(f"Keine FAQ-Objekte mit Ähnlichkeit >= {similarity_threshold} gefunden.")
            else:
                logger.warning("Keine FAQ-Objekte in der Antwort gefunden.")
            
            return []
        except Exception as e:
            logger.error(f"Fehler bei der semantischen Suche: {str(e)}")
            return []
    except Exception as e:
        logger.error(f"Fehler beim Durchsuchen der FAQ-Datenbank: {str(e)}", exc_info=True)
        return []
    finally:
        # Schließe den Client
        if client:
            try:
                client.close()
                logger.info("Temporärer Weaviate-Client für FAQ-Suche geschlossen.")
            except Exception as e:
                logger.error(f"Fehler beim Schließen des Clients: {str(e)}")
                pass 