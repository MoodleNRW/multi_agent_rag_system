from langchain_openai import OpenAIEmbeddings
from langchain_weaviate.vectorstores import WeaviateVectorStore
import weaviate
import logging
from typing import Tuple, Optional, Dict
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
# Globales Dictionary für Retriever
global_retrievers: Optional[Dict[str, object]] = None

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
        if not self._client.is_connected():
            logger.info("Client in VectorStore ist nicht verbunden. Verbinde...")
            self._client.connect()
            
        return super()._select_relevance_score_fn()
    
    def similarity_search_with_score(self, *args, **kwargs):
        """Überschreibe diese Methode, um sie mit der Verbindungsprüfung zu erweitern."""
        # Stelle sicher, dass der Client verbunden ist, bevor wir ihn verwenden
        if not self._client.is_connected():
            logger.info("Client in VectorStore ist nicht verbunden. Verbinde...")
            self._client.connect()
            
        return super().similarity_search_with_score(*args, **kwargs)
    
    def similarity_search(self, *args, **kwargs):
        """Überschreibe diese Methode, um sie mit der Verbindungsprüfung zu erweitern."""
        # Stelle sicher, dass der Client verbunden ist, bevor wir ihn verwenden
        if not self._client.is_connected():
            logger.info("Client in VectorStore ist nicht verbunden. Verbinde...")
            self._client.connect()
            
        return super().similarity_search(*args, **kwargs)

# Function to actually create retrievers (can be called by ensure_global_retrievers)
def _create_and_get_retrievers() -> Dict[str, Optional[object]]:
    """
    Internal function to create and return a dictionary of retrievers.
    Handles potential None values.
    """
    retrievers_dict = {}
    try:
        chunks, summaries, quotes, faqs = create_retrievers()
        retrievers_dict["chunks"] = chunks
        retrievers_dict["summaries"] = summaries
        retrievers_dict["quotes"] = quotes
        retrievers_dict["faq"] = faqs
        logger.info("Global retrievers created and cached.")
    except Exception as e:
        logger.error(f"Error during retriever creation in _create_and_get_retrievers: {e}")
        # Initialize with None if creation fails
        retrievers_dict = {"chunks": None, "summaries": None, "quotes": None, "faq": None}
    return retrievers_dict

def ensure_global_retrievers() -> Dict[str, Optional[object]]:
    """
    Ensures that the global retrievers dictionary exists and is populated.
    Returns the dictionary of retrievers.
    """
    global global_retrievers
    if global_retrievers is None:
        logger.info("Global retrievers not cached. Creating...")
        global_retrievers = _create_and_get_retrievers()
    # Optionally, add a check here to recreate if they are somehow invalid, but start simple
    return global_retrievers

def create_retrievers() -> Tuple[Optional[object], Optional[object], Optional[object], Optional[object]]:
    """
    Erstellt Retriever für verschiedene Inhaltstypen (Chunks, Summaries, Quotes, FAQs).
    
    Returns:
        Tuple aus vier Retrievern (chunks, summaries, quotes, faqs) oder None für fehlende Retriever
    """
    try:
        # Stelle sicher, dass der globale Client existiert und verbunden ist
        client = ensure_global_client()
        if client is None:
            logger.error("Konnte keinen funktionierenden Weaviate-Client erstellen")
            return None, None, None, None
        
        # Erstelle Retriever mit dem globalen Client
        return create_retrievers_with_client(client)
    except Exception as e:
        logger.error(f"Fehler beim Erstellen der Retriever: {str(e)}")
        return None, None, None, None

def create_retrievers_with_client(client) -> Tuple[Optional[object], Optional[object], Optional[object], Optional[object]]:
    """
    Erstellt Retriever für verschiedene Inhaltstypen mit einem bestimmten Weaviate-Client.
    
    Args:
        client: Der Weaviate-Client, der für die Retriever verwendet werden soll.
        
    Returns:
        Tuple aus vier Retrievern (chunks, summaries, quotes, faqs) oder None für fehlende Retriever
    """
    try:
        # Überprüfe, ob Klassen existieren und Daten enthalten
        data_status = weaviate_client.check_weaviate_data(client)
        #logger.info(f"Verfügbare Daten in Weaviate: {data_status}")
        
        if not data_status["classes_exist"]:
            logger.error("Weaviate-Klassen existieren nicht. Führen Sie zuerst den Crawler aus.")
            return None, None, None, None
        
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
        
        # Für Zitate verwenden wir die Quote-Collection
        quotes_vector_store = None
        try:
            # Prüfe, ob die Quote-Collection existiert und Daten enthält
            if "Quote" in data_status["details"] and data_status["details"]["Quote"] > 0:
                quotes_vector_store = KeepAliveWeaviateVectorStore(
                    client=client, 
                    index_name="Quote", 
                    embedding=embeddings,
                    text_key="content"
                )
                logger.info(f"Quote-Vector-Store mit {data_status['details']['Quote']} Objekten erstellt.")
            else:
                # Fallback: Verwende Content_chunk, wenn keine Quote-Collection verfügbar ist
                logger.warning("Keine Quote-Collection gefunden oder leer. Verwende Content_chunk als Fallback.")
                quotes_vector_store = chunks_vector_store
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Quote-Vector-Store: {str(e)}")
            # Fallback: Verwende Content_chunk
            quotes_vector_store = chunks_vector_store
            
        # Für FAQs verwenden wir die FAQ-Collection
        faq_vector_store = None
        try:
            # Prüfe, ob die FAQ-Collection existiert
            if "FAQ" in data_status["details"]:
                faq_vector_store = KeepAliveWeaviateVectorStore(
                    client=client, 
                    index_name="FAQ", 
                    embedding=embeddings,
                    text_key="question"  # Wir suchen primär nach ähnlichen Fragen
                )
                logger.info(f"FAQ-Vector-Store mit {data_status['details'].get('FAQ', 0)} Objekten erstellt.")
            else:
                logger.warning("Keine FAQ-Collection gefunden. FAQ-Retriever wird nicht erstellt.")
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des FAQ-Vector-Store: {str(e)}")

        # Retriever mit angepassten Suchparametern erstellen
        chunks_retriever = chunks_vector_store.as_retriever(search_kwargs={"k": 4})     
        summaries_retriever = summaries_vector_store.as_retriever(search_kwargs={"k": 4})
        
        # Stelle sicher, dass quotes_vector_store nicht None ist
        if quotes_vector_store is None:
            quotes_vector_store = chunks_vector_store
            logger.warning("Verwende Content_chunk als Fallback für Quote-Retriever.")
            
        quotes_retriever = quotes_vector_store.as_retriever(search_kwargs={"k": 10})
        
        # FAQ-Retriever erstellen, falls verfügbar
        faq_retriever = None
        if faq_vector_store is not None:
            faq_retriever = faq_vector_store.as_retriever(search_kwargs={"k": 3})
            logger.info("FAQ-Retriever erfolgreich erstellt.")
        
        logger.info("Retriever erfolgreich erstellt.")
        return chunks_retriever, summaries_retriever, quotes_retriever, faq_retriever

    except weaviate.exceptions.WeaviateBaseError as e:
        logger.error(f"Weaviate-Fehler beim Erstellen der Retriever: {str(e)}")
        return None, None, None, None
    except Exception as e:
        logger.error(f"Allgemeiner Fehler beim Erstellen der Retriever: {str(e)}")
        return None, None, None, None
