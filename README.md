# multi_agent_rag_system
## Inhaltsverzeichnis

- [Einführung](#einführung)
- [Installation](#installation)
- [Benutzung](#benutzung)
- [Daten-Crawler](#daten-crawler)
- [Evaluierung mit RAGAS](#evaluierung-mit-ragas)
- [Erweiterte Funktionen](#erweiterte-funktionen)
- [Abhängigkeiten](#abhängigkeiten)
- [Beitragen](#beitragen)

## Einführung

Das Multi-Agent-RAG-System (Retrieval Augmented Generation-System) für Moodle-Dokumentation und Code beantwortet automatisch Supportanfragen und unterstützt bei der Entwicklung. Es crawlt die Moodle Docs, um auf Anfragen in Echtzeit zu reagieren. Für komplexere Fälle erstellt es automatisch Tickets und leitet diese an die entsprechenden Experten weiter. 

**Bitte beachten Sie, dass es sich um einen Prototyp handelt, der während des DevCamps der MoodleMoot DACH 2024 entstanden ist. Eine Verwendung in Produktivumgebungen wird derzeit nicht empfohlen.**

## Installation

Um die Chainlit-Anwendung auf Ihrem Rechner zu installieren und einzurichten, folgen Sie diesen Schritten:

1. Stellen Sie sicher, dass Python 3 auf Ihrem System installiert ist.
2. Klonen Sie dieses Repository auf Ihren lokalen Rechner:

    ```bash
    git clone https://github.com/MoodleNRW/multi_agent_rag_system
    cd multi_agent_rag_system
    ```

3. Erstellen Sie eine virtuelle Umgebung:

    ```bash
    python3 -m venv .venv
    ```

4. Aktivieren Sie die virtuelle Umgebung (Mac):

    ```bash
    source .venv/bin/activate
    ```

5. Installieren Sie die erforderlichen Pakete:

    ```bash
    pip install -U -r requirements.txt
    ```

6. Starten Sie die Weaviate-Vektordatenbank über Docker:

    ```bash
    docker-compose up -d
    ```

## Benutzung

Nach der Installation des Projekts können Sie die Chainlit-Anwendung starten:

```bash
chainlit run app.py
```

Die Anwendung wird dann in Ihrem Standard-Webbrowser geöffnet. Sie können die Einstellungen über die Benutzeroberfläche anpassen, einschließlich des API-Schlüssels, der Temperatur, der maximalen Token-Anzahl und des zu verwendenden Modells.

### Fehlerbehebung

Wenn keine ausreichenden Daten in der Vektordatenbank vorhanden sind, wird die Anwendung automatisch eine Schaltfläche anzeigen, mit der Sie den Moodle-Docs-Crawler starten können. Dies sammelt die notwendigen Daten und speichert sie in der Weaviate-Datenbank.

## Daten-Crawler

Das System verfügt über einen integrierten Web-Crawler, der speziell für die Moodle-Dokumentation optimiert ist. Sie können den Crawler manuell ausführen, um die Vektordatenbank mit aktuellen Daten zu füllen:

```bash
python3 moodledoc_crawler.py https://moodlenrw.de 50
```

Parameter:
- URL der zu crawlenden Webseite (z.B. Moodle-Dokumentation)
- Maximale Anzahl der zu crawlenden Seiten (Tiefe)

Der Crawler wird automatisch die folgenden Schritte ausführen:
1. Sammeln aller relevanten Texte aus der Moodle-Dokumentation
2. Aufteilen der Texte in Chunks
3. Erstellen von Zusammenfassungen für jeden Abschnitt
4. Speichern der Daten in der Weaviate-Vektordatenbank

## Evaluierung mit RAGAS

Das System unterstützt die Evaluierung der Antwortqualität mit RAGAS (Retrieval Augmented Generation Assessment System). RAGAS bietet verschiedene Metriken zur Bewertung der Qualität von RAG-Systemen:

- **Antwortgenauigkeit (answer_correctness)**: Misst, ob die generierte Antwort sachlich korrekt ist.
- **Treue (faithfulness)**: Misst, wie gut die generierte Antwort durch die abgerufenen Dokumente gestützt wird.
- **Antwortrelevanz (answer_relevancy)**: Misst, wie relevant die generierte Antwort für die Frage ist.
- **Kontextabruf (context_recall)**: Misst den Anteil der relevanten Dokumente, die erfolgreich abgerufen wurden.
- **Antwortähnlichkeit (answer_similarity)**: Misst die semantische Ähnlichkeit zwischen der generierten Antwort und der Ground-Truth-Antwort.

### Evaluierung über die Benutzeroberfläche

1. Starten Sie die Anwendung mit `chainlit run app.py`
2. Klicken Sie auf den "📊 RAGAS-Evaluierung" Button
3. Wählen Sie eine der folgenden Optionen:
   - **Testdaten hochladen**: Laden Sie eine JSON-Datei mit Testdaten hoch
   - **Aktuelle Konversation evaluieren**: Evaluieren Sie die aktuelle Konversationshistorie

### Evaluierung über die Kommandozeile

Sie können die Evaluierung auch über die Kommandozeile durchführen:

```bash
# Erstellen einer Beispiel-Testdatendatei
python evaluation/run_evaluation.py --create-example --output example_test_data.json

# Durchführen der Evaluierung
python evaluation/run_evaluation.py --file example_test_data.json
```

Die Evaluierungsergebnisse werden sowohl in der Benutzeroberfläche angezeigt als auch in einer JSON-Datei gespeichert.

## Erweiterte Funktionen

Das System wurde mit mehreren fortschrittlichen Funktionen erweitert:

### Halluzinationsprüfung

Die Halluzinationsprüfung überprüft, ob die generierten Antworten auf den abgerufenen Fakten basieren. Dies verbessert die Zuverlässigkeit der Antworten erheblich.

### Relevanzprüfung

Die Relevanzprüfung bewertet, ob der abgerufene Kontext für die Anfrage relevant ist. Dies verbessert die Qualität der Antworten, indem irrelevante Informationen herausgefiltert werden.

### Chain-of-Thought-Reasoning

Das System verwendet Chain-of-Thought-Reasoning, um komplexe Fragen zu beantworten. Dies ermöglicht eine transparente Darstellung des Denkprozesses und verbessert die Nachvollziehbarkeit der Antworten.

### Erweiterte Modellunterstützung

Das System unterstützt verschiedene LLM-Provider:
- OpenAI (GPT-4, GPT-3.5)
- Groq (Llama 3)
- Claude (optional)
- Ollama (optional)

## Abhängigkeiten

Die Chainlit-Anwendung benötigt folgende Hauptabhängigkeiten:

- **Python 3**: [Installationsanleitung](https://www.python.org/downloads/)
- **Chainlit**: Für die Chat-Benutzeroberfläche
- **LangChain & LangGraph**: Für Workflow-Orchestrierung und RAG-Pipeline
- **Weaviate**: Als Vektordatenbank
- **OpenAI**: Für die Verbindung zur KI-API
- **Requests & BeautifulSoup4**: Für Web-Crawling
- **RAGAS**: Für die Evaluierung der Antwortqualität
- **Datasets**: Für die Verwaltung von Evaluierungsdaten

Alle erforderlichen Pakete sind in der `Requirements.txt`-Datei aufgelistet.

## Beitragen

Wir begrüßen Beiträge zu diesem Projekt! Um beizutragen:

1. Forken Sie das Repository.
2. Erstellen Sie einen neuen Branch für Ihr Feature oder Ihren Fix.
3. Committen Sie Ihre Änderungen und pushen Sie sie zu Ihrem Fork.
4. Reichen Sie einen Pull Request mit einer klaren Beschreibung Ihrer Änderungen ein.

Bitte stellen Sie sicher, dass Ihr Code den vorhandenen Stil-Richtlinien folgt und fügen Sie bei Bedarf Tests hinzu.
