import chainlit as cl
from typing import List, Dict, Any
import pandas as pd
import asyncio
import logging
from datasets import Dataset
from models.models_wrapper import get_llm

# Importiere RAGAS-Komponenten
try:
    from ragas import evaluate
    from ragas.metrics import (
        answer_correctness,
        faithfulness,
        answer_relevancy,
        context_recall,
        answer_similarity
    )
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    logging.warning("RAGAS ist nicht installiert. Die Evaluierungsfunktionen werden nicht verfügbar sein.")

logger = logging.getLogger(__name__)

class RagasEvaluator:
    """
    Klasse zur Evaluierung von RAG-Antworten mit RAGAS-Metriken.
    """
    
    def __init__(self):
        """
        Initialisiert den RAGAS-Evaluator.
        """
        self.metrics = [
            answer_correctness,
            faithfulness,
            answer_relevancy,
            context_recall,
            answer_similarity
        ] if RAGAS_AVAILABLE else []
        
    async def evaluate_answers(self, 
                              questions: List[str], 
                              answers: List[str], 
                              contexts: List[str], 
                              ground_truths: List[str] = None) -> Dict[str, Any]:
        """
        Evaluiert die generierten Antworten mit RAGAS-Metriken.
        
        Args:
            questions: Liste der Fragen
            answers: Liste der generierten Antworten
            contexts: Liste der abgerufenen Kontexte
            ground_truths: Liste der Ground-Truth-Antworten (optional)
            
        Returns:
            Dictionary mit Evaluierungsergebnissen
        """
        if not RAGAS_AVAILABLE:
            return {"error": "RAGAS ist nicht installiert. Bitte installieren Sie RAGAS mit 'pip install ragas'."}
        
        if ground_truths is None:
            ground_truths = ["" for _ in questions]
        
        # Bereite Daten für RAGAS vor
        data_samples = {
            'question': questions,
            'answer': answers,
            'contexts': [[context] for context in contexts],  # RAGAS erwartet eine Liste von Kontexten pro Frage
            'ground_truth': ground_truths
        }
        
        dataset = Dataset.from_dict(data_samples)
        
        # Führe die Evaluierung in einem separaten Thread aus, um die UI nicht zu blockieren
        loop = asyncio.get_event_loop()
        score = await loop.run_in_executor(None, self._run_evaluation, dataset)
        
        # Konvertiere die Ergebnisse in ein Dictionary
        results_df = score.to_pandas()
        results = self._analyze_results(results_df)
        
        return results
    
    def _run_evaluation(self, dataset):
        """
        Führt die RAGAS-Evaluierung aus.
        
        Args:
            dataset: Das Dataset mit Fragen, Antworten, Kontexten und Ground-Truth-Antworten
            
        Returns:
            RAGAS-Evaluierungsergebnisse
        """
        llm = get_llm(temperature=0)
        return evaluate(dataset, metrics=self.metrics, llm=llm)
    
    def _analyze_results(self, results_df):
        """
        Analysiert die RAGAS-Evaluierungsergebnisse.
        
        Args:
            results_df: DataFrame mit RAGAS-Evaluierungsergebnissen
            
        Returns:
            Dictionary mit analysierten Ergebnissen
        """
        metrics_explanation = {
            "answer_correctness": "Misst, ob die generierte Antwort sachlich korrekt ist.",
            "faithfulness": "Misst, wie gut die generierte Antwort durch die abgerufenen Dokumente gestützt wird.",
            "answer_relevancy": "Misst, wie relevant die generierte Antwort für die Frage ist.",
            "context_recall": "Misst den Anteil der relevanten Dokumente, die erfolgreich abgerufen wurden.",
            "answer_similarity": "Misst die semantische Ähnlichkeit zwischen der generierten Antwort und der Ground-Truth-Antwort."
        }
        
        # Berechne Durchschnittswerte für jede Metrik
        avg_scores = {}
        for metric in metrics_explanation.keys():
            if metric in results_df.columns:
                avg_scores[metric] = results_df[metric].mean()
        
        # Erstelle ein Dictionary mit den Ergebnissen
        results = {
            "metrics_explanation": metrics_explanation,
            "avg_scores": avg_scores,
            "detailed_results": results_df.to_dict(orient="records")
        }
        
        return results

async def display_evaluation_results(results):
    """
    Zeigt die Evaluierungsergebnisse in der Chainlit-UI an.
    
    Args:
        results: Dictionary mit Evaluierungsergebnissen
    """
    if "error" in results:
        await cl.Message(content=f"⚠️ Fehler bei der Evaluierung: {results['error']}").send()
        return
    
    # Erstelle eine Nachricht mit den Evaluierungsergebnissen
    message_content = "## 📊 RAGAS-Evaluierungsergebnisse\n\n"
    
    # Füge die durchschnittlichen Scores hinzu
    message_content += "### Durchschnittliche Scores\n\n"
    for metric, score in results["avg_scores"].items():
        message_content += f"- **{metric}**: {score:.4f}\n"
    
    # Füge die Erklärungen der Metriken hinzu
    message_content += "\n### Erklärung der Metriken\n\n"
    for metric, explanation in results["metrics_explanation"].items():
        message_content += f"- **{metric}**: {explanation}\n"
    
    # Sende die Nachricht
    await cl.Message(content=message_content).send()
    
    # Erstelle eine Tabelle mit den detaillierten Ergebnissen
    if results["detailed_results"]:
        df = pd.DataFrame(results["detailed_results"])
        
        # Formatiere die Tabelle für die Anzeige
        table_content = "### Detaillierte Ergebnisse\n\n"
        table_content += "| Frage | Antwort | "
        
        # Füge die Metrik-Spalten hinzu
        for metric in results["metrics_explanation"].keys():
            if metric in df.columns:
                table_content += f"{metric} | "
        
        table_content += "\n| --- | --- | "
        for _ in range(len([m for m in results["metrics_explanation"].keys() if m in df.columns])):
            table_content += "--- | "
        
        # Füge die Zeilen hinzu
        for _, row in df.iterrows():
            table_content += f"\n| {row['question'][:50]}... | {row['answer'][:50]}... | "
            for metric in results["metrics_explanation"].keys():
                if metric in df.columns:
                    table_content += f"{row[metric]:.4f} | "
        
        # Sende die Tabelle
        await cl.Message(content=table_content).send()

# Erstelle eine Instanz des Evaluators
evaluator = RagasEvaluator()

async def evaluate_conversation(questions, answers, contexts, ground_truths=None):
    """
    Evaluiert eine Konversation mit RAGAS-Metriken.
    
    Args:
        questions: Liste der Fragen
        answers: Liste der generierten Antworten
        contexts: Liste der abgerufenen Kontexte
        ground_truths: Liste der Ground-Truth-Antworten (optional)
    """
    results = await evaluator.evaluate_answers(questions, answers, contexts, ground_truths)
    await display_evaluation_results(results) 