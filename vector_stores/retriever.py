from langchain_openai import OpenAIEmbeddings
from langchain_weaviate.vectorstores import WeaviateVectorStore
import weaviate
import logging
from typing import Tuple, Optional
import os
import dotenv
from . import weaviate_client

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Lade Umgebungsvariablen
dotenv.load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')

# Globaler Client für die gesamte Anwendung
global_client = None

def ensure_global_client():
    """
    Stellt sicher, dass der globale Weaviate-Client existiert und verbunden ist.
    """
    global global_client
    
    try:
        if global_client is None:
            logger.info("Erstelle einen neuen globalen Weaviate-Client")
            global_client = weaviate_client.create_weaviate_client()
        
        if not global_client.is_connected():
            logger.info("Der globale WeaviateClient ist nicht verbunden. Verbinde...")
            global_client.connect()
            
        return global_client
    except Exception as e:
        logger.error(f"Fehler beim Verbinden des globalen Weaviate-Clients: {str(e)}")
        # Bei einem kritischen Fehler erstellen wir einen neuen Client
        try:
            global_client = weaviate_client.create_weaviate_client()
            global_client.connect()
            return global_client
        except Exception as e2:
            logger.error(f"Kritischer Fehler: Konnte keinen neuen Client erstellen: {str(e2)}")
            return None

class KeepAliveWeaviateVectorStore(WeaviateVectorStore):
    """
    Eine angepasste Version der WeaviateVectorStore, die sicherstellt, 
    dass der Client verbunden bleibt.
    """
    
    def _select_relevance_score_fn(self):
        """Überschreibe diese Methode, um sie mit der Verbindungsprüfung zu erweitern."""
        # Stelle sicher, dass der Client verbunden ist, bevor wir ihn verwenden
        if not self.client.is_connected():
            logger.info("Client in VectorStore ist nicht verbunden. Verbinde...")
            self.client.connect()
            
        return super()._select_relevance_score_fn()
    
    def similarity_search_with_score(self, *args, **kwargs):
        """Überschreibe diese Methode, um sie mit der Verbindungsprüfung zu erweitern."""
        # Stelle sicher, dass der Client verbunden ist, bevor wir ihn verwenden
        if not self.client.is_connected():
            logger.info("Client in VectorStore ist nicht verbunden. Verbinde...")
            self.client.connect()
            
        return super().similarity_search_with_score(*args, **kwargs)
    
    def similarity_search(self, *args, **kwargs):
        """Überschreibe diese Methode, um sie mit der Verbindungsprüfung zu erweitern."""
        # Stelle sicher, dass der Client verbunden ist, bevor wir ihn verwenden
        if not self.client.is_connected():
            logger.info("Client in VectorStore ist nicht verbunden. Verbinde...")
            self.client.connect()
            
        return super().similarity_search(*args, **kwargs)

def create_retrievers() -> Tuple[Optional[object], Optional[object], Optional[object]]:
    """
    Erstellt Retriever für verschiedene Inhaltstypen (Chunks, Summaries, Quotes).
    
    Returns:
        Tuple aus drei Retrievern (chunks, summaries, quotes) oder None für fehlende Retriever
    """
    try:
        # Stelle sicher, dass der globale Client existiert und verbunden ist
        client = ensure_global_client()
        if client is None:
            logger.error("Konnte keinen funktionierenden Weaviate-Client erstellen")
            return None, None, None
        
        # Überprüfe, ob Klassen existieren und Daten enthalten
        data_status = weaviate_client.check_weaviate_data(client)
        logger.info(f"Verfügbare Daten in Weaviate: {data_status}")
        
        if not data_status["classes_exist"]:
            logger.error("Weaviate-Klassen existieren nicht. Führen Sie zuerst den Crawler aus.")
            return None, None, None
        
        if not data_status["has_sufficient_data"]:
            class_name = "Content_chunk"
            count = data_status["details"].get(class_name, 0)
            min_documents = 5
            error_message = f"Insufficient data in Weaviate class '{class_name}': {count}/{min_documents} documents. Please run the crawler first."
            logger.error(error_message)
            raise ValueError(error_message)

        # OpenAI Embeddings initialisieren
        embeddings = OpenAIEmbeddings()
        
        # Vector Stores für die verschiedenen Datentypen erstellen mit unserer angepassten Klasse
        chunks_vector_store = KeepAliveWeaviateVectorStore(
            client=client, 
            index_name="Content_chunk", 
            embedding=embeddings,
            text_key="content_chunk"
        )

        summaries_vector_store = KeepAliveWeaviateVectorStore(
            client=client, 
            index_name="Content_summary", 
            embedding=embeddings,
            text_key="content_summary"
        )
        
        # Für Zitate verwenden wir auch Content_chunk, filtern aber nach bestimmten Eigenschaften
        # oder passen die Abfrageparameter an
        quotes_vector_store = KeepAliveWeaviateVectorStore(
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
