# RAGAS-Evaluierung im Multi-Agent-RAG-System

Diese Dokumentation beschreibt die Implementierung und Verwendung der RAGAS-Evaluierung im Multi-Agent-RAG-System.

## Was ist RAGAS?

RAGAS (Retrieval Augmented Generation Assessment System) ist ein Framework zur Evaluierung von RAG-Systemen. Es bietet verschiedene Metriken zur Bewertung der Qualität von generierten Antworten und abgerufenen Kontexten.

## Implementierte Metriken

Das System verwendet folgende RAGAS-Metriken:

1. **Antwortgenauigkeit (answer_correctness)**
   - Misst, ob die generierte Antwort sachlich korrekt ist
   - Bewertet die Übereinstimmung mit Ground-Truth-Antworten (falls vorhanden)
   - Werte zwischen 0 und 1, wobei höhere Werte besser sind

2. **Treue (faithfulness)**
   - Misst, wie gut die generierte Antwort durch die abgerufenen Dokumente gestützt wird
   - Erkennt Halluzinationen und nicht durch den Kontext gestützte Behauptungen
   - Werte zwischen 0 und 1, wobei höhere Werte besser sind

3. **Antwortrelevanz (answer_relevancy)**
   - Misst, wie relevant die generierte Antwort für die Frage ist
   - Bewertet, ob die Antwort tatsächlich auf die Frage eingeht
   - Werte zwischen 0 und 1, wobei höhere Werte besser sind

4. **Kontextabruf (context_recall)**
   - Misst den Anteil der relevanten Dokumente, die erfolgreich abgerufen wurden
   - Bewertet die Qualität des Retrieval-Prozesses
   - Werte zwischen 0 und 1, wobei höhere Werte besser sind

5. **Antwortähnlichkeit (answer_similarity)**
   - Misst die semantische Ähnlichkeit zwischen der generierten Antwort und der Ground-Truth-Antwort
   - Bewertet die inhaltliche Übereinstimmung, nicht nur wörtliche Übereinstimmung
   - Werte zwischen 0 und 1, wobei höhere Werte besser sind

## Verwendung der RAGAS-Evaluierung

### Über die Benutzeroberfläche

1. Starten Sie die Anwendung mit `chainlit run app.py`
2. Klicken Sie auf den "📊 RAGAS-Evaluierung" Button in der Benutzeroberfläche
3. Wählen Sie eine der folgenden Optionen:
   - **Testdaten hochladen**: Laden Sie eine JSON-Datei mit Testdaten hoch
   - **Aktuelle Konversation evaluieren**: Evaluieren Sie die aktuelle Konversationshistorie

### Über die Kommandozeile

Sie können die Evaluierung auch über die Kommandozeile durchführen:

```bash
# Erstellen einer Beispiel-Testdatendatei
python evaluation/run_evaluation.py --create-example --output example_test_data.json

# Durchführen der Evaluierung
python evaluation/run_evaluation.py --file example_test_data.json
```

## Format der Testdaten

Die Testdaten müssen im JSON-Format vorliegen und folgende Struktur haben:

```json
{
  "questions": [
    "Was ist Moodle?",
    "Wie erstelle ich einen Kurs in Moodle?"
  ],
  "answers": [
    "Moodle ist ein Open-Source-Lernmanagementsystem...",
    "Um einen Kurs in Moodle zu erstellen, müssen Sie..."
  ],
  "contexts": [
    "Moodle ist ein Open-Source-Lernmanagementsystem, das...",
    "Kurserstellung in Moodle: Gehen Sie zur Administration..."
  ],
  "ground_truths": [
    "Moodle ist ein Open-Source-Lernmanagementsystem...",
    "Um einen Kurs zu erstellen, navigieren Sie..."
  ]
}
```

- `questions`: Liste der Fragen
- `answers`: Liste der generierten Antworten
- `contexts`: Liste der abgerufenen Kontexte
- `ground_truths` (optional): Liste der Ground-Truth-Antworten

## Interpretation der Ergebnisse

Die Evaluierungsergebnisse werden in der Benutzeroberfläche angezeigt und in einer JSON-Datei gespeichert. Die Ergebnisse enthalten:

- Durchschnittliche Scores für jede Metrik
- Detaillierte Ergebnisse für jede Frage-Antwort-Kombination
- Erklärungen der Metriken

### Beispiel für Evaluierungsergebnisse

```json
{
  "metrics_explanation": {
    "answer_correctness": "Misst, ob die generierte Antwort sachlich korrekt ist.",
    "faithfulness": "Misst, wie gut die generierte Antwort durch die abgerufenen Dokumente gestützt wird.",
    "answer_relevancy": "Misst, wie relevant die generierte Antwort für die Frage ist.",
    "context_recall": "Misst den Anteil der relevanten Dokumente, die erfolgreich abgerufen wurden.",
    "answer_similarity": "Misst die semantische Ähnlichkeit zwischen der generierten Antwort und der Ground-Truth-Antwort."
  },
  "avg_scores": {
    "answer_correctness": 0.95,
    "faithfulness": 0.87,
    "answer_relevancy": 0.92,
    "context_recall": 0.78,
    "answer_similarity": 0.89
  },
  "detailed_results": [
    {
      "question": "Was ist Moodle?",
      "answer": "Moodle ist ein Open-Source-Lernmanagementsystem...",
      "answer_correctness": 1.0,
      "faithfulness": 0.95,
      "answer_relevancy": 0.98,
      "context_recall": 0.85,
      "answer_similarity": 0.92
    },
    ...
  ]
}
```

## Verbesserung des RAG-Systems basierend auf Evaluierungsergebnissen

Die RAGAS-Evaluierung kann verwendet werden, um das RAG-System zu verbessern:

1. **Niedrige Faithfulness-Scores**: Verbessern Sie die Halluzinationsprüfung und stellen Sie sicher, dass Antworten auf den abgerufenen Kontexten basieren.

2. **Niedrige Context-Recall-Scores**: Optimieren Sie die Retrieval-Komponente, indem Sie die Chunking-Strategie anpassen oder die Anzahl der abgerufenen Dokumente erhöhen.

3. **Niedrige Answer-Relevancy-Scores**: Verbessern Sie die Prompt-Templates für die Antwortgenerierung, um sicherzustellen, dass die Antworten auf die Fragen eingehen.

4. **Niedrige Answer-Correctness-Scores**: Überprüfen Sie die Qualität der abgerufenen Dokumente und verbessern Sie die Faktenprüfung.

5. **Niedrige Answer-Similarity-Scores**: Passen Sie die Antwortgenerierung an, um besser mit den erwarteten Antworten übereinzustimmen.

## Technische Implementierung

Die RAGAS-Evaluierung ist in folgenden Dateien implementiert:

- `evaluation/ragas_evaluator.py`: Hauptimplementierung der RAGAS-Evaluierung
- `evaluation/run_evaluation.py`: Kommandozeilen-Tool für die Evaluierung
- `ui/evaluation_ui.py`: UI-Komponenten für die Evaluierung

Die Evaluierungsergebnisse werden in der Benutzeroberfläche angezeigt und in einer JSON-Datei gespeichert. 