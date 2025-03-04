# TODO-Liste für Multi-Agent-RAG-System

## Vektorspeicher-Integration
- [ ] Implementierung der Vektorspeicher-Retriever in `vector_stores/retriever.py` vervollständigen
- [ ] Weaviate-Client-Verbindung stabilisieren und fehlerbehandlung hinzufügen
- [ ] Unterstützung für verschiedene Chunking-Strategien einbauen
- [ ] Dokument-Metadaten besser nutzen (wie im Notebook mit chapter_metadata)

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
- [ ] Crawler-Optimierung für bessere Extraktion von Moodle-Dokumentation
- [ ] Inkrementelle Aktualisierung der Vektordatenbank implementieren
- [ ] Vorverarbeitungs-Pipeline für Dokumente verbessern
- [ ] Unterstützung für verschiedene Dokumenttypen erweitern

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
- [ ] Fortschrittsanzeige für komplexe Anfragen verbessern
- [ ] Konversationsverlauf speichern und nutzen
- [ ] Einstellungsoptionen erweitern
- [ ] Benutzerauthentifizierung hinzufügen

## Wartung und Dokumentation
- [ ] Einheitlichen Code-Stil implementieren
- [ ] Vollständige Dokumentation für alle Komponenten erstellen
- [ ] Unit-Tests für Kernfunktionen hinzufügen
- [ ] Logging verbessern für einfachere Fehlersuche
- [ ] Konfigurationsmanagement vereinheitlichen

## Infrastruktur
- [ ] Docker-Konfiguration für einfacheres Deployment optimieren
- [ ] Umgebungsvariablen und Konfigurationsmanagement verbessern
- [ ] Performance-Optimierung für große Datenmengen
- [ ] Ressourcenverwaltung für LLM-Aufrufe implementieren (Rate-Limiting, Kostenkontrolle) 