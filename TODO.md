# TODO-Liste für Multi-Agent-RAG-System

## Vektorspeicher-Integration
- [x] Implementierung der Vektorspeicher-Retriever in `vector_stores/retriever.py` vervollständigen
- [x] Weaviate-Client-Verbindung stabilisieren und Fehlerbehandlung hinzufügen
- [x] Überprüfung auf ausreichende Daten in der Vektordatenbank implementieren
- [x] Unterstützung für verschiedene Chunking-Strategien einbauen
- [x] Dokument-Metadaten besser nutzen (wie im Notebook mit chapter_metadata)
- [x] Visualisierung der Weaviate-Datenbankinhalte implementieren
- [x] Funktionalität zum Leeren der Datenbank hinzufügen

## LLM-Integration
- [x] Integration zusätzlicher LLM-Provider (wie Groq im Notebook)
- [x] Strukturierte Ausgabeformate für LLMs konsistent implementieren
- [x] Templating-System für Prompts verbessern
- [x] Temperaturseinstellungen besser konfigurierbar machen

## Graph-Workflow-Verbesserungen
- [x] Graph-Visualisierungsfunktion vollständig implementieren (wie im Notebook)
- [x] Bedingte Kanten für komplexere Entscheidungslogik hinzufügen
- [x] Rekursionsbehandlung verbessern
- [x] Workflow-Fehlerbehandlung robuster gestalten

## Moodle-Integration
- [ ] Moodle-API-Anbindung für Kurserstellung vollständig implementieren
- [ ] Authentifizierung für Moodle-API hinzufügen
- [ ] Weitere Moodle-spezifische Tools entwickeln
- [ ] Moodle-Benutzerrechte und -rollen berücksichtigen

## Daten-Crawler und -Verarbeitung
- [x] Crawler-Optimierung für bessere Extraktion von Moodle-Dokumentation
- [x] Integration des Crawlers in die Benutzeroberfläche für einfachere Datenerfassung
- [ ] Inkrementelle Aktualisierung der Vektordatenbank implementieren
- [ ] Vorverarbeitungs-Pipeline für Dokumente verbessern
- [ ] Unterstützung für verschiedene Dokumenttypen erweitern
- [ ] Scheduling für regelmäßige Aktualisierungen der Datenbank

## Evaluation und Qualitätssicherung
- [x] Ragas-basierte Evaluationspipeline implementieren (wie im Notebook)
- [x] Metriken für Antwortqualität einbauen
- [x] Halluzinationserkennung verbessern
- [x] A/B-Tests zur Verbesserung der RAG-Pipeline ermöglichen
- [x] Feedback-Loop für kontinuierliche Verbesserung implementieren

## Fragebearbeitung und -analyse
- [x] Frage-Umformulierung implementieren (wie im Notebook mit `rewrite_question`)
- [x] Chain-of-Thought Reasoning für komplexe Antworten einbauen
- [x] Relevanzprüfung für abgerufene Kontexte verbessern
- [x] Datenextraktions- und Zusammenfassungsfunktionen erweitern

## Benutzerschnittstelle
- [x] Benutzerfreundliche Fehlermeldungen bei fehlenden Daten implementieren
- [x] Crawler-Integration in die UI für einfache Datenerfassung
- [x] Fortschrittsanzeige für komplexe Anfragen verbessern
- [ ] Konversationsverlauf speichern und nutzen
- [x] Einstellungsoptionen erweitern
- [ ] Benutzerauthentifizierung hinzufügen
- [ ] Mehrsprachige Unterstützung ausbauen

## Wartung und Dokumentation
- [x] Logging verbessern für einfachere Fehlersuche
- [ ] Einheitlichen Code-Stil implementieren
- [ ] Vollständige Dokumentation für alle Komponenten erstellen
- [ ] Unit-Tests für Kernfunktionen hinzufügen
- [x] Konfigurationsmanagement vereinheitlichen

## Infrastruktur
- [x] Verbesserte Fehlererkennung für die Weaviate-Datenbank
- [ ] Docker-Konfiguration für einfacheres Deployment optimieren
- [x] Umgebungsvariablen und Konfigurationsmanagement verbessern
- [ ] Performance-Optimierung für große Datenmengen
- [ ] Ressourcenverwaltung für LLM-Aufrufe implementieren (Rate-Limiting, Kostenkontrolle)

## Implementierte Verbesserungen aus dem Notebook
- [x] Halluzinationsprüfung mit `is_answer_grounded_on_context` implementiert
- [x] Relevanzprüfung mit `is_relevant_content` implementiert
- [x] RAGAS-Evaluierungskomponente implementiert
- [x] Erweiterte Modellunterstützung (Groq, Claude, Ollama) implementiert
- [x] Chain-of-Thought-Reasoning für komplexe Antworten implementiert
- [x] Verbesserte Workflow-Logik mit bedingten Kanten implementiert
- [x] Verbesserte UI-Anzeige für Gedankengänge und Zwischenschritte
- [x] RAGAS-Evaluierung in die UI integriert
- [x] Konversationshistorie für Evaluierungszwecke implementiert 