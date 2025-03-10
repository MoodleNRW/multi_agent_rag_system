# Moodle-Daten Import für Weaviate

Dieses Skript importiert Moodle-Dokumentationsdaten im JSON-Format in die Weaviate-Vektordatenbank.

## Voraussetzungen

- Python 3.9 oder höher
- Eine laufende Weaviate-Instanz (standardmäßig auf http://localhost:8090)
- Die Umgebungsvariable `OPENAI_API_KEY` muss gesetzt sein (für die Vektorisierung)
- Installierte Abhängigkeiten (siehe unten)

## Installation

```bash
pip install weaviate-client python-dotenv tqdm
```

## Verwendung

1. Stelle sicher, dass Weaviate läuft.
2. Bereite deine JSON-Datendatei vor. Die Daten sollten in folgendem Format vorliegen:

```json
[
  {
    "id": 25258,
    "title": "AI placements",
    "sections": [
      {
        "id": "0e6ce627-cd37-5842-a203-25e98f5408e1",
        "anchor": "",
        "title": "AI placements",
        "source": "https://docs.moodle.org/405/en/AI_placements",
        "text": "Inhalt des Abschnitts...",
        "all_links": [],
        "wiki_links": [],
        "index": 0,
        "level": 1,
        "page_id": 25258,
        "doc_id": "dd5d4766-0aac-556f-8778-2afc00e5d4e9",
        "doc_title": "AI placements",
        "doc_hash": "be562830-41f0-597a-81a4-117a6ea1dec7",
        "parent": null,
        "children": [],
        "previous": [],
        "next": [],
        "relations": []
      }
    ],
    "categories": ["Kategorie1", "Kategorie2"],
    "internal_links": [],
    "external_links": [],
    "language_links": []
  }
]
```

3. Führe das Skript mit dem Pfad zur JSON-Datei aus:

```bash
python moodle_import.py deine_daten.json
```

## Was macht das Skript?

1. Es verbindet sich mit deiner lokalen Weaviate-Instanz.
2. Es stellt sicher, dass alle erforderlichen Schema-Klassen in Weaviate vorhanden sind.
3. Es importiert jedes Dokument als:
   - Einen Hauptdokumenteintrag in der `Content`-Collection.
   - Einzelne Abschnitte als Chunks in der `Content_chunk`-Collection.
   - Eine automatisch generierte kurze Zusammenfassung in der `Content_summary`-Collection.
4. Es liefert statistische Informationen über den Import-Prozess.

## Fehlerbehandlung

- Das Skript protokolliert detaillierte Informationen über den Import-Prozess.
- Bei Fehlern während des Imports wird das Skript versuchen, fortzufahren und die fehlgeschlagenen Einträge zu protokollieren.

## Anmerkungen

- Das Schema wird automatisch erstellt, falls es nicht existiert.
- Bereits existierende Daten in der Datenbank werden nicht überschrieben oder gelöscht.
- Der Import kann je nach Datenmenge einige Zeit dauern.
- Es wird empfohlen, den Import mit einer kleinen Datenprobe zu testen, bevor große Datenmengen importiert werden. 