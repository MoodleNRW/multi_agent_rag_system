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
    connection_params = ConnectionParams.from_url(
        url=WEAVIATE_URL,
        grpc_port=WEAVIATE_GRPC_PORT
    )
    
    client = weaviate.WeaviateClient(
        connection_params=connection_params,
        additional_headers={"X-OpenAI-Api-Key": API_KEY}
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
        
        for class_name in ["Content_chunk", "Content_summary", "Quote", "FAQ"]:
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
                    
                    # Nur für Content_chunk und Content_summary prüfen wir auf Mindestanzahl
                    if class_name in ["Content_chunk", "Content_summary"] and obj_count < 5:  # Mindestens 5 Dokumente sollten vorhanden sein
                        result["has_sufficient_data"] = False
                        logger.warning(f"Weaviate-Klasse '{class_name}' enthält nur {obj_count} Objekte. Möglicherweise unzureichende Daten.")
                except Exception as e:
                    logger.error(f"Fehler beim Zählen der Objekte in '{class_name}': {str(e)}")
                    result["has_sufficient_data"] = False
                    result["details"][class_name] = 0
            else:
                # Nur für Content_chunk und Content_summary setzen wir classes_exist auf False
                if class_name in ["Content_chunk", "Content_summary"]:
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
        #logger.info(f"Gefundene Collections: {existing_collections}")
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
    
    #logger.info(f"Gefundene Collections: {collection_names}")
    
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
    
    # Schema für Quote
    if "Quote" not in collection_names:
        logger.info("Erstelle Quote-Schema...")
        quote_properties = [
            wvc.config.Property(name="url", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="source", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="date", data_type=wvc.config.DataType.DATE),
            wvc.config.Property(name="title", data_type=wvc.config.DataType.TEXT)
        ]
        
        try:
            quote_config = client.collections.create(
                name="Quote",
                properties=quote_properties,
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_openai()
            )
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Quote-Schemas: {e}")
            return False
    
    # Schema für FAQ
    if "FAQ" not in collection_names:
        logger.info("Erstelle FAQ-Schema...")
        faq_properties = [
            wvc.config.Property(name="question", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="answer", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="date", data_type=wvc.config.DataType.DATE),
            wvc.config.Property(name="approved", data_type=wvc.config.DataType.BOOL)
        ]
        
        try:
            logger.info("Erstelle FAQ-Collection mit den Eigenschaften: question, answer, date, approved")
            faq_config = client.collections.create(
                name="FAQ",
                properties=faq_properties,
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_openai()
            )
            logger.info("FAQ-Collection erfolgreich erstellt.")
            
            # Überprüfe, ob die Collection erstellt wurde
            try:
                collection_names = client.collections.list_all(simple=True)
                if "FAQ" in collection_names:
                    logger.info("FAQ-Collection wurde erfolgreich erstellt und ist in der Liste der Collections vorhanden.")
                    
                    # Überprüfe die Vektorisierer-Konfiguration
                    faq_collection = client.collections.get("FAQ")
                    vectorizer_info = None
                    
                    # Versuche verschiedene Möglichkeiten, die Vektorisierer-Konfiguration zu erhalten
                    try:
                        # Option 1: Über Konfigurationsattribute
                        if hasattr(faq_collection.config, 'vectorizer_config'):
                            vectorizer_info = faq_collection.config.vectorizer_config.vectorizer
                        # Option 2: Über vectorizers
                        elif hasattr(faq_collection.config, 'vectorizers'):
                            vectorizers = faq_collection.config.vectorizers
                            if vectorizers and len(vectorizers) > 0:
                                vectorizer_info = vectorizers[0]
                        # Option 3: Direktes Attribut (ältere Versionen)
                        elif hasattr(faq_collection.config, 'vectorizer'):
                            vectorizer_info = faq_collection.config.vectorizer
                            
                        logger.info(f"FAQ-Collection Vektorisierer: {vectorizer_info}")
                    except Exception as e:
                        logger.warning(f"Konnte Vektorisierer-Konfiguration nicht ermitteln: {str(e)}")
                        vectorizer_info = None
                    
                    if vectorizer_info != "text2vec-openai":
                        logger.error(f"FAQ-Collection hat falschen Vektorisierer: {vectorizer_info}. Sollte 'text2vec-openai' sein.")
                        # Lösche die Collection und erstelle sie neu
                        client.collections.delete("FAQ")
                        logger.info("FAQ-Collection gelöscht, um sie mit korrektem Vektorisierer neu zu erstellen.")
                        
                        # Erstelle die Collection neu
                        faq_config = client.collections.create(
                            name="FAQ",
                            properties=faq_properties,
                            vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_openai()
                        )
                        logger.info("FAQ-Collection mit korrektem Vektorisierer neu erstellt.")
                else:
                    logger.error("FAQ-Collection wurde erstellt, ist aber nicht in der Liste der Collections vorhanden.")
            except Exception as e:
                logger.error(f"Fehler beim Überprüfen der erstellten FAQ-Collection: {e}")
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des FAQ-Schemas: {e}")
            return False
    
    logger.info("Schema-Prüfung abgeschlossen.")
    return True 