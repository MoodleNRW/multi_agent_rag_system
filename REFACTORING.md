# Refactoring Documentation

## Übersicht der Refaktorierung

Die Anwendung wurde refaktoriert, um eine bessere Modularität, Wartbarkeit und Skalierbarkeit zu ermöglichen. Die ursprüngliche `app.py`-Datei mit 908 Zeilen wurde in mehrere Module aufgeteilt, wobei jedes Modul für einen bestimmten Aspekt der Anwendung verantwortlich ist.

## Neue Projektstruktur

Die Anwendung wurde in die folgenden Hauptmodule aufgeteilt:

### 1. UI-Modul (`ui/`)
- `ui_handlers.py`: Beinhaltet Funktionen zur Darstellung der Benutzeroberfläche
- `__init__.py`: Exportiert die Hauptfunktionen des Moduls

### 2. Crawling-Modul (`crawling/`)
- `crawler_manager.py`: Verwaltet den Crawling-Prozess und die zugehörigen Callbacks
- `__init__.py`: Exportiert die Hauptfunktionen des Moduls

### 3. Vektor-DB-Modul (`vector_stores/`)
- `db_manager.py`: Beinhaltet Funktionen für das Datenbank-Management und -Operationen
- `retriever.py`: Implementiert die Retriever-Funktionalität 
- `weaviate_client.py`: Beinhaltet die Weaviate-Client-Implementierung
- `__init__.py`: Exportiert die Hauptfunktionen des Moduls

### 4. Hauptanwendung (`app.py`)
- Eine schlankere Hauptdatei, die die verschiedenen Module integriert
- Enthält nur noch die Kernfunktionalität und Callbacks

## Vorteile der neuen Struktur

1. **Bessere Lesbarkeit**: Kleinere Dateien sind einfacher zu verstehen und zu warten.
2. **Bessere Testbarkeit**: Module können unabhängig voneinander getestet werden.
3. **Bessere Erweiterbarkeit**: Neue Funktionen können einfacher hinzugefügt werden, ohne die Kernlogik zu beeinflussen.
4. **Klare Verantwortlichkeiten**: Jedes Modul hat eine definierte Aufgabe.
5. **Einfachere Fehlersuche**: Probleme können leichter auf ein bestimmtes Modul eingegrenzt werden.

## Änderungen im Detail

### UI-Modul
- Extrahierte UI-bezogene Funktionen aus der Hauptdatei.
- Verbesserte Dokumentation der UI-Funktionen.

### Crawling-Modul
- Extrahierte Crawler-bezogene Funktionen aus der Hauptdatei.
- Verbesserte Fehlerbehandlung im Crawler-Manager.

### Vektor-DB-Modul
- Extrahierte Datenbank-Management-Funktionen aus der Hauptdatei.
- Verbesserte Ressourcenverwaltung durch konsequentes Schließen von Datenbankverbindungen.
- Einheitlicher Zugriff auf die Vektordatenbank durch zentrale Funktionen.

### Hauptanwendung
- Reduzierte die Komplexität durch das Auslagern von Funktionen in dedizierte Module.
- Verbesserte Fehlerbehandlung und Logging.
- Zentrale Konfiguration und Initialisierung.

## Verwendung der refaktorierten Anwendung

Die Anwendung wird genauso verwendet wie zuvor:
```
chainlit run app.py
```

Die Funktionalität bleibt identisch, aber der Code ist nun besser strukturiert und einfacher zu warten. 