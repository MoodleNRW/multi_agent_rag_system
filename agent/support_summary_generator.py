from pydantic import BaseModel, Field
from typing import List
import chainlit as cl
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from .state import PlanExecute

class SupportSummary(BaseModel):
    """Zusammenfassung für den Supportmitarbeiter"""
    question: str = Field(description="Die ursprüngliche Frage")
    relevant_information: str = Field(
        description="Relevante Informationen, die bei der Beantwortung der Frage helfen können"
    )
    issues_encountered: str = Field(description="Aufgetretene Probleme oder Fehler")
    suggestions: str = Field(description="Vorschläge, wie weiter vorzugehen ist")
    critical_analysis: str = Field(description="Kritische Analyse des Systems und Verbesserungsvorschläge")

@cl.step(name="Support Summary", type="tool")
async def support_summary_step(state: PlanExecute):
    """
    Generiert eine Zusammenfassung für den Supportmitarbeiter basierend auf dem aktuellen Zustand.
    Args:
        state: Der aktuelle Zustand des Prozesses.
    Returns:
        Die aktualisierte Zusammenfassung für den Supportmitarbeiter.
    """
    # Definiere das Prompt-Template
    support_summary_prompt_template = """Du bist ein hilfreicher Assistent und fasst den aktuellen Zustand für einen Supportmitarbeiter zusammen.

**Wichtige Informationen für den Supportmitarbeiter:**

**Frage:** {question}

**Aktueller Zustand:**

Der aktuelle Prozess befindet sich im Zustand "{curr_state}".
{additional_state_info}

**Vergangene Schritte:**

{past_steps_info}

**Herausforderungen:**

{issues_encountered}

**Kritische Analyse:**

{critical_analysis}

**Empfehlungen:**

{suggestions}

Bitte stelle diese Zusammenfassung in Markdown-Format bereit, wobei die Struktur wie oben bleibt. Wenn möglich, füge relevante retrievte Texte hinzu, die bei der Beantwortung der Frage helfen.

"""

    # Bereite zusätzliche Informationen vor
    additional_state_info = "Es wurden mehrere Versuche unternommen, Informationen über '{query_to_retrieve_or_answer}' abzurufen, allerdings wurden nur irrelevante Daten gefunden."
    past_steps_info = "Das System hat mehrfach Informationen aus verschiedenen Quellen ({past_steps_list}) abgerufen, konnte jedoch keine relevanten Daten zu '{query_to_retrieve_or_answer}' finden."

    # Konvertiere die Liste der vergangenen Schritte in einen formatieren String
    past_steps_list = ', '.join(state["past_steps"])

    # Bereite die Inhalte für die kritische Analyse und Empfehlungen vor
    issues_encountered = "Das System konnte keine relevanten Informationen zu '{query}' finden und hat stattdessen irrelevante Daten abgerufen.".format(query=state["query_to_retrieve_or_answer"])
    critical_analysis = "Möglicherweise ist '{query}' nicht in der aktuellen Wissensbasis enthalten oder die Suchanfragen sind nicht spezifisch genug.".format(query=state["query_to_retrieve_or_answer"])
    suggestions = "Überprüfe, ob '{query}' in der Wissensbasis vorhanden ist. Erwäge, die Wissensbasis zu aktualisieren oder die Suchstrategie anzupassen.".format(query=state["query_to_retrieve_or_answer"])

    # Ersetze Platzhalter in zusätzlichen Informationen
    additional_state_info_filled = additional_state_info.format(query_to_retrieve_or_answer=state["query_to_retrieve_or_answer"])
    past_steps_info_filled = past_steps_info.format(
        past_steps_list=past_steps_list,
        query_to_retrieve_or_answer=state["query_to_retrieve_or_answer"]
    )

    # Erstelle das Prompt mit den gefüllten Variablen
    support_summary_prompt = PromptTemplate(
        template=support_summary_prompt_template,
        input_variables=[
            "curr_state",
            "question",
            "additional_state_info",
            "past_steps_info",
            "issues_encountered",
            "critical_analysis",
            "suggestions"
        ],
    )

    # LLM abrufen
    llm = get_llm()

    # Erstelle die Kette
    support_summary_chain = support_summary_prompt | llm

    # Rufe die Kette auf
    result = support_summary_chain.invoke({
        "curr_state": state["curr_state"],
        "question": state["question"],
        "additional_state_info": additional_state_info_filled,
        "past_steps_info": past_steps_info_filled,
        "issues_encountered": issues_encountered,
        "critical_analysis": critical_analysis,
        "suggestions": suggestions
    })

    # Logge die Zusammenfassung
    cl.Task(title="Support Summary", status=cl.TaskStatus.DONE)
    cl.Message(content=result.content)

    # Aktualisiere den Zustand mit der Zusammenfassung
    return result.content
