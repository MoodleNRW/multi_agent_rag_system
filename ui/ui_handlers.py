import chainlit as cl
import logging
import time
import os

# Konfiguriere Logger
logger = logging.getLogger(__name__)

async def show_crawler_option():
    """Zeigt eine Schaltfläche zum Ausführen des Crawlers an, wenn nicht genügend Daten vorhanden sind."""
    msg = cl.Message(content="📥 **Crawler starten**\n\nDer Crawler sammelt Daten von der Moodle-Dokumentation, um fundierte Antworten auf Ihre Fragen geben zu können. Klicken Sie auf die Schaltfläche unten, um den Prozess zu starten.")
    
    actions = [
        cl.Action(name="run_crawler", payload={"action": "run"}, label="🚀 Crawler ausführen")
    ]
    
    msg.actions = actions
    await msg.send()

async def update_ui(step_output):
    """Aktualisiert die Benutzeroberfläche basierend auf dem aktuellen Schritt im Workflow."""
    current_state = step_output.get("curr_state", "")
    print("UPDATE UI", step_output)
    if current_state in ["retrieve_chunks", "retrieve_summaries", "retrieve_quotes"]:
        await cl.Message(content=f"Retrieving information: {current_state}").send()
    elif current_state == "answer":
        await cl.Message(content="Generating answer based on retrieved information...").send()
    elif current_state == "planner":
        await cl.Message(content="Planning next steps...").send()
    elif current_state == "anonymize_question":
        await cl.Message(content="Anonymizing the question...").send()
    elif current_state == "de_anonymize_plan":
        await cl.Message(content="De-anonymizing the plan...").send()
    elif current_state == "break_down_plan":
        await cl.Message(content="Breaking down the plan into smaller steps...").send()
    elif current_state == "task_handler":
        await cl.Message(content="Deciding on the next action...").send()
    elif current_state == "replan":
        await cl.Message(content="Adjusting the plan based on new information...").send()
    elif current_state == "get_final_answer":
        await cl.Message(content="Preparing the final answer...").send()

    # You can add more detailed logging here if needed
    cl.Task(title=current_state, status=cl.TaskStatus.RUNNING) 