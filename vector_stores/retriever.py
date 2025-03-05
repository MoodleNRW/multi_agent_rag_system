from typing import Tuple, Optional, List, Dict, Any
import logging
from langchain_weaviate.vectorstores import WeaviateVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from vector_stores.db_manager import WeaviateManager

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_global_client():
    """
    Stellt sicher, dass ein globaler Weaviate-Client existiert und gibt ihn zurück.
    Diese Funktion ist nur zur Kompatibilität mit bestehendem Code vorhanden.
    
    Returns:
        Der Weaviate-Client oder None, wenn keine Verbindung möglich ist.
    """
    manager = WeaviateManager()
    return manager.client

class KeepAliveWeaviateVectorStore(WeaviateVectorStore):
    """Eine erweiterte Version des WeaviateVectorStore mit Verbindungswiederherstellung."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.db_manager = WeaviateManager()
    
    def _select_relevance_score_fn(self):
        """Überschreibt die Methode zur Auswahl der Relevanzfunktion."""
        return lambda x: x
    
    def _ensure_connection(self):
        """Stellt sicher, dass die Verbindung zu Weaviate besteht."""
        if not self.db_manager.is_connected():
            self.db_manager.connect()
    
    def similarity_search_with_score(self, *args, **kwargs):
        """Führt eine Ähnlichkeitssuche mit Scores durch und stellt die Verbindung wieder her, falls nötig."""
        self._ensure_connection()
        try:
            return super().similarity_search_with_score(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Fehler bei similarity_search_with_score: {str(e)}")
            self._ensure_connection()
            return super().similarity_search_with_score(*args, **kwargs)
    
    def similarity_search(self, *args, **kwargs):
        """Führt eine Ähnlichkeitssuche durch und stellt die Verbindung wieder her, falls nötig."""
        self._ensure_connection()
        try:
            return super().similarity_search(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Fehler bei similarity_search: {str(e)}")
            self._ensure_connection()
            return super().similarity_search(*args, **kwargs)

class RetrieverFactory:
    """Fabrik zur Erstellung von Retrievern für verschiedene Weaviate-Sammlungen."""
    
    def __init__(self, openai_api_key: str = None):
        self.logger = logging.getLogger(__name__)
        self.db_manager = WeaviateManager()
        self.openai_api_key = openai_api_key or self.db_manager.api_key
        
    def create_retrievers(self) -> Tuple[Optional[KeepAliveWeaviateVectorStore], 
                                         Optional[KeepAliveWeaviateVectorStore], 
                                         Optional[KeepAliveWeaviateVectorStore]]:
        """
        Erstellt Retriever für Chunks, Summaries und Quotes.
        
        Returns:
            Tuple mit (chunks_retriever, summaries_retriever, quotes_retriever)
        """
        if not self.db_manager.client:
            self.logger.error("Kein Weaviate-Client verfügbar")
            return None, None, None
        
        try:
            # Überprüfe, ob die Daten existieren
            data_status = self.db_manager.check_data()
            if not data_status["classes_exist"]:
                self.logger.error("Weaviate-Schema existiert nicht")
                return None, None, None
                
            if not data_status["has_sufficient_data"]:
                self.logger.warning("Nicht genügend Daten in Weaviate")
                
            # Erstelle Embeddings
            embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)
            
            # Chunks-Retriever
            chunks_retriever = KeepAliveWeaviateVectorStore(
                client=self.db_manager.client,
                index_name="Chunk",
                text_key="content",
                embedding=embeddings,
                attributes=["url", "title", "chapter", "section", "importance_score", "chunking_strategy"]
            )
            
            # Summaries-Retriever
            summaries_retriever = KeepAliveWeaviateVectorStore(
                client=self.db_manager.client,
                index_name="Summary",
                text_key="content",
                embedding=embeddings,
                attributes=["url", "title", "document_id"]
            )
            
            # Quotes-Retriever
            quotes_retriever = KeepAliveWeaviateVectorStore(
                client=self.db_manager.client,
                index_name="Quote",
                text_key="content",
                embedding=embeddings,
                attributes=["url", "title", "document_id"]
            )
            
            return chunks_retriever, summaries_retriever, quotes_retriever
            
        except Exception as e:
            self.logger.error(f"Fehler beim Erstellen der Retriever: {str(e)}")
            return None, None, None

# Funktion zur Kompatibilität mit bestehendem Code
def create_retrievers() -> Tuple[Optional[object], Optional[object], Optional[object]]:
    """
    Erstellt die drei Retriever für die Anwendung.
    
    Returns:
        Ein Tupel mit (chunks_retriever, summaries_retriever, quotes_retriever)
    """
    factory = RetrieverFactory()
    return factory.create_retrievers()
