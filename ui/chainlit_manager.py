import chainlit as cl
import logging
import plotly.express as px
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import io
from typing import Dict, Any, List, Optional
import asyncio
from vector_stores.db_manager import WeaviateManager
from crawling.crawler_manager import CrawlerManager

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChainlitUIManager:
    """Manager für Chainlit UI-Interaktionen."""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ChainlitUIManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        self.db_manager = WeaviateManager()
        self.crawler_manager = CrawlerManager()
        self._initialized = True
    
    async def show_db_management(self):
        """Zeigt das Datenbank-Management-Panel an."""
        try:
            # Überprüfe Daten
            data_status = self.db_manager.check_data()
            
            # Erstelle Aktionsschaltflächen
            actions = []
            
            # Visualisierungsaktion
            actions.append(cl.Action(name="db_visualize", payload={"action": "visualize"}, label="📊 Daten visualisieren"))
            
            # Reinigungsaktionen
            if data_status["classes_exist"] and data_status["has_sufficient_data"]:
                actions.append(cl.Action(name="db_clear", payload={"action": "clear"}, label="🗑️ Ausgewählte Daten löschen"))
                actions.append(cl.Action(name="db_clear_all", payload={"action": "clear_all"}, label="💥 Alle Daten löschen"))
            
            # Restart-Aktion
            actions.append(cl.Action(name="app_restart", payload={"action": "restart"}, label="🔄 Anwendung neu starten"))
            
            # Nachricht mit Status und Aktionen
            status_message = ""
            
            # Status für jede Klasse
            for class_name, count in data_status["details"].items():
                status_message += f"- **{class_name}**: {count} Objekte\n"
            
            msg = cl.Message(content=f"## Datenbank-Status\n\n{status_message}\n\nWählen Sie eine Aktion aus:")
            msg.actions = actions
            await msg.send()
            
        except Exception as e:
            self.logger.error(f"Fehler beim Anzeigen des Datenbank-Managements: {str(e)}")
            await cl.Message(content=f"⚠️ Fehler beim Laden des Datenbank-Managements: {str(e)}").send()
    
    async def show_crawler_options(self, message: str = None):
        """Zeigt die Crawler-Optionen an."""
        if not message:
            message = "📥 **Crawler starten**\n\nDer Crawler sammelt Daten von der Moodle-Dokumentation, um fundierte Antworten auf Ihre Fragen geben zu können. Klicken Sie auf die Schaltfläche unten, um den Prozess zu starten."
        
        msg = cl.Message(content=message)
        
        actions = [
            cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
        ]
        
        msg.actions = actions
        await msg.send()
    
    async def show_chunking_strategies(self):
        """Zeigt die Optionen für Chunking-Strategien an."""
        strategy_actions = [
            cl.Action(name="select_strategy", payload={"strategy": "recursive"}, label="Rekursiv (Standard)"),
            cl.Action(name="select_strategy", payload={"strategy": "semantic"}, label="Semantisch (Überschriften)"),
            cl.Action(name="select_strategy", payload={"strategy": "hierarchical"}, label="Hierarchisch (Kapitel)")
        ]
        
        strategy_msg = cl.Message(content="Bitte wählen Sie eine Chunking-Strategie für die Verarbeitung der Dokumente:")
        strategy_msg.actions = strategy_actions
        await strategy_msg.send()
    
    async def update_crawler_status(self, status: Dict[str, Any]):
        """Aktualisiert den Crawler-Status in der UI."""
        progress = status.get("progress", 0)
        urls_processed = status.get("urls_processed", 0)
        total_urls = status.get("total_urls", 0)
        
        progress_text = f"Fortschritt: {progress:.2f}% ({urls_processed}/{total_urls} URLs verarbeitet)"
        
        message = f"""## Crawler-Status
        
Status: {'Läuft' if status.get('running', False) else 'Abgeschlossen'}
{progress_text}
Nachricht: {status.get('message', '')}
"""
        if status.get("errors", []):
            message += "\n**Fehler:**\n" + "\n".join([f"- {err}" for err in status["errors"]])
        
        await cl.Message(content=message).send()
    
    async def show_db_visualization(self):
        """Zeigt eine Visualisierung der Datenbank an."""
        try:
            # Überprüfe Daten
            data_status = self.db_manager.check_data()
            
            if not data_status["classes_exist"]:
                await cl.Message(content="⚠️ Es sind keine Daten in der Datenbank vorhanden, die visualisiert werden können.").send()
                return
            
            # Erstelle ein DataFrame für die Visualisierung
            data = []
            for class_name, count in data_status["details"].items():
                data.append({"Klasse": class_name, "Anzahl": count})
            
            df = pd.DataFrame(data)
            
            # Erstelle ein Balkendiagramm
            fig = px.bar(df, x="Klasse", y="Anzahl", title="Datenbank-Inhalt", 
                         color="Klasse", color_discrete_sequence=px.colors.qualitative.Pastel)
            
            # Speichere das Diagramm als Bild
            img_bytes = io.BytesIO()
            fig.write_image(img_bytes, format="png")
            img_bytes.seek(0)
            
            # Sende das Bild
            elements = [
                cl.Image(name="db_visualization", content=img_bytes.read(), display="inline")
            ]
            
            await cl.Message(content="## Datenbank-Visualisierung", elements=elements).send()
            
        except Exception as e:
            self.logger.error(f"Fehler bei der Datenbank-Visualisierung: {str(e)}")
            await cl.Message(content=f"⚠️ Fehler bei der Visualisierung: {str(e)}").send()
    
    async def update_workflow_step(self, step_output):
        """Aktualisiert die UI basierend auf dem Workflow-Schritt."""
        current_state = step_output.get("curr_state", "")
        
        state_messages = {
            "retrieve_chunks": "Retrieving information: retrieve_chunks",
            "retrieve_summaries": "Retrieving information: retrieve_summaries",
            "retrieve_quotes": "Retrieving information: retrieve_quotes",
            "answer": "Generating answer based on retrieved information...",
            "planner": "Planning next steps...",
            "anonymize_question": "Anonymizing the question...",
            "de_anonymize_plan": "De-anonymizing the plan...",
            "break_down_plan": "Breaking down the plan into smaller steps...",
            "task_handler": "Deciding on the next action...",
            "replan": "Adjusting the plan based on new information...",
            "get_final_answer": "Preparing the final answer..."
        }
        
        if current_state in state_messages:
            await cl.Message(content=state_messages[current_state]).send()
        
        # Task für Chainlit
        cl.Task(title=current_state, status=cl.TaskStatus.RUNNING) 