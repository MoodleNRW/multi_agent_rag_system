# multi_agent_rag_system
## Inhaltsverzeichnis

- [Einführung](#einführung)
- [Installation](#installation)
- [Benutzung](#benutzung)
- [Abhängigkeiten](#abhängigkeiten)
- [Beitragen](#beitragen)

## Einführung

Diese Chainlit-Anwendung ist eine interaktive Chat-Schnittstelle, die sich mit einer OpenAI-kompatiblen API von GWDG (Gesellschaft für wissenschaftliche Datenverarbeitung mbH Göttingen) verbindet. Sie ermöglicht Benutzern die Interaktion mit verschiedenen KI-Modellen und bietet eine flexible Möglichkeit zur Verwaltung von Einstellungen und Konfigurationen.

**Bitte beachten Sie, dass es sich um einen Prototyp handelt, der zu Lernzwecken in der AG KI in Moodle vom Moodle an Hochschulen e.V. dient. Eine Verwendung in Produktivumgebungen wird nicht empfohlen.**

## Installation

Um die Chainlit-Anwendung auf Ihrem Rechner zu installieren und einzurichten, folgen Sie diesen Schritten:

1. Stellen Sie sicher, dass Python 3 auf Ihrem System installiert ist.
2. Klonen Sie dieses Repository auf Ihren lokalen Rechner:

    ```bash
    git clone https://github.com/Freakrider/chainlit_gwdg.git
    cd chainlit_gwdg
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

## Benutzung

Nach der Installation des Projekts können Sie die Chainlit-Anwendung starten:

```bash
chainlit run app.py
```

Die Anwendung wird dann in Ihrem Standard-Webbrowser geöffnet. Sie können die Einstellungen über die Benutzeroberfläche anpassen, einschließlich des API-Schlüssels, der Temperatur, der maximalen Token-Anzahl und des zu verwendenden Modells.

## Abhängigkeiten

Die Chainlit-Anwendung benötigt folgende Hauptabhängigkeiten:

- **Python 3**: [Installationsanleitung](https://www.python.org/downloads/)
- **Chainlit**: Für die Chat-Benutzeroberfläche
- **OpenAI**: Für die Verbindung zur KI-API
- **Requests**: Für HTTP-Anfragen

Alle erforderlichen Pakete sind in der `Requirements.txt`-Datei aufgelistet.

## Beitragen

Wir begrüßen Beiträge zu diesem Projekt! Um beizutragen:

1. Forken Sie das Repository.
2. Erstellen Sie einen neuen Branch für Ihr Feature oder Ihren Fix.
3. Committen Sie Ihre Änderungen und pushen Sie sie zu Ihrem Fork.
4. Reichen Sie einen Pull Request mit einer klaren Beschreibung Ihrer Änderungen ein.

Bitte stellen Sie sicher, dass Ihr Code den vorhandenen Stil-Richtlinien folgt und fügen Sie bei Bedarf Tests hinzu.