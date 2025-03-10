# agent/answerer.py

import chainlit as cl
import asyncio
from typing import List, Tuple, Dict
from .state import PlanExecute
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langsmith import traceable
import time

class QuestionAnswerFromContext(BaseModel):
    """
    Output-Schema für die Antwortgenerierung.
    """
    reasoning: str = Field(description="Der Gedankengang zur Beantwortung der Frage.")
    answer_based_on_content: str = Field(description="Die endgültige Antwort auf die Frage, basierend auf dem Kontext.")


@traceable(pass_config=False)
@cl.step(name="Generate Answer", type="tool")
async def run_qualtative_answer_workflow(state: PlanExecute):
    """
    Generiert eine Antwort auf eine Frage basierend auf dem bereitgestellten Kontext.
    
    Args:
        state: Der aktuelle Zustand der Planausführung.
        
    Returns:
        Der aktualisierte Zustand mit der generierten Antwort.
    """
    state["curr_state"] = "answer"
    
    question_answer_cot_prompt_template = """
    # Beispiele für Chain-of-Thought-Reasoning

    ## Beispiel 1
    Kontext: Maria ist größer als Jana. Jana ist kleiner als Tom. Tom ist gleich groß wie David.
    Frage: Wer ist die größte Person?
    Gedankengang:
    Der Kontext sagt uns, dass Maria größer als Jana ist.
    Es heißt auch, dass Jana kleiner als Tom ist.
    Und Tom ist gleich groß wie David.
    Die Reihenfolge von groß nach klein ist also: Maria, Tom/David, Jana.
    Daher muss Maria die größte Person sein.

    ## Beispiel 2
    Kontext: In der Moodle-Dokumentation wird beschrieben, dass Kurse in Kategorien organisiert werden können. Administratoren können Kategorien erstellen und Kursleiter können ihre Kurse in diesen Kategorien platzieren. Außerdem können Kurse verschiedene Formate haben, wie z.B. Wochenformat oder Themenformat.
    Frage: Wie organisiert Moodle Kurse?
    Gedankengang:
    Der Kontext beschreibt, wie Kurse in Moodle organisiert werden.
    Es wird erwähnt, dass Kurse in Kategorien organisiert werden können.
    Administratoren können diese Kategorien erstellen.
    Kursleiter können dann ihre Kurse in diesen Kategorien platzieren.
    Zusätzlich können Kurse verschiedene Formate haben, wie Wochen- oder Themenformat.
    Die Antwort ist also: Moodle organisiert Kurse in Kategorien, die von Administratoren erstellt werden, und Kurse können verschiedene Formate wie Wochen- oder Themenformat haben.

    ## Beispiel 3
    Kontext: Die Moodle-Plattform wurde 2002 von Martin Dougiamas gegründet.
    Frage: Wann wurde die Moodle-App für iOS veröffentlicht?
    Gedankengang:
    Der Kontext enthält nur Informationen darüber, wann Moodle gegründet wurde (2002) und von wem (Martin Dougiamas).
    Es gibt keine Informationen darüber, wann die Moodle-App für iOS veröffentlicht wurde.
    Ohne zusätzlichen Kontext kann diese Frage nicht beantwortet werden.
    
    Wende Chain-of-Thought-Reasoning auf die folgende Frage an. Arbeite schrittweise und beantworte die Frage, nur wenn ausreichend Informationen im Kontext vorhanden sind.
    
    Kontext:
    {context}
    
    Frage:
    {question}
    """
    
    question = state["query_to_retrieve_or_answer"]
    context = state["curr_context"] if "curr_context" in state else state["aggregated_context"]
    
    question_answer_cot_prompt = PromptTemplate(
        template=question_answer_cot_prompt_template,
        input_variables=["context", "question"],
    )
    
    llm = get_llm(temperature=0)
    chain = question_answer_cot_prompt | llm.with_structured_output(
        QuestionAnswerFromContext,
        method="function_calling",
        strict=True
    )
    
    await cl.Message(content=f"Beantworte die Frage mit Chain-of-Thought-Reasoning: '{question}'").send()
    
    start_time = time.time()
    result = chain.invoke({"context": context, "question": question})
    end_time = time.time()
    
    state["answer"] = result.answer_based_on_content
    
    # Zeige den Gedankengang an
    thought_msg = cl.Message(content=f"**Gedankengang:**\n\n{result.reasoning}")
    thought_msg.language = "markdown"
    await thought_msg.send()
    
    # Zeige die Antwort an
    answer_msg = cl.Message(content=f"**Antwort:**\n\n{result.answer_based_on_content}")
    answer_msg.language = "markdown"
    await answer_msg.send()
    
    await cl.Message(content=f"⏱️ Antwort in {round(end_time - start_time, 2)} Sekunden generiert").send()
    
    return state

@traceable(pass_config=False)
@cl.step(name="Generate Final Answer", type="tool")
async def run_qualtative_answer_workflow_for_final_answer(state: PlanExecute):
    """
    Generiert eine finale Antwort auf die ursprüngliche Frage basierend auf dem gesammelten Kontext.
    
    Args:
        state: Der aktuelle Zustand der Planausführung.
        
    Returns:
        Der aktualisierte Zustand mit der generierten Antwort.
    """
    state["curr_state"] = "get_final_answer"
    
    final_answer_cot_prompt_template = """
    # Finale Antwort generieren

    Du bist ein Experte für Moodle und sollst eine fundierte, präzise Antwort auf die Frage geben.
    
    Verwende den folgenden strukturierten Ansatz:
    
    1. Verstehen der Frage: Analysiere die Frage sorgfältig
    2. Analyse des Kontexts: Identifiziere alle relevanten Informationen im Kontext
    3. Bewertung der Informationsqualität: Prüfe, ob der Kontext ausreichend Informationen enthält
    4. Strukturierte Antwortentwicklung: Baue eine klare, präzise Antwort auf
    5. Selbstüberprüfung: Stelle sicher, dass die Antwort durch den Kontext gestützt wird
    
    Bitte beantworte die folgende Frage, indem du zuerst deinen schrittweisen Denkprozess aufzeigst und dann eine endgültige Antwort formulierst.
    
    WICHTIG: Erwähne NICHT, dass du diese Informationen "aus dem Kontext" hast. Formuliere die Antwort, als wärst du ein Moodle-Experte, der direkt antwortet.
    
    WICHTIG: Wenn die Frage nicht beantwortet werden kann, erkläre klar, warum nicht und was für Informationen fehlen.
    
    Kontext:
    {context}
    
    Frage:
    {question}
    """
    
    question = state["question"]  # Die ursprüngliche Frage verwenden
    context = state["aggregated_context"]
    
    final_answer_cot_prompt = PromptTemplate(
        template=final_answer_cot_prompt_template,
        input_variables=["context", "question"],
    )
    
    llm = get_llm(temperature=0)
    chain = final_answer_cot_prompt | llm.with_structured_output(
        QuestionAnswerFromContext,
        method="function_calling",
        strict=True
    )
    
    await cl.Message(content=f"🎯 Generiere finale Antwort auf die ursprüngliche Frage: '{question}'").send()
    
    start_time = time.time()
    result = chain.invoke({"context": context, "question": question})
    end_time = time.time()
    
    state["response"] = result.answer_based_on_content
    
    # Zeige den Gedankengang intern
    thought_msg = cl.Message(content=f"**Interner Gedankengang:**\n\n{result.reasoning}")
    #thought_msg.language = "markdown"
    thought_msg.type = "system"
    await thought_msg.send()
    
    # Zeige die finale Antwort mit besonderer Formatierung
    answer_msg = cl.Message(content=result.answer_based_on_content)
    answer_msg.language = "Antwort"
    answer_msg.parent_id = None
    await answer_msg.send()
    
    await cl.Message(content=f"⏱️ Finale Antwort in {round(end_time - start_time, 2)} Sekunden generiert").send()
    
    return state