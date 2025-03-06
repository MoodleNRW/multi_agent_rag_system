"""
UI-Komponenten für die RAGAS-Evaluierung.
"""

import chainlit as cl
import json
import os
from typing import List, Dict, Any
import asyncio

from evaluation.ragas_evaluator import evaluate_conversation, display_evaluation_results

async def show_evaluation_option():
    """
    Zeigt eine Schaltfläche zur Durchführung der RAGAS-Evaluierung an.
    """
    msg = cl.Message(content="📊 **RAGAS-Evaluierung**\n\nFühren Sie eine Evaluierung des RAG-Systems mit RAGAS-Metriken durch. Sie können entweder eine Testdatendatei hochladen oder die aktuelle Konversation evaluieren.")
    
    actions = [
        cl.Action(name="upload_test_data", payload={"action": "upload"}, label="📤 Testdaten hochladen"),
        cl.Action(name="evaluate_conversation", payload={"action": "evaluate"}, label="🔍 Aktuelle Konversation evaluieren")
    ]
    
    msg.actions = actions
    await msg.send()

@cl.action_callback("upload_test_data")
async def on_upload_test_data(action):
    """
    Callback für die Aktion 'Testdaten hochladen'.
    """
    await action.remove()
    
    # Zeige Datei-Upload-Element an
    await cl.Message(content="Bitte laden Sie eine JSON-Datei mit Testdaten hoch. Die Datei sollte Listen für 'questions', 'answers', 'contexts' und optional 'ground_truths' enthalten.").send()
    
    file_element = cl.File(
        name="test_data.json",
        display="inline",
        accept=["application/json"],
        max_files=1
    )
    
    msg = cl.Message(content="", elements=[file_element])
    await msg.send()

@cl.on_file_upload(accept=["application/json"])
async def on_file_upload(file: cl.File):
    """
    Callback für den Upload einer JSON-Datei.
    """
    try:
        # Lese die hochgeladene Datei
        content = file.content.decode("utf-8")
        test_data = json.loads(content)
        
        # Überprüfe, ob die erforderlichen Felder vorhanden sind
        if not all(key in test_data for key in ["questions", "answers", "contexts"]):
            await cl.Message(content="⚠️ Die hochgeladene Datei enthält nicht alle erforderlichen Felder (questions, answers, contexts).").send()
            return
        
        # Führe die Evaluierung durch
        await cl.Message(content=f"🔄 Starte Evaluierung mit {len(test_data['questions'])} Testfällen...").send()
        
        questions = test_data["questions"]
        answers = test_data["answers"]
        contexts = test_data["contexts"]
        ground_truths = test_data.get("ground_truths")
        
        # Führe die Evaluierung durch
        await evaluate_conversation(questions, answers, contexts, ground_truths)
        
    except json.JSONDecodeError:
        await cl.Message(content="⚠️ Die hochgeladene Datei enthält kein gültiges JSON.").send()
    except Exception as e:
        await cl.Message(content=f"⚠️ Fehler bei der Evaluierung: {str(e)}").send()

@cl.action_callback("evaluate_conversation")
async def on_evaluate_conversation(action):
    """
    Callback für die Aktion 'Aktuelle Konversation evaluieren'.
    """
    await action.remove()
    
    # Hole die Konversationshistorie
    conversation_history = cl.user_session.get("conversation_history", [])
    
    if not conversation_history:
        await cl.Message(content="⚠️ Es gibt keine Konversationshistorie zum Evaluieren. Bitte stellen Sie zuerst einige Fragen.").send()
        return
    
    # Extrahiere Fragen, Antworten und Kontexte aus der Konversationshistorie
    questions = []
    answers = []
    contexts = []
    
    for item in conversation_history:
        if all(key in item for key in ["question", "answer", "context"]):
            questions.append(item["question"])
            answers.append(item["answer"])
            contexts.append(item["context"])
    
    if not questions:
        await cl.Message(content="⚠️ Es wurden keine vollständigen Frage-Antwort-Paare in der Konversationshistorie gefunden.").send()
        return
    
    # Führe die Evaluierung durch
    await cl.Message(content=f"🔄 Starte Evaluierung mit {len(questions)} Frage-Antwort-Paaren aus der Konversationshistorie...").send()
    
    # Führe die Evaluierung durch
    await evaluate_conversation(questions, answers, contexts)

def store_conversation_item(question: str, answer: str, context: str):
    """
    Speichert ein Frage-Antwort-Paar in der Konversationshistorie.
    
    Args:
        question: Die Frage
        answer: Die Antwort
        context: Der Kontext
    """
    conversation_history = cl.user_session.get("conversation_history", [])
    
    conversation_history.append({
        "question": question,
        "answer": answer,
        "context": context
    })
    
    cl.user_session.set("conversation_history", conversation_history)

async def add_evaluation_button():
    """
    Fügt einen Evaluierungsbutton zur UI hinzu.
    """
    eval_button = cl.Action(
        name="show_evaluation",
        payload={"action": "show"},
        label="📊 RAGAS-Evaluierung"
    )
    
    msg = cl.Message(content="")
    msg.actions = [eval_button]
    await msg.send()

@cl.action_callback("show_evaluation")
async def on_show_evaluation(action):
    """
    Callback für die Aktion 'RAGAS-Evaluierung anzeigen'.
    """
    await action.remove()
    await show_evaluation_option() 