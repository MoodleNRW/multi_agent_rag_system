import weaviate
import weaviate.classes as wvc
from weaviate.connect import ConnectionParams
import os
import dotenv
import logging
from typing import Dict, Any, Optional

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Lade Umgebungsvariablen
dotenv.load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')

# Konfiguration
WEAVIATE_URL = "http://localhost:8090"
WEAVIATE_GRPC_PORT = 50051

def create_weaviate_client() -> weaviate.WeaviateClient:
    """
    Erstellt einen neuen Weaviate-Client mit den konfigurierten Verbindungsparametern.
    
    Returns:
        weaviate.WeaviateClient: Der initialisierte Weaviate-Client
    """
    # Extrahiere Host und Port aus URL
    url_parts = WEAVIATE_URL.replace("http://", "").replace("https://", "").split(":")
    host = url_parts[0]
    http_port = int(url_parts[1]) if len(url_parts) > 1 else 80
    
    # Erstelle ConnectionParams mit der korrekten Struktur für Weaviate Client v4.9.6
    connection_params = ConnectionParams(
        http={
            "host": host,
            "port": http_port,
            "secure": WEAVIATE_URL.startswith("https")
        },
        grpc={
            "host": host,
            "port": WEAVIATE_GRPC_PORT,
            "secure": WEAVIATE_URL.startswith("https")
        }
    )
    
    # Füge OpenAI-API-Key als zusätzlichen Header hinzu, wenn verfügbar
    additional_headers = {}
    if API_KEY:
        additional_headers["X-OpenAI-Api-Key"] = API_KEY
    
    client = weaviate.WeaviateClient(
        connection_params=connection_params,
        additional_headers=additional_headers
    )
    
    return client

def ensure_weaviate_connection(client: weaviate.WeaviateClient) -> bool:
    """
    Stellt sicher, dass der Weaviate-Client verbunden ist.
    
    Args:
        client: Der Weaviate-Client
        
    Returns:
        bool: True, wenn die Verbindung hergestellt ist, sonst False
    """
    try:
        if not client.is_connected():
            client.connect()
        return True
    except Exception as e:
        logger.error(f"Fehler bei der Verbindung mit Weaviate: {str(e)}")
        try:
            client.close()
        except:
            pass
        return False

def check_weaviate_data(client: weaviate.WeaviateClient) -> Dict[str, Any]:
    """
    Überprüft, ob genügend Daten in den Weaviate-Klassen vorhanden sind.
    
    Args:
        client: Weaviate-Client-Instanz
        
    Returns:
        Dictionary mit Klassennamen und Status-Informationen
    """
    result = {
        "classes_exist": True,
        "has_sufficient_data": True,
        "details": {}
    }
    try:
        # Sicherstellen, dass der Client verbunden ist
        if not client.is_connected():
            client.connect()
        
        # Hole alle Sammlungen (Collections) mit der neuen v4 API
        collection_names = []
        collections = client.collections.list_all(simple=True)
        collection_names = collections
        
        for class_name in ["Content_chunk", "Content_summary"]:
            if class_name in collection_names:
                try:
                    # Hole die Sammlung und zähle die Objekte
                    collection = client.collections.get(class_name)
                    count_result = collection.aggregate.over_all()
                    obj_count = 0
                    if hasattr(count_result, 'total_count'):
                        obj_count = count_result.total_count
                    else:
                        # Versuche alternative Methoden, die Anzahl zu ermitteln
                        try:
                            # Methode 1: Versuche, alle Objekte zu zählen
                            all_objects = collection.query.fetch_objects(limit=1000)
                            obj_count = len(all_objects.objects)
                        except Exception as e2:
                            logger.error(f"Alternative Zählmethode fehlgeschlagen: {str(e2)}")
                            obj_count = 0
                    
                    result["details"][class_name] = obj_count
                    
                    if obj_count < 5:  # Mindestens 5 Dokumente sollten vorhanden sein
                        result["has_sufficient_data"] = False
                        logger.warning(f"Weaviate-Klasse '{class_name}' enthält nur {obj_count} Objekte. Möglicherweise unzureichende Daten.")
                except Exception as e:
                    logger.error(f"Fehler beim Zählen der Objekte in '{class_name}': {str(e)}")
                    result["has_sufficient_data"] = False
                    result["details"][class_name] = 0
            else:
                result["classes_exist"] = False
                result["has_sufficient_data"] = False
                result["details"][class_name] = 0
                logger.warning(f"Weaviate-Klasse '{class_name}' existiert nicht. Führen Sie zuerst den Crawler aus.")
        return result
    except Exception as e:
        logger.error(f"Fehler beim Überprüfen der Weaviate-Daten: {str(e)}")
        return {
            "classes_exist": False,
            "has_sufficient_data": False,
            "details": {"error": str(e)}
        }

def create_weaviate_schema(client: weaviate.WeaviateClient) -> bool:
    """
    Erstellt die erforderlichen Schemas in Weaviate, falls sie noch nicht existieren.
    
    Args:
        client: Der Weaviate-Client
        
    Returns:
        bool: True, wenn die Schemas erstellt wurden, sonst False
    """
    logger.info("Prüfe und erstelle Schemas...")
    
    # Stelle sicher, dass die Verbindung hergestellt ist
    if not ensure_weaviate_connection(client):
        logger.error("Keine Verbindung zu Weaviate möglich.")
        return False
    
    # Initialisiere collection_names
    collection_names = []
    
    try:
        # Überprüfen, ob die Schemas bereits existieren
        logger.info("Überprüfe bestehende Collections...")
        existing_collections = client.collections.list_all(simple=True)
        collection_names = existing_collections
        logger.info(f"Gefundene Collections: {existing_collections}")
    except Exception as e:
        logger.error(f"Fehler beim Auflisten der Collections: {e}")
        # Bei Fehler versuchen wir, jede Collection direkt abzufragen
        collection_names = []
        for name in ["Content", "Content_chunk", "Content_summary"]:
            try:
                client.collections.get(name)
                collection_names.append(name)
                logger.info(f"Collection {name} existiert bereits.")
            except:
                logger.info(f"Collection {name} existiert noch nicht.")
    
    logger.info(f"Gefundene Collections: {collection_names}")
    
    # Schema für Content
    if "Content" not in collection_names:
        logger.info("Erstelle Content-Schema...")
        content_properties = [
            wvc.config.Property(name="url", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="date", data_type=wvc.config.DataType.DATE),
            wvc.config.Property(name="title", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="chapter", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="section", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="last_updated", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="importance_score", data_type=wvc.config.DataType.NUMBER)
        ]
        
        try:
            content_config = client.collections.create(
                name="Content",
                properties=content_properties,
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_openai()
            )
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Content-Schemas: {e}")
            return False
    
    # Schema für Content_chunk
    if "Content_chunk" not in collection_names:
        logger.info("Erstelle Content_chunk-Schema...")
        chunk_properties = [
            wvc.config.Property(name="url", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="content_chunk", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="chunk_nr", data_type=wvc.config.DataType.NUMBER),
            wvc.config.Property(name="chunk_type", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="date", data_type=wvc.config.DataType.DATE)
        ]
        
        try:
            chunk_config = client.collections.create(
                name="Content_chunk",
                properties=chunk_properties,
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_openai()
            )
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Content_chunk-Schemas: {e}")
            return False
    
    # Schema für Content_summary
    if "Content_summary" not in collection_names:
        logger.info("Erstelle Content_summary-Schema...")
        summary_properties = [
            wvc.config.Property(name="url", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="content_summary", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="date", data_type=wvc.config.DataType.DATE)
        ]
        
        try:
            summary_config = client.collections.create(
                name="Content_summary",
                properties=summary_properties,
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_openai()
            )
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Content_summary-Schemas: {e}")
            return False
    
    logger.info("Schema-Prüfung abgeschlossen.")
    return True 