import weaviate
import weaviate.classes as wvc
from weaviate.connect import ConnectionParams
import os
import logging
from typing import Dict, Any, Optional, Union
import dotenv

# Lade Umgebungsvariablen
dotenv.load_dotenv()

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class WeaviateManager:
    """Zentralisierter Manager für alle Weaviate-Operationen."""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(WeaviateManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, url: str = None, grpc_port: int = None):
        if self._initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        self.url = url or os.getenv('WEAVIATE_URL', 'http://localhost:8090')
        self.grpc_port = grpc_port or int(os.getenv('WEAVIATE_GRPC_PORT', '50051'))
        self.api_key = os.getenv('OPENAI_API_KEY')
        self._client = None
        self._initialized = True
        
    def __del__(self):
        """Stellt sicher, dass der Client ordnungsgemäß geschlossen wird, wenn das Objekt gelöscht wird."""
        self.disconnect()
        
    @property
    def client(self) -> Union[weaviate.WeaviateClient, None]:
        """Gibt den Weaviate-Client zurück, stellt sicher, dass er verbunden ist."""
        if not self._client:
            self._client = self._create_client()
        
        if self._client and not self.is_connected():
            self.connect()
            
        return self._client
    
    def _create_client(self) -> Optional[weaviate.WeaviateClient]:
        """Erstellt einen neuen Weaviate-Client."""
        try:
            self.logger.info(f"Verbindung zu Weaviate herstellen: {self.url}, GRPC-Port: {self.grpc_port}")
            
            # Extrahiere Host und Port aus der URL
            url_parts = self.url.replace("http://", "").replace("https://", "").split(":")
            host = url_parts[0]
            http_port = int(url_parts[1]) if len(url_parts) > 1 else 80
            
            # Korrigierte ConnectionParams-Erstellung für Weaviate Client v4.9.6 API
            connection_params = ConnectionParams(
                http={
                    "host": host,
                    "port": http_port,
                    "secure": self.url.startswith("https")
                },
                grpc={
                    "host": host,
                    "port": self.grpc_port,
                    "secure": self.url.startswith("https")
                }
            )
            
            # Client mit korrekten ConnectionParams erstellen
            client = weaviate.WeaviateClient(connection_params)
            
            # Verbindung testen
            try:
                # Direkt Meta-Information abfragen, um Verbindung zu überprüfen
                meta = client.get_meta()
                self.logger.info(f"Weaviate-Client erfolgreich verbunden mit Version: {meta.version}")
                return client
            except Exception as e:
                self.logger.error(f"Verbindungstest fehlgeschlagen: {str(e)}")
                client.close()
                return None
            
        except Exception as e:
            self.logger.error(f"Fehler beim Erstellen des Weaviate-Clients: {str(e)}")
            return None
    
    def is_connected(self) -> bool:
        """Überprüft, ob der Client verbunden ist."""
        if not self._client:
            return False
            
        try:
            # Verwende get_meta() statt cluster.get_nodes_status()
            self._client.get_meta()
            return True
        except Exception:
            return False
    
    def connect(self) -> bool:
        """Stellt eine Verbindung zum Weaviate-Server her."""
        try:
            if not self._client:
                self._client = self._create_client()
                
            if not self._client:
                self.logger.error("Konnte keinen Weaviate-Client erstellen")
                return False
                
            # Teste die Verbindung mit get_meta() statt cluster.get_nodes_status()
            meta = self._client.get_meta()
            self.logger.info(f"Erfolgreich mit Weaviate verbunden (Version: {meta.version})")
            return True
        except Exception as e:
            self.logger.error(f"Fehler bei der Verbindung mit Weaviate: {str(e)}")
            # Versuche den Client zu schließen, falls er existiert
            if self._client:
                try:
                    # Prüfe, ob close-Methode existiert
                    if hasattr(self._client, 'close'):
                        self._client.close()
                except Exception as close_err:
                    self.logger.error(f"Fehler beim Schließen des Clients: {str(close_err)}")
            self._client = None
            return False
    
    def disconnect(self) -> None:
        """Trennt die Verbindung zum Weaviate-Server ordnungsgemäß."""
        if self._client:
            try:
                if hasattr(self._client, 'close'):
                    self.logger.info("Schließe Weaviate-Client-Verbindung")
                    self._client.close()
            except Exception as e:
                self.logger.error(f"Fehler beim Schließen des Weaviate-Clients: {str(e)}")
            finally:
                self._client = None
    
    def check_data(self) -> Dict[str, Any]:
        """Überprüft die Daten in Weaviate."""
        if not self.client:
            return {
                "classes_exist": False,
                "has_sufficient_data": False,
                "details": {}
            }
        
        try:
            # Überprüfe, ob die erforderlichen Klassen existieren
            schema = self.client.schema.get()
            classes = [c["class"] for c in schema["classes"]] if "classes" in schema else []
            
            # Aktualisierte Namen der Klassen, die in der Datenbank existieren
            required_classes = ["Content", "Content_chunk", "Content_summary"]
            classes_exist = all(cls in classes for cls in required_classes)
            
            # Sammle Statistiken für jede Klasse
            details = {}
            has_sufficient_data = True
            
            for cls in required_classes:
                if cls in classes:
                    try:
                        # Zähle die Objekte in der Klasse
                        count = self.client.collections.get(cls).aggregate.over_all().total
                        details[cls] = count
                        
                        # Wenn eine Klasse weniger als 5 Objekte hat, reicht das möglicherweise nicht aus
                        if count < 5:
                            has_sufficient_data = False
                    except Exception as e:
                        self.logger.error(f"Fehler beim Zählen der Objekte in {cls}: {str(e)}")
                        details[cls] = 0
                        has_sufficient_data = False
                else:
                    details[cls] = 0
                    has_sufficient_data = False
            
            return {
                "classes_exist": classes_exist,
                "has_sufficient_data": has_sufficient_data,
                "details": details
            }
        except Exception as e:
            self.logger.error(f"Fehler beim Überprüfen der Weaviate-Daten: {str(e)}")
            return {
                "classes_exist": False,
                "has_sufficient_data": False,
                "details": {},
                "error": str(e)
            }
    
    def create_schema(self) -> bool:
        """Erstellt das Schema in Weaviate."""
        if not self.client:
            return False
            
        try:
            # Importiere die Schema-Erstellungsfunktion aus weaviate_client
            from vector_stores.weaviate_client import create_weaviate_schema
            
            # Verwende die Funktion mit dem aktuellen Client
            result = create_weaviate_schema(self.client)
            self.logger.info(f"Schema erstellt: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Fehler beim Erstellen des Schemas: {str(e)}")
            return False
    
    def close(self):
        """Schließt die Verbindung zum Weaviate-Server."""
        if self._client:
            try:
                self._client.close()
                self._client = None
            except Exception as e:
                self.logger.error(f"Fehler beim Schließen des Weaviate-Clients: {str(e)}")

# Globale Instanz
def ensure_global_client():
    """Stellt sicher, dass eine globale WeaviateManager-Instanz existiert und gibt deren Client zurück."""
    manager = WeaviateManager()
    return manager.client 