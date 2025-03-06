#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Skript zur Durchführung der RAGAS-Evaluierung des Multi-Agent-RAG-Systems.
"""

import asyncio
import argparse
import json
import os
import sys
from typing import List, Dict, Any, Optional

# Füge das Hauptverzeichnis zum Pfad hinzu, um Importe zu ermöglichen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.ragas_evaluator import evaluate_conversation, RagasEvaluator
from models.models_wrapper import get_llm

async def run_evaluation_from_file(file_path: str):
    """
    Führt eine Evaluierung basierend auf Testdaten aus einer JSON-Datei durch.
    
    Args:
        file_path: Pfad zur JSON-Datei mit Testdaten
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        questions = test_data.get('questions', [])
        answers = test_data.get('answers', [])
        contexts = test_data.get('contexts', [])
        ground_truths = test_data.get('ground_truths', None)
        
        if not questions or not answers or not contexts:
            print("Fehler: Die Testdaten müssen Listen für 'questions', 'answers' und 'contexts' enthalten.")
            return
        
        if len(questions) != len(answers) or len(questions) != len(contexts):
            print("Fehler: Die Listen für 'questions', 'answers' und 'contexts' müssen die gleiche Länge haben.")
            return
        
        if ground_truths and len(ground_truths) != len(questions):
            print("Warnung: Die Liste 'ground_truths' hat nicht die gleiche Länge wie 'questions'. Verwende keine Ground-Truth-Antworten.")
            ground_truths = None
        
        print(f"Starte Evaluierung mit {len(questions)} Testfällen...")
        evaluator = RagasEvaluator()
        results = await evaluator.evaluate_answers(questions, answers, contexts, ground_truths)
        
        # Speichere Ergebnisse in einer JSON-Datei
        output_path = os.path.splitext(file_path)[0] + "_results.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"Evaluierungsergebnisse wurden in '{output_path}' gespeichert.")
        
        # Zeige Zusammenfassung der Ergebnisse
        print("\n=== Evaluierungsergebnisse ===")
        if "avg_scores" in results:
            for metric, score in results["avg_scores"].items():
                print(f"{metric}: {score:.4f}")
        else:
            print(f"Fehler: {results.get('error', 'Unbekannter Fehler')}")
    
    except FileNotFoundError:
        print(f"Fehler: Die Datei '{file_path}' wurde nicht gefunden.")
    except json.JSONDecodeError:
        print(f"Fehler: Die Datei '{file_path}' enthält kein gültiges JSON.")
    except Exception as e:
        print(f"Fehler bei der Evaluierung: {str(e)}")

def create_example_test_data(output_path: str):
    """
    Erstellt eine Beispiel-Testdatendatei.
    
    Args:
        output_path: Pfad zur Ausgabedatei
    """
    example_data = {
        "questions": [
            "Was ist Moodle?",
            "Wie erstelle ich einen Kurs in Moodle?",
            "Welche Aktivitäten kann ich in Moodle hinzufügen?"
        ],
        "answers": [
            "Moodle ist ein Open-Source-Lernmanagementsystem, das von Bildungseinrichtungen weltweit genutzt wird, um Online-Kurse zu erstellen und zu verwalten.",
            "Um einen Kurs in Moodle zu erstellen, müssen Sie Administrator- oder Kursersteller-Rechte haben. Gehen Sie zur Seite 'Website-Administration' > 'Kurse' > 'Kurse verwalten' und klicken Sie auf 'Neuen Kurs anlegen'. Füllen Sie die erforderlichen Felder aus und klicken Sie auf 'Speichern'.",
            "In Moodle können Sie verschiedene Aktivitäten hinzufügen, wie Foren, Aufgaben, Tests, Wikis, Glossare, Datenbanken, Workshops, Umfragen und SCORM-Pakete. Jede Aktivität bietet unterschiedliche Interaktionsmöglichkeiten für die Lernenden."
        ],
        "contexts": [
            "Moodle ist ein Open-Source-Lernmanagementsystem (LMS), das von Bildungseinrichtungen weltweit genutzt wird, um Online-Kurse zu erstellen und zu verwalten. Es wurde entwickelt, um Lehrenden und Lernenden eine sichere und integrierte Plattform für personalisiertes Lernen zu bieten.",
            "Kurserstellung in Moodle: Gehen Sie zur Administration > Kurse > Kurse verwalten und klicken Sie auf 'Neuen Kurs anlegen'. Füllen Sie die erforderlichen Felder wie Kursname, Kurzbeschreibung und Format aus. Wählen Sie die gewünschten Einstellungen für Sichtbarkeit, Datum und Zugriff. Klicken Sie auf 'Speichern', um den Kurs zu erstellen.",
            "Moodle bietet verschiedene Aktivitäten wie Foren, Aufgaben, Tests, Wikis, Glossare, Datenbanken, Workshops, Umfragen und SCORM-Pakete. Foren ermöglichen Diskussionen, Aufgaben dienen zur Einreichung von Arbeiten, Tests zur Bewertung, Wikis zur kollaborativen Inhaltserstellung, Glossare zum Erstellen von Begriffslisten, Datenbanken zum Sammeln von Einträgen, Workshops für Peer-Reviews, Umfragen für Feedback und SCORM-Pakete für interaktive Inhalte."
        ],
        "ground_truths": [
            "Moodle ist ein Open-Source-Lernmanagementsystem (LMS), das von Bildungseinrichtungen weltweit genutzt wird.",
            "Um einen Kurs zu erstellen, navigieren Sie zu 'Administration' > 'Kurse' > 'Kurse verwalten' und klicken auf 'Neuen Kurs anlegen'. Füllen Sie die erforderlichen Informationen aus und speichern Sie.",
            "Moodle unterstützt folgende Aktivitäten: Foren, Aufgaben, Tests, Wikis, Glossare, Datenbanken, Workshops, Umfragen und SCORM-Pakete."
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(example_data, f, indent=2, ensure_ascii=False)
    
    print(f"Beispiel-Testdaten wurden in '{output_path}' gespeichert.")

async def main():
    parser = argparse.ArgumentParser(description="RAGAS-Evaluierung für das Multi-Agent-RAG-System")
    parser.add_argument("--file", "-f", type=str, help="Pfad zur JSON-Datei mit Testdaten")
    parser.add_argument("--create-example", "-c", action="store_true", help="Erstellt eine Beispiel-Testdatendatei")
    parser.add_argument("--output", "-o", type=str, default="example_test_data.json", help="Pfad zur Ausgabedatei für Beispiel-Testdaten")
    
    args = parser.parse_args()
    
    if args.create_example:
        create_example_test_data(args.output)
    elif args.file:
        await run_evaluation_from_file(args.file)
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main()) 