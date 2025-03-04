from langchain_openai import OpenAIEmbeddings
from langchain_weaviate.vectorstores import WeaviateVectorStore
import weaviate
import os
import dotenv
import logging
from typing import Tuple, Optional, Dict, Any

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Lade Umgebungsvariablen
dotenv.load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')

def check_weaviate_data(client: weaviate.Client) -> Dict[str, Any]:
    """
    Überprüft, ob genügend Daten in den Weaviate-Klassen vorhanden sind.
    
    Args:
        client: Weaviate-Client-Instanz
        
    Returns:
        Dictionary mit Klassennamen und Anzahl der Objekte
    """
    result = {}
    try:
        for class_name in ["Content_chunk", "Content_summary"]:
            if client.schema.exists(class_name):
                # Abfrage, um die Anzahl der Objekte in der Klasse zu zählen
                count_result = client.query.aggregate(class_name).with_meta_count().do()
                count = count_result.get("data", {}).get("Aggregate", {}).get(class_name, [{}])[0].get("meta", {}).get("count", 0)
                result[class_name] = count
                
                if count < 5:  # Mindestens 5 Dokumente sollten vorhanden sein
                    logger.warning(f"Weaviate-Klasse '{class_name}' enthält nur {count} Objekte. Möglicherweise unzureichende Daten.")
            else:
                result[class_name] = 0
        return result
    except Exception as e:
        logger.error(f"Fehler beim Überprüfen der Weaviate-Daten: {str(e)}")
        return {}

def create_retrievers() -> Tuple[Optional[object], Optional[object], Optional[object]]:
    """
    Erstellt und gibt Retriever-Objekte zurück, die auf den Weaviate-Vektorspeichern basieren.
    
    Returns:
        Tuple mit drei Retrievern: chunks_retriever, summaries_retriever, quotes_retriever
        Bei Fehlern werden None-Werte zurückgegeben
        
    Raises:
        Exception: Wenn nicht genügend Daten in der Datenbank vorhanden sind
    """
    try:
        # OpenAI Embeddings initialisieren
        embeddings = OpenAIEmbeddings()
        
        # Verbindung zur Weaviate-Instanz herstellen
        client = weaviate.Client(
            url="http://localhost:8090",
            additional_headers={
                "X-OpenAI-Api-Key": API_KEY
            }
        )
        
        # Überprüfen, ob Weaviate erreichbar ist
        if not client.is_ready():
            logger.error("Weaviate-Client ist nicht bereit. Überprüfen Sie, ob der Weaviate-Server läuft.")
            return None, None, None
            
        # Überprüfen, ob die erforderlichen Klassen existieren
        required_classes = ["Content_chunk", "Content_summary"]
        for class_name in required_classes:
            if not client.schema.exists(class_name):
                logger.error(f"Weaviate-Klasse '{class_name}' existiert nicht. Führen Sie zuerst den Crawler aus.")
                return None, None, None
        
        # Überprüfen, ob genügend Daten vorhanden sind
        data_counts = check_weaviate_data(client)
        logger.info(f"Verfügbare Daten in Weaviate: {data_counts}")
        
        # Überprüfen, ob mindestens 5 Dokumente in jeder Klasse vorhanden sind
        min_documents = 5
        for class_name, count in data_counts.items():
            if count < min_documents:
                error_message = f"Insufficient data in Weaviate class '{class_name}': {count}/{min_documents} documents. Please run the crawler first."
                logger.error(error_message)
                raise Exception(error_message)

        # Vector Stores für die verschiedenen Datentypen erstellen
        chunks_vector_store = WeaviateVectorStore(
            client=client, 
            index_name="Content_chunk", 
            embedding=embeddings,
            text_key="content_chunk"
        )

        summaries_vector_store = WeaviateVectorStore(
            client=client, 
            index_name="Content_summary", 
            embedding=embeddings,
            text_key="content_summary"
        )
        
        # Für Zitate verwenden wir auch Content_chunk, filtern aber nach bestimmten Eigenschaften
        # oder passen die Abfrageparameter an
        quotes_vector_store = WeaviateVectorStore(
            client=client, 
            index_name="Content_chunk", 
            embedding=embeddings,
            text_key="content_chunk"
        )

        # Retriever mit angepassten Suchparametern erstellen
        chunks_retriever = chunks_vector_store.as_retriever(search_kwargs={"k": 4})     
        summaries_retriever = summaries_vector_store.as_retriever(search_kwargs={"k": 4})
        quotes_retriever = quotes_vector_store.as_retriever(search_kwargs={"k": 10})
        
        logger.info("Retriever erfolgreich erstellt.")
        return chunks_retriever, summaries_retriever, quotes_retriever

    except weaviate.exceptions.WeaviateBaseError as e:
        logger.error(f"Weaviate-Fehler beim Erstellen der Retriever: {str(e)}")
        return None, None, None
    except Exception as e:
        logger.error(f"Allgemeiner Fehler beim Erstellen der Retriever: {str(e)}")
        return None, None, None
