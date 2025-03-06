"""
Evaluierungsmodul für das Multi-Agent-RAG-System.

Dieses Modul enthält Komponenten zur Evaluierung der Qualität der generierten Antworten.
"""

from evaluation.ragas_evaluator import evaluate_conversation, display_evaluation_results, RagasEvaluator

__all__ = ["evaluate_conversation", "display_evaluation_results", "RagasEvaluator"] 