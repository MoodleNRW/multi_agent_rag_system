import chainlit as cl
import logging
import time
import os
import asyncio # Importiere asyncio für sleep

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
    },
    "keep_only_relevant_content": {
        "emoji": "🗑️",
        "description": "Filtere irrelevante Informationen heraus...",
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
    Zeigt nur die TaskList für Zwischenschritte an.
    
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
        task_list = cl.TaskList(status=f"Aktueller Schritt: {current_state.replace('_', ' ').title()}")
        
        # Erstelle eine Task mit dem entsprechenden Emoji und der Beschreibung im Titel
        task = cl.Task(
            title=f"{step_info['emoji']} {current_state.replace('_', ' ').title()}: {step_info['description']}",
            status=cl.TaskStatus.RUNNING
        )
        
        # Füge die Task zur TaskList hinzu
        await task_list.add_task(task)
        
        # Sende die TaskList mit dem RUNNING Status
        await task_list.send()
        
        # Kurze Pause, damit der Benutzer den "RUNNING"-Status sehen kann
        await asyncio.sleep(0.1) 
        
        # Aktualisiere den Task-Status auf DONE
        # (Nur die finale Antwort wird als separate Nachricht gesendet, nicht die Statusmeldung hier)
        if current_state != "get_final_answer": # Markiere alle Schritte außer dem letzten als DONE
             task.status = cl.TaskStatus.DONE
             await task_list.send() # Sende die aktualisierte TaskList

        # Keine separaten cl.Message-Objekte mehr für Zwischenschritte
        # message_content = ...
        # message = await cl.Message(content=message_content).send()
        # task.forId = message.id # Nicht mehr relevant ohne message
        
        # Auch keine Gedankengang-Nachrichten mehr
        # if current_state == "answer" ...

    # Logge zusätzliche Informationen für Debugging (unverändert)
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
            
            # Kurze Pause, damit der Benutzer den "RUNNING"-Status sehen kann
            await asyncio.sleep(0.1)

            # Aktualisiere den Status aller Tasks auf DONE
            for task in step_tasks:
                task.status = cl.TaskStatus.DONE
            
            # Aktualisiere den Status der TaskList
            steps_task_list.status = "Schritte abgeschlossen"
            
            # Sende die aktualisierte TaskList erneut, um die Statusänderungen zu übermitteln
            await steps_task_list.send() 