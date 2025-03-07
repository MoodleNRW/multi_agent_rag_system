# agent/answerer.py

import chainlit as cl
import asyncio
from typing import List, Tuple, Dict
from .state import PlanExecute
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

class QuestionAnswerFromContext(BaseModel):
    """
    Output-Schema für die Antwortgenerierung.
    """
    reasoning: str = Field(description="Der Gedankengang zur Beantwortung der Frage.")
    answer_based_on_content: str = Field(description="Die endgültige Antwort auf die Frage, basierend auf dem Kontext.")

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
    **Kontext**: Maria ist größer als Jana. Jana ist kleiner als Tom. Tom ist genauso groß wie David.
    **Frage**: Wer ist die größte Person?
    **Gedankengang**:
    Der Kontext sagt uns, dass Maria größer als Jana ist.
    Es wird auch gesagt, dass Jana kleiner als Tom ist.
    Und Tom ist genauso groß wie David.
    Die Reihenfolge von groß nach klein ist also: Maria, Tom/David, Jana.
    Daher muss Maria die größte Person sein.
    **Antwort**: Maria ist die größte Person.

    ## Beispiel 2
    **Kontext**: Harry las ein Buch über Zaubersprüche. Ein Zauberspruch erlaubte es dem Zauberer, eine Person für kurze Zeit in ein Tier zu verwandeln. Ein anderer Zauberspruch konnte Objekte schweben lassen. Ein dritter Zauberspruch erzeugte ein helles Licht am Ende des Zauberstabs des Zauberers.
    **Frage**: Was könnte Harry tun, wenn er diese Zaubersprüche anwenden würde?
    **Gedankengang**:
    Der Kontext beschreibt drei verschiedene Zaubersprüche.
    Der erste Zauberspruch ermöglicht es, eine Person vorübergehend in ein Tier zu verwandeln.
    Der zweite Zauberspruch kann Objekte schweben lassen.
    Der dritte Zauberspruch erzeugt ein helles Licht.
    Wenn Harry diese Zaubersprüche anwenden würde, könnte er jemanden für eine Weile in ein Tier verwandeln, Objekte schweben lassen und eine helle Lichtquelle erzeugen.
    **Antwort**: Basierend auf dem Kontext könnte Harry, wenn er diese Zaubersprüche anwenden würde, Menschen in Tiere verwandeln, Dinge schweben lassen und einen Bereich beleuchten.

    ## Beispiel 3
    **Kontext**: Harry Potter wachte an seinem Geburtstag auf und fand ein Geschenk am Ende seines Bettes. Er öffnete es aufgeregt und fand einen Nimbus 2000 Besen.
    **Frage**: Warum erhielt Harry einen Besen zum Geburtstag?
    **Gedankengang**:
    Der Kontext besagt, dass Harry Potter an seinem Geburtstag aufwachte und ein Geschenk erhielt - einen Nimbus 2000 Besen.
    Allerdings enthält der Kontext keine Informationen darüber, warum er dieses spezifische Geschenk erhielt oder wer es ihm gab.
    Es gibt keine Details über Harrys Interessen, Hobbys oder die Motivation des Schenkenden.
    Ohne zusätzlichen Kontext über Harrys Hintergrund oder die Motivation des Schenkenden gibt es keine Möglichkeit, den Grund zu bestimmen, warum er einen Besen als Geburtstagsgeschenk erhielt.
    **Antwort**: Basierend auf dem gegebenen Kontext kann ich nicht bestimmen, warum Harry einen Besen zum Geburtstag erhielt. Der Kontext erwähnt nur, dass er einen Nimbus 2000 Besen bekam, aber nicht den Grund dafür oder wer ihn geschenkt hat.

    # Deine Aufgabe
    Beantworte die folgende Frage, indem du zuerst deinen Gedankengang Schritt für Schritt darlegst und dann eine endgültige Antwort gibst.

    **Kontext**:
    {context}

    **Frage**:
    {question}

    Gib deine Antwort in einem strukturierten Format zurück:
    - reasoning: Dein ausführlicher Gedankengang zur Beantwortung der Frage
    - answer_based_on_content: Die endgültige Antwort auf die Frage, basierend auf dem Kontext
    """
    
    question_answer_from_context_cot_prompt = PromptTemplate(
        template=question_answer_cot_prompt_template,
        input_variables=["context", "question"],
    )
    
    question_answer_from_context_llm = get_llm(temperature=0)
    question_answer_from_context_cot_chain = question_answer_from_context_cot_prompt | question_answer_from_context_llm.with_structured_output(
        QuestionAnswerFromContext, 
        method="function_calling",
        strict=True
    )
    
    response = question_answer_from_context_cot_chain.invoke({
        "context": state["curr_context"],
        "question": state["query_to_retrieve_or_answer"]
    })
    
    # Speichere sowohl den Gedankengang als auch die Antwort
    state["reasoning"] = response.reasoning
    state["response"] = response.answer_based_on_content
    
    # Füge den Gedankengang und die Antwort zum aggregierten Kontext hinzu
    state["aggregated_context"] += f"\n\nGedankengang:\n{response.reasoning}\n\nGenerierte Antwort:\n{response.answer_based_on_content}"
    
    # Zeige den Gedankengang in der UI an
    await cl.Message(content=f"🧠 **Gedankengang**:\n\n{response.reasoning}").send()
    
    return state

@cl.step(name="Generate Final Answer", type="tool")
async def run_qualtative_answer_workflow_for_final_answer(state: PlanExecute):
    """
    Generiert eine endgültige Antwort auf die ursprüngliche Frage basierend auf allen gesammelten Informationen.
    
    Args:
        state: Der aktuelle Zustand der Planausführung.
        
    Returns:
        Der aktualisierte Zustand mit der endgültigen Antwort.
    """
    state["curr_state"] = "get_final_answer"
    
    final_answer_prompt_template = """
    # Aufgabe: Endgültige Antwort generieren

    Basierend auf allen gesammelten Informationen, erstelle eine endgültige, umfassende Antwort auf die ursprüngliche Frage.

    **Ursprüngliche Frage**: 
    {question}

    **Gesammelte Informationen**: 
    {aggregated_context}

    ## Anweisungen:
    1. Analysiere alle gesammelten Informationen sorgfältig.
    2. Führe einen strukturierten Gedankengang durch, um die Frage zu beantworten.
    3. Synthetisiere die Informationen zu einer detaillierten, präzisen und vollständigen Antwort.
    4. Behalte URLs und Verweise auf die Originalquellen in der Antwort bei.
    5. Wenn die Informationen nicht ausreichen, um die Frage vollständig zu beantworten, gib an, welche Aspekte nicht beantwortet werden können.

    Gib deine Antwort in einem strukturierten Format zurück:
    - reasoning: Dein ausführlicher Gedankengang zur Beantwortung der Frage
    - answer_based_on_content: Die endgültige Antwort auf die Frage, basierend auf allen gesammelten Informationen
    """
    
    final_answer_prompt = PromptTemplate(
        template=final_answer_prompt_template,
        input_variables=["question", "aggregated_context"],
    )
    
    final_answer_llm = get_llm(temperature=0)
    final_answer_chain = final_answer_prompt | final_answer_llm.with_structured_output(
        QuestionAnswerFromContext, 
        method="function_calling",
        strict=True
    )
    
    response = final_answer_chain.invoke({
        "question": state["question"],
        "aggregated_context": state["aggregated_context"]
    })
    
    # Speichere sowohl den Gedankengang als auch die Antwort
    state["final_reasoning"] = response.reasoning
    state["response"] = response.answer_based_on_content
    
    # Zeige den Gedankengang in der UI an
    await cl.Message(content=f"🧠 **Finaler Gedankengang**:\n\n{response.reasoning}").send()
    
    return state