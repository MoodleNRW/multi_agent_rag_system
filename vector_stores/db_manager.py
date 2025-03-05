import chainlit as cl
import logging
import subprocess
import sys
from vector_stores.weaviate_client import create_weaviate_client, ensure_weaviate_connection, check_weaviate_data
from vector_stores.retriever import create_retrievers, ensure_global_client

# Konfiguriere Logger
logger = logging.getLogger(__name__)

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
    finally:
        if temp_client:
            try:
                temp_client.close()
            except:
                pass

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
        import pandas as pd
        import plotly.express as px
        
        df = pd.DataFrame(data)
        fig = px.bar(df, x="Klasse", y="Anzahl", title="Objekte pro Klasse in Weaviate")
        
        # Plot anzeigen
        await cl.Message(content="### Datenvisualisierung").send()
        await cl.Message(content=fig).send()
        
    except Exception as e:
        logger.error(f"Fehler bei der Datenvisualisierung: {str(e)}")
        await cl.Message(content=f"⚠️ Fehler bei der Datenvisualisierung: {str(e)}").send()
    finally:
        if temp_client:
            try:
                temp_client.close()
            except:
                pass

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
    finally:
        if temp_client:
            try:
                temp_client.close()
            except:
                pass

@cl.action_callback("db_clear_all")
async def on_db_clear_all(action):
    """Löscht alle Daten aus der Datenbank."""
    await action.remove()
    
    # Verwende den globalen Client anstelle eines temporären Clients
    try:
        client = ensure_global_client()  # Verwende den globalen Client
        
        # Stelle sicher, dass der globale Client existiert und verbunden ist
        if client is None:
            await cl.Message(content="⚠️ Fehler bei der Verbindung mit der Weaviate-Datenbank.").send()
            return
        
        # Prüfe explizit die Verbindung
        if not client.is_connected():
            client.connect()  # Verbinde erneut, wenn nicht verbunden
        
        # Klassen abrufen
        collection_names = client.collections.list_all(simple=True)
        
        if not collection_names:
            await cl.Message(content="Keine Klassen zum Löschen gefunden.").send()
            return
        
        # Lösche alle Klassen
        try:
            # Lösche alle Klassen auf einmal
            client.collections.delete_all()
            logger.info("Alle Klassen wurden gelöscht")
            await cl.Message(content="✅ Alle Klassen und deren Objekte wurden erfolgreich gelöscht.").send()
        except Exception as delete_error:
            logger.error(f"Fehler beim Löschen aller Klassen: {str(delete_error)}")
            await cl.Message(content=f"⚠️ Fehler beim Löschen aller Klassen: {str(delete_error)}").send()
            
            # Versuche, jede Klasse einzeln zu löschen
            success_count = 0
            for class_name in collection_names:
                try:
                    # Prüfe, ob der Client noch verbunden ist, bevor wir fortfahren
                    if not client.is_connected():
                        client.connect()
                        
                    # Lösche die Klasse
                    client.collections.delete(class_name)
                    await cl.Message(content=f"✅ Klasse **{class_name}** wurde gelöscht.").send()
                    success_count += 1
                except Exception as e:
                    logger.error(f"Fehler beim Löschen der Klasse {class_name}: {str(e)}")
                    await cl.Message(content=f"⚠️ Fehler beim Löschen von {class_name}: {str(e)}").send()
        
        await cl.Message(content="Die Anwendung sollte neu gestartet werden, um die Änderungen zu übernehmen.").send()
        
        restart_msg = cl.Message(content="Anwendung muss neu gestartet werden, um die Änderungen zu übernehmen.")
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
    finally:
        if temp_client:
            try:
                temp_client.close()
            except:
                pass

@cl.action_callback("db_clear_class_confirm")
async def on_db_clear_class_confirm(action):
    """Löscht alle Objekte einer bestimmten Klasse."""
    class_name = action.payload["class_name"]
    await action.remove()
    
    status_msg = cl.Message(content=f"⏳ Lösche alle Objekte aus **{class_name}**...")
    await status_msg.send()
    
    try:
        # Verwende den globalen Client anstelle eines temporären Clients
        client = ensure_global_client()
        if client is None:
            await cl.Message(content="⚠️ Fehler bei der Verbindung mit der Weaviate-Datenbank.").send()
            return
            
        # Prüfe explizit die Verbindung
        if not client.is_connected():
            client.connect()
        
        # Lösche die Klasse komplett und erstelle sie neu
        # Dies ist die effektivste Methode, um alle Objekte zu löschen
        try:
            # Lösche die Klasse
            client.collections.delete(class_name)
            logger.info(f"Klasse {class_name} wurde gelöscht")
        except Exception as delete_error:
            logger.error(f"Fehler beim Löschen der Klasse {class_name}: {str(delete_error)}")
            # Wenn die Klasse nicht existiert, ist das kein Problem
        
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
        client = ensure_global_client()
        if client:
            client.close()
        logger.info("Weaviate-Verbindung vor dem Neustart geschlossen.")
    except Exception as e:
        logger.error(f"Fehler beim Schließen der Weaviate-Verbindung: {str(e)}")
    
    # Starte die Anwendung neu (im Hintergrund)
    subprocess.Popen(["chainlit", "run", "app.py"])
    
    # Beende die aktuelle Instanz
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
    finally:
        if temp_client:
            try:
                temp_client.close()
            except:
                pass

async def reconnect_weaviate_if_needed():
    """Stellt sicher, dass der Weaviate-Client verbunden ist und stellt die Verbindung bei Bedarf wieder her."""
    try:
        client = ensure_global_client()
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