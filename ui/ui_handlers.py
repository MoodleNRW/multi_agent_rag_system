import chainlit as cl
import logging
import time
import os

# Konfiguriere Logger
logger = logging.getLogger(__name__)

# Emojis und Beschreibungen für verschiedene Workflow-Zustände
STEP_INFO = {
    "anonymize_question": {
        "emoji": "🔒",
        "description": "Anonymisiere die Frage für das ersetzen von bennanter Entitäten durch Platzhalter",
        "type": "process"
    },
    "planner": {
        "emoji": "🧠",
        "description": "Plane die Schritte zur Beantwortung deiner Frage...",
        "type": "process"
    },
    "de_anonymize_plan": {
        "emoji": "🔓",
        "description": "De-anonymisiere den Plan...",
        "type": "process"
    },
    "break_down_plan": {
        "emoji": "📋",
        "description": "Teile den Plan in kleinere Schritte auf...",
        "type": "process"
    },
    "task_handler": {
        "emoji": "🔄",
        "description": "Entscheide über die nächste Aktion...",
        "type": "process"
    },
    "retrieve_chunks": {
        "emoji": "🔍",
        "description": "Suche nach relevanten Textabschnitten...",
        "type": "tool"
    },
    "retrieve_summaries": {
        "emoji": "📝",
        "description": "Suche nach passenden Zusammenfassungen...",
        "type": "tool"
    },
    "retrieve_quotes": {
        "emoji": "💬",
        "description": "Suche nach relevanten Zitaten...",
        "type": "tool"
    },
    "answer": {
        "emoji": "✍️",
        "description": "Formuliere eine Antwort basierend auf den gefundenen Informationen...",
        "type": "output"
    },
    "replan": {
        "emoji": "🔄",
        "description": "Passe den Plan basierend auf neuen Informationen an...",
        "type": "process"
    },
    "get_final_answer": {
        "emoji": "✅",
        "description": "Erstelle die endgültige Antwort...",
        "type": "output"
    },
    "hallucination_check": {
        "emoji": "🔍",
        "description": "Überprüfe, ob die Antwort auf Fakten basiert...",
        "type": "process"
    },
    "relevance_check": {
        "emoji": "🎯",
        "description": "Überprüfe, ob der abgerufene Inhalt relevant ist...",
        "type": "process"
    }
}

async def show_crawler_option():
    """Zeigt eine Schaltfläche zum Ausführen des Crawlers an, wenn nicht genügend Daten vorhanden sind."""
    msg = cl.Message(content="📥 **Crawler starten**\n\nDer Crawler sammelt Daten von der Moodle-Dokumentation, um fundierte Antworten auf Ihre Fragen geben zu können. Klicken Sie auf die Schaltfläche unten, um den Prozess zu starten.")
    
    actions = [
        cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
    ]
    
    msg.actions = actions
    await msg.send()

async def update_ui(step_output):
    """
    Aktualisiert die Benutzeroberfläche basierend auf dem aktuellen Schritt im Workflow.
    
    Args:
        step_output: Der aktuelle Ausgabezustand des Workflows
    """
    # Füge eine Null-Überprüfung hinzu
    if step_output is None:
        logger.warning("UI Update: step_output ist None, überspringe Update")
        return
        
    current_state = step_output.get("curr_state", "")
    logger.debug(f"UI Update: {current_state}")
    
    # Wenn der aktuelle Zustand bekannt ist, zeige eine detaillierte Statusmeldung an
    if current_state in STEP_INFO:
        step_info = STEP_INFO[current_state]
        
        # Erstelle eine TaskList für die Anzeige des aktuellen Schritts
        task_list = cl.TaskList(status=f"Verarbeite: {current_state.replace('_', ' ').title()}")
        
        # Erstelle eine Task mit dem entsprechenden Emoji und Statustext
        task = cl.Task(
            title=f"{step_info['emoji']} {current_state.replace('_', ' ').title()}",
            status=cl.TaskStatus.RUNNING
        )
        
        # Füge die Task zur TaskList hinzu
        await task_list.add_task(task)
        
        # Sende die TaskList
        await task_list.send()
        
        # Sende eine detaillierte Nachricht, die den aktuellen Prozess erklärt
        message_content = f"{step_info['emoji']} **{current_state.replace('_', ' ').title()}**: {step_info['description']}"
        
        # Füge weitere Details hinzu, wenn verfügbar
        if current_state.startswith("retrieve_"):
            # Zeige Fortschritt für Retrieval-Schritte
            message_content += "\n\n*Suche nach den relevantesten Informationen für deine Anfrage...*"
            
            # Zeige die Abfrage an
            if "query_to_retrieve_or_answer" in step_output:
                message_content += f"\n\n**Abfrage**: {step_output['query_to_retrieve_or_answer']}"
        elif current_state == "answer":
            # Zeige Fortschritt für Antwort-Generierung
            message_content += "\n\n*Formuliere eine präzise und hilfreiche Antwort basierend auf den gefundenen Informationen...*"
            
            # Zeige die Frage an
            if "query_to_retrieve_or_answer" in step_output:
                message_content += f"\n\n**Frage**: {step_output['query_to_retrieve_or_answer']}"
        elif current_state == "hallucination_check":
            # Zeige Fortschritt für Halluzinationsprüfung
            message_content += "\n\n*Überprüfe, ob die generierte Antwort auf den abgerufenen Fakten basiert...*"
        elif current_state == "relevance_check":
            # Zeige Fortschritt für Relevanzprüfung
            message_content += "\n\n*Überprüfe, ob der abgerufene Inhalt für die Anfrage relevant ist...*"
        elif current_state == "get_final_answer":
            # Zeige Fortschritt für endgültige Antwort
            message_content += "\n\n*Erstelle eine umfassende Antwort basierend auf allen gesammelten Informationen...*"
        
        message = await cl.Message(content=message_content).send()
        
        # Verknüpfe die Task mit der Nachricht
        task.forId = message.id
        
        # Aktualisiere den Task-Status nach kurzer Verzögerung
        task.status = cl.TaskStatus.DONE
        await task_list.send()
        
        # Zeige den Gedankengang an, wenn verfügbar
        if current_state == "answer" and "reasoning" in step_output:
            await cl.Message(content=f"🧠 **Gedankengang**:\n\n{step_output['reasoning']}").send()
        elif current_state == "get_final_answer" and "final_reasoning" in step_output:
            await cl.Message(content=f"🧠 **Finaler Gedankengang**:\n\n{step_output['final_reasoning']}").send()
    else:
        # Fallback für unbekannte Zustände
        await cl.Message(content=f"🔄 Verarbeite: {current_state}").send()

    # Logge zusätzliche Informationen für Debugging
    if "plan" in step_output and step_output["plan"]:
        plan_steps = step_output["plan"]
        if len(plan_steps) > 0:
            # Erstelle eine TaskList für den Plan
            plan_task_list = cl.TaskList(status="Plan")
            
            # Erstelle eine Task für den Plan-Header
            plan_header_task = cl.Task(title="📋 Plan", status=cl.TaskStatus.DONE)
            await plan_task_list.add_task(plan_header_task)
            
            # Sende die TaskList
            await plan_task_list.send()
            
            # Erstelle eine TaskList für die einzelnen Planschritte
            steps_task_list = cl.TaskList(status="Schritte werden ausgeführt")
            
            # Füge für jeden Schritt eine Task hinzu und setze den Status auf RUNNING
            step_tasks = []
            for i, step in enumerate(plan_steps, 1):
                step_task = cl.Task(title=f"Schritt {i}: {step}", status=cl.TaskStatus.RUNNING)
                await steps_task_list.add_task(step_task)
                step_tasks.append(step_task)
            
            # Sende die TaskList mit den Schritten im RUNNING-Status
            await steps_task_list.send()
            
            # Aktualisiere den Status aller Tasks auf DONE
            for task in step_tasks:
                task.status = cl.TaskStatus.DONE
            
            # Aktualisiere den Status der TaskList
            steps_task_list.status = "Schritte abgeschlossen"
            
            # Sende die aktualisierte TaskList erneut, um die Statusänderungen zu übermitteln
            await steps_task_list.send() 