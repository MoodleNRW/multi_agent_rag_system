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
- [ ] Integration zusätzlicher LLM-Provider (wie Groq im Notebook)
- [ ] Strukturierte Ausgabeformate für LLMs konsistent implementieren
- [ ] Templating-System für Prompts verbessern
- [ ] Temperaturseinstellungen besser konfigurierbar machen

## Graph-Workflow-Verbesserungen
- [ ] Graph-Visualisierungsfunktion vollständig implementieren (wie im Notebook)
- [ ] Bedingte Kanten für komplexere Entscheidungslogik hinzufügen
- [ ] Rekursionsbehandlung verbessern
- [ ] Workflow-Fehlerbehandlung robuster gestalten

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
- [ ] Ragas-basierte Evaluationspipeline implementieren (wie im Notebook)
- [ ] Metriken für Antwortqualität einbauen
- [ ] Halluzinationserkennung verbessern
- [ ] A/B-Tests zur Verbesserung der RAG-Pipeline ermöglichen
- [ ] Feedback-Loop für kontinuierliche Verbesserung implementieren

## Fragebearbeitung und -analyse
- [ ] Frage-Umformulierung implementieren (wie im Notebook mit `rewrite_question`)
- [ ] Chain-of-Thought Reasoning für komplexe Antworten einbauen
- [ ] Relevanzprüfung für abgerufene Kontexte verbessern
- [ ] Datenextraktions- und Zusammenfassungsfunktionen erweitern

## Benutzerschnittstelle
- [x] Benutzerfreundliche Fehlermeldungen bei fehlenden Daten implementieren
- [x] Crawler-Integration in die UI für einfache Datenerfassung
- [ ] Fortschrittsanzeige für komplexe Anfragen verbessern
- [ ] Konversationsverlauf speichern und nutzen
- [ ] Einstellungsoptionen erweitern
- [ ] Benutzerauthentifizierung hinzufügen
- [ ] Mehrsprachige Unterstützung ausbauen

## Wartung und Dokumentation
- [x] Logging verbessern für einfachere Fehlersuche
- [ ] Einheitlichen Code-Stil implementieren
- [ ] Vollständige Dokumentation für alle Komponenten erstellen
- [ ] Unit-Tests für Kernfunktionen hinzufügen
- [ ] Konfigurationsmanagement vereinheitlichen

## Infrastruktur
- [x] Verbesserte Fehlererkennung für die Weaviate-Datenbank
- [ ] Docker-Konfiguration für einfacheres Deployment optimieren
- [ ] Umgebungsvariablen und Konfigurationsmanagement verbessern
- [ ] Performance-Optimierung für große Datenmengen
- [ ] Ressourcenverwaltung für LLM-Aufrufe implementieren (Rate-Limiting, Kostenkontrolle) 