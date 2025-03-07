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
        
        # Stelle sicher, dass der Client verbunden ist
        if not ensure_weaviate_connection(client):
            logger.error("Keine Verbindung zu Weaviate möglich.")
            return False
        
        # Prüfe, ob die FAQ-Collection existiert
        collection_names = client.collections.list_all(simple=True)
        
        if "FAQ" not in collection_names:
            logger.error("FAQ-Collection existiert nicht.")
            return False
        
        # Hole die FAQ-Collection
        faq_collection = client.collections.get("FAQ")
        
        # Erstelle ein neues FAQ-Objekt
        faq_object = {
            "question": question,
            "answer": answer,
            "date": datetime.datetime.now().isoformat(),
            "approved": True  # Standardmäßig genehmigt, da vom Benutzer bestätigt
        }
        
        # Füge das Objekt zur Collection hinzu
        faq_collection.data.insert(faq_object)
        
        logger.info(f"FAQ erfolgreich gespeichert: {question[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Speichern der FAQ: {str(e)}")
        return False
    finally:
        # Schließe den Client
        if client:
            try:
                client.close()
            except:
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
        cl.Action(name="search_faqs", payload={}, label="🔍 FAQs durchsuchen")
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
        
        # Stelle sicher, dass der Client verbunden ist
        if not ensure_weaviate_connection(client):
            logger.error("Keine Verbindung zu Weaviate möglich.")
            return []
        
        # Prüfe, ob die FAQ-Collection existiert
        collection_names = client.collections.list_all(simple=True)
        
        if "FAQ" not in collection_names:
            logger.error("FAQ-Collection existiert nicht.")
            return []
        
        # Hole die FAQ-Collection
        faq_collection = client.collections.get("FAQ")
        
        # Hole alle FAQs
        response = faq_collection.query.fetch_objects(
            limit=limit,
            sort=[{"path": ["date"], "order": "desc"}]  # Sortiere nach Datum absteigend
        )
        
        # Extrahiere die Objekte
        faqs = []
        for obj in response.objects:
            properties = obj.properties
            faqs.append(properties)
        
        return faqs
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der FAQs: {str(e)}")
        return []
    finally:
        # Schließe den Client
        if client:
            try:
                client.close()
            except:
                pass 