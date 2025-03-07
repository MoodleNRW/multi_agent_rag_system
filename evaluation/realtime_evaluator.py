"""
Echtzeit-Evaluierung des Multi-Agent-RAG-Systems.

Diese Komponente evaluiert das System während der Verarbeitung von Nachrichten,
anstatt nur nachträglich mit RAGAS.
"""

import logging
import time
from typing import Dict, Any, List, Optional
import chainlit as cl
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)

class RealtimeEvaluator:
    """
    Klasse zur Echtzeit-Evaluierung des RAG-Systems während der Verarbeitung von Nachrichten.
    """
    
    def __init__(self):
        """
        Initialisiert den Echtzeit-Evaluator.
        """
        self.metrics = {
            "retrieval_time": [],
            "answer_time": [],
            "total_time": [],
            "num_retrieval_steps": [],
            "num_reasoning_steps": [],
            "context_relevance": [],
            "answer_quality": []
        }
        self.current_evaluation = {}
        self.start_time = None
        self.total_retrieval_time = 0  # Neue Variable für die Gesamtzeit aller Retrieval-Schritte
    
    def start_evaluation(self, question: str):
        """
        Startet die Evaluierung für eine neue Frage.
        
        Args:
            question: Die zu evaluierende Frage
        """
        self.start_time = time.time()
        self.total_retrieval_time = 0  # Zurücksetzen der Gesamtzeit
        self.current_evaluation = {
            "question": question,
            "retrieval_start_time": None,
            "retrieval_end_time": None,
            "answer_start_time": None,
            "answer_end_time": None,
            "retrieved_contexts": [],
            "reasoning_steps": [],
            "final_answer": None,
            "processed_steps": [],
            "retrieval_steps": [],
            "reasoning_steps": []
        }
        logger.info(f"Starte Echtzeit-Evaluierung für Frage: {question}")
    
    def log_retrieval_start(self):
        """Protokolliert den Start eines Retrieval-Schritts."""
        self.current_evaluation["retrieval_start_time"] = time.time()
        logger.info(f"Retrieval-Start: {self.current_evaluation['retrieval_start_time']}")
    
    def log_retrieval_end(self):
        """Protokolliert das Ende eines Retrieval-Schritts und addiert die Zeit zur Gesamtzeit."""
        end_time = time.time()
        if "retrieval_start_time" in self.current_evaluation:
            step_time = end_time - self.current_evaluation["retrieval_start_time"]
            self.total_retrieval_time += step_time
            logger.info(f"Retrieval-Schritt-Zeit: {step_time}, Gesamtzeit bisher: {self.total_retrieval_time}")
        self.current_evaluation["retrieval_end_time"] = end_time
    
    def log_answer_start(self):
        """Protokolliert den Start eines Antwort-Generierungsschritts."""
        if self.current_evaluation.get("answer_start_time") is None:
            self.current_evaluation["answer_start_time"] = time.time()
    
    def log_answer_end(self):
        """Protokolliert das Ende eines Antwort-Generierungsschritts."""
        self.current_evaluation["answer_end_time"] = time.time()
    
    def add_retrieved_context(self, context: str, relevance_score: Optional[float] = None):
        """
        Fügt einen abgerufenen Kontext zur Evaluierung hinzu.
        
        Args:
            context: Der abgerufene Kontext
            relevance_score: Optional, der Relevanz-Score des Kontexts
        """
        self.current_evaluation["retrieved_contexts"].append({
            "context": context,
            "relevance_score": relevance_score,
            "timestamp": time.time()
        })
    
    def add_reasoning_step(self, reasoning: str):
        """
        Fügt einen Reasoning-Schritt zur Evaluierung hinzu.
        
        Args:
            reasoning: Der Reasoning-Schritt
        """
        self.current_evaluation["reasoning_steps"].append({
            "reasoning": reasoning,
            "timestamp": time.time()
        })
    
    def set_final_answer(self, answer: str):
        """
        Setzt die endgültige Antwort für die Evaluierung.
        
        Args:
            answer: Die endgültige Antwort
        """
        self.current_evaluation["final_answer"] = answer
    
    async def evaluate_context_relevance(self, question: str, context: str) -> float:
        """
        Evaluiert die Relevanz eines Kontexts für eine Frage.
        
        Args:
            question: Die Frage
            context: Der Kontext
            
        Returns:
            Ein Relevanz-Score zwischen 0 und 1
        """
        prompt_template = """
        Auf einer Skala von 0 bis 1, wie relevant ist der folgende Kontext für die gegebene Frage?
        
        Frage: {question}
        
        Kontext: {context}
        
        Gib nur eine Zahl zwischen 0 und 1 zurück, wobei 0 bedeutet "überhaupt nicht relevant" und 1 bedeutet "vollständig relevant".
        """
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["question", "context"],
        )
        
        llm = get_llm(temperature=0)
        chain = prompt | llm
        
        response = chain.invoke({
            "question": question,
            "context": context
        })
        
        try:
            # Extrahiere die Zahl aus der Antwort
            relevance_score = float(response.content.strip())
            # Stelle sicher, dass der Score zwischen 0 und 1 liegt
            relevance_score = max(0, min(1, relevance_score))
            return relevance_score
        except:
            logger.warning(f"Konnte keinen gültigen Relevanz-Score aus der Antwort extrahieren: {response.content}")
            return 0.5  # Fallback-Wert
    
    async def evaluate_answer_quality(self, question: str, answer: str, context: str) -> Dict[str, float]:
        """
        Evaluiert die Qualität einer Antwort.
        
        Args:
            question: Die Frage
            answer: Die Antwort
            context: Der Kontext
            
        Returns:
            Ein Dictionary mit verschiedenen Qualitätsmetriken
        """
        prompt_template = """
        Evaluiere die folgende Antwort auf eine Frage basierend auf dem gegebenen Kontext.
        
        Frage: {question}
        
        Kontext: {context}
        
        Antwort: {answer}
        
        Bewerte die Antwort auf einer Skala von 0 bis 1 für die folgenden Kriterien:
        1. Korrektheit: Ist die Antwort sachlich korrekt basierend auf dem Kontext?
        2. Vollständigkeit: Beantwortet die Antwort die Frage vollständig?
        3. Relevanz: Ist die Antwort relevant für die Frage?
        4. Klarheit: Ist die Antwort klar und verständlich formuliert?
        5. Prägnanz: Ist die Antwort prägnant und auf den Punkt gebracht?
        
        Gib deine Bewertung in folgendem Format zurück:
        {{"correctness": 0.X, "completeness": 0.X, "relevance": 0.X, "clarity": 0.X, "conciseness": 0.X}}
        """
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["question", "context", "answer"],
        )
        
        llm = get_llm(temperature=0)
        chain = prompt | llm
        
        response = chain.invoke({
            "question": question,
            "context": context,
            "answer": answer
        })
        
        try:
            # Extrahiere das JSON aus der Antwort
            import json
            import re
            
            # Suche nach einem JSON-Objekt in der Antwort
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                scores = json.loads(json_str)
                
                # Stelle sicher, dass alle erwarteten Schlüssel vorhanden sind
                expected_keys = ["correctness", "completeness", "relevance", "clarity", "conciseness"]
                for key in expected_keys:
                    if key not in scores:
                        scores[key] = 0.5  # Fallback-Wert
                
                # Stelle sicher, dass alle Scores zwischen 0 und 1 liegen
                for key in scores:
                    scores[key] = max(0, min(1, float(scores[key])))
                
                return scores
            else:
                logger.warning(f"Konnte kein JSON-Objekt in der Antwort finden: {response.content}")
                return {key: 0.5 for key in ["correctness", "completeness", "relevance", "clarity", "conciseness"]}
        except Exception as e:
            logger.warning(f"Fehler beim Extrahieren der Qualitätsmetriken: {str(e)}")
            return {key: 0.5 for key in ["correctness", "completeness", "relevance", "clarity", "conciseness"]}
    
    def complete_evaluation(self) -> Dict[str, Any]:
        """
        Schließt die aktuelle Evaluierung ab und berechnet die Metriken.
        
        Returns:
            Ein Dictionary mit den Evaluierungsergebnissen
        """
        end_time = time.time()
        
        # Berechne Zeiten
        total_time = end_time - self.start_time
        
        # Verwende die akkumulierte Retrieval-Zeit
        retrieval_time = self.total_retrieval_time
        logger.info(f"Gesamte Retrieval-Zeit: {retrieval_time}")
        
        answer_time = 0
        if self.current_evaluation.get("answer_start_time") and self.current_evaluation.get("answer_end_time"):
            answer_time = self.current_evaluation["answer_end_time"] - self.current_evaluation["answer_start_time"]
        
        # Zähle Schritte aus den Listen
        num_retrieval_steps = len(self.current_evaluation.get("retrieval_steps", []))
        num_reasoning_steps = len(self.current_evaluation.get("reasoning_steps", []))
        
        logger.info(f"Retrieval-Schritte: {self.current_evaluation.get('retrieval_steps', [])}")
        logger.info(f"Reasoning-Schritte: {self.current_evaluation.get('reasoning_steps', [])}")
        
        # Aktualisiere Metriken
        self.metrics["retrieval_time"].append(retrieval_time)
        self.metrics["answer_time"].append(answer_time)
        self.metrics["total_time"].append(total_time)
        self.metrics["num_retrieval_steps"].append(num_retrieval_steps)
        self.metrics["num_reasoning_steps"].append(num_reasoning_steps)
        
        # Erstelle Evaluierungsergebnis
        result = {
            "question": self.current_evaluation["question"],
            "final_answer": self.current_evaluation["final_answer"],
            "metrics": {
                "retrieval_time": retrieval_time,
                "answer_time": answer_time,
                "total_time": total_time,
                "num_retrieval_steps": num_retrieval_steps,
                "num_reasoning_steps": num_reasoning_steps
            },
            "retrieved_contexts": self.current_evaluation["retrieved_contexts"],
            "reasoning_steps": self.current_evaluation["reasoning_steps"],
            "processed_steps": self.current_evaluation.get("processed_steps", [])
        }
        
        logger.info(f"Evaluierung abgeschlossen: {result['metrics']}")
        
        return result
    
    async def display_evaluation_results(self, results: Dict[str, Any]):
        """
        Zeigt die Evaluierungsergebnisse in der Chainlit-UI an.
        
        Args:
            results: Die Evaluierungsergebnisse
        """
        message_content = "## 📊 Echtzeit-Evaluierungsergebnisse\n\n"
        
        # Füge Metriken hinzu
        message_content += "### ⏱️ Zeitmetriken\n\n"
        
        # Formatiere Zeiten mit mehr Dezimalstellen für sehr kleine Werte
        total_time = results['metrics']['total_time']
        retrieval_time = results['metrics']['retrieval_time']
        answer_time = results['metrics']['answer_time']
        
        # Verwende dynamische Formatierung für bessere Lesbarkeit kleiner Werte
        if total_time < 0.01:
            total_time_formatted = f"{total_time:.6f}"
        else:
            total_time_formatted = f"{total_time:.2f}"
            
        if retrieval_time < 0.01:
            retrieval_time_formatted = f"{retrieval_time:.6f}"
        else:
            retrieval_time_formatted = f"{retrieval_time:.2f}"
            
        if answer_time < 0.01:
            answer_time_formatted = f"{answer_time:.6f}"
        else:
            answer_time_formatted = f"{answer_time:.2f}"
        
        message_content += f"- **Gesamtzeit**: {total_time_formatted} Sekunden\n"
        message_content += f"- **Retrieval-Zeit**: {retrieval_time_formatted} Sekunden\n"
        message_content += f"- **Antwort-Zeit**: {answer_time_formatted} Sekunden\n\n"
        
        message_content += "### 🔄 Prozessmetriken\n\n"
        message_content += f"- **Anzahl Retrieval-Schritte**: {results['metrics']['num_retrieval_steps']}\n"
        message_content += f"- **Anzahl Reasoning-Schritte**: {results['metrics']['num_reasoning_steps']}\n\n"
        
        # Zeige verarbeitete Schritte an
        if "processed_steps" in results and results["processed_steps"]:
            message_content += "### 🔍 Verarbeitete Schritte\n\n"
            message_content += ", ".join(results["processed_steps"]) + "\n\n"
        
        # Füge Kontext-Relevanz hinzu, falls vorhanden
        if results["retrieved_contexts"]:
            message_content += "### 📚 Verwendete Quellen\n\n"
            for i, context_data in enumerate(results["retrieved_contexts"], 1):
                context = context_data.get("context", "")
                relevance_score = context_data.get("relevance_score")
                
                # Kürze den Kontext auf maximal 200 Zeichen
                short_context = context[:200] + "..." if len(context) > 200 else context
                
                message_content += f"**Quelle {i}**:\n"
                message_content += f"{short_context}\n"
                
                if relevance_score is not None:
                    message_content += f"Relevanz: {relevance_score:.2f}\n"
                
                message_content += "\n"
        
        # Sende die Nachricht
        await cl.Message(content=message_content).send()

# Erstelle eine globale Instanz des Evaluators
realtime_evaluator = RealtimeEvaluator()

async def evaluate_step(state: Dict[str, Any], step_name: str):
    """
    Evaluiert einen Schritt im Workflow.
    
    Args:
        state: Der aktuelle Zustand
        step_name: Der Name des Schritts
    """
    logger.info(f"Evaluiere Schritt: {step_name}")
    
    # Spezielle Behandlung für relevance_check und hallucination_check
    if step_name == "relevance_check":
        if step_name not in realtime_evaluator.current_evaluation.get("processed_steps", []):
            realtime_evaluator.current_evaluation.setdefault("processed_steps", []).append(step_name)
        if step_name not in realtime_evaluator.current_evaluation.get("retrieval_steps", []):
            realtime_evaluator.current_evaluation.setdefault("retrieval_steps", []).append(step_name)
        return
    
    if step_name == "hallucination_check":
        if step_name not in realtime_evaluator.current_evaluation.get("processed_steps", []):
            realtime_evaluator.current_evaluation.setdefault("processed_steps", []).append(step_name)
        if step_name not in realtime_evaluator.current_evaluation.get("reasoning_steps", []):
            realtime_evaluator.current_evaluation.setdefault("reasoning_steps", []).append(step_name)
        return
    
    # Retrieval-Schritte erkennen
    retrieval_steps = [
        "retrieve_chunks", 
        "retrieve_summaries", 
        "retrieve_quotes", 
        "parallel_retrieval",
        "retrieve_or_answer",
        "is_relevant_content",
        "check_relevance",
        "relevance_check"
    ]
    
    # Reasoning-Schritte erkennen
    reasoning_steps = [
        "anonymize_question",
        "planner",
        "de_anonymize_plan",
        "break_down_plan",
        "task_handler",
        "replan",
        "can_be_answered",
        "answer",
        "check_hallucination",
        "hallucination_check",
        "is_answer_grounded_on_context"
    ]
    
    # Füge den Schritt zur Liste der verarbeiteten Schritte hinzu
    if step_name not in realtime_evaluator.current_evaluation.get("processed_steps", []):
        realtime_evaluator.current_evaluation.setdefault("processed_steps", []).append(step_name)
    
    # Kategorisiere den Schritt
    if step_name in retrieval_steps:
        if step_name not in realtime_evaluator.current_evaluation.get("retrieval_steps", []):
            realtime_evaluator.current_evaluation.setdefault("retrieval_steps", []).append(step_name)
        
        realtime_evaluator.log_retrieval_start()
        
        # Wenn der Schritt abgeschlossen ist und ein Kontext vorhanden ist
        if "context" in state and state["context"]:
            # Füge den Kontext zur Evaluierung hinzu
            relevance_score = None
            try:
                relevance_score = await realtime_evaluator.evaluate_context_relevance(
                    state["question"], 
                    state["context"]
                )
            except Exception as e:
                logger.warning(f"Fehler bei der Evaluierung der Kontext-Relevanz: {str(e)}")
            
            realtime_evaluator.add_retrieved_context(state["context"], relevance_score)
        
        realtime_evaluator.log_retrieval_end()
    
    elif step_name in reasoning_steps:
        if step_name not in realtime_evaluator.current_evaluation.get("reasoning_steps", []):
            realtime_evaluator.current_evaluation.setdefault("reasoning_steps", []).append(step_name)
        
        realtime_evaluator.log_answer_start()
        
        # Wenn ein Reasoning vorhanden ist
        if "reasoning" in state and state["reasoning"]:
            realtime_evaluator.add_reasoning_step(state["reasoning"])
        
        realtime_evaluator.log_answer_end()
    
    elif step_name == "get_final_answer":
        # Wenn eine Antwort vorhanden ist
        if "response" in state and state["response"]:
            realtime_evaluator.set_final_answer(state["response"])

async def start_evaluation(question: str):
    """
    Startet die Echtzeit-Evaluierung für eine neue Frage.
    
    Args:
        question: Die zu evaluierende Frage
    """
    realtime_evaluator.start_evaluation(question)

async def complete_evaluation():
    """
    Schließt die aktuelle Evaluierung ab und zeigt die Ergebnisse an.
    
    Returns:
        Die Evaluierungsergebnisse
    """
    results = realtime_evaluator.complete_evaluation()
    await realtime_evaluator.display_evaluation_results(results)
    return results 