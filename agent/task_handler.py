# agent/task_handler.py

import chainlit as cl
from typing import Dict, List, Optional
from langchain.prompts import PromptTemplate
import json
from models.models_wrapper import get_llm
from pydantic import BaseModel, Field
from .state import PlanExecute

class TaskHandlerOutput(BaseModel):
    """Output schema for the task handler."""
    query: str = Field(description="The query to be either retrieved from the vector store, the question that should be answered from context or to be used to create a moodle course.")
    curr_context: str = Field(description="The context to be based on in order to answer the query or create a moodle course.")
    tool: str = Field(description="The tool to be used should be either retrieve_chunks, retrieve_summaries, retrieve_quotes, parallel_retrieval, answer or create_moodle_course.")

@cl.step(name="Task Handler", type="process")
async def run_task_handler_chain(state: PlanExecute):
    """ Run the task handler chain to decide which tool to use to execute the task.
    Args:
       state: The current state of the plan execution.
    Returns:
       The updated state of the plan execution.
    """
    state["curr_state"] = "task_handler"

    task_handler_prompt_template = """Du bist ein Task-Handler, der eine Aufgabe {curr_task} erhält und entscheiden muss, welches Tool zur Ausführung der Aufgabe verwendet werden soll.
    
    Du hast folgende Tools zur Verfügung:
    
    Tool A (retrieve_chunks): Ein Tool, das relevante Informationen aus einem Vektorspeicher von Textabschnitten basierend auf einer Abfrage abruft.
    - Verwende Tool A für detaillierte, spezifische Fragen, die präzise Informationen erfordern.
    - Gut für: technische Details, schrittweise Anleitungen, spezifische Fehlermeldungen.
    
    Tool B (retrieve_summaries): Ein Tool, das relevante Informationen aus einem Vektorspeicher von Kapitelzusammenfassungen basierend auf einer Abfrage abruft.
    - Verwende Tool B für allgemeine, überblicksartige Fragen, die einen breiteren Kontext erfordern.
    - Gut für: Konzeptüberblicke, Einführungen in Themen, Verständnis größerer Zusammenhänge.
    
    Tool C (retrieve_quotes): Ein Tool, das relevante Informationen aus einem Vektorspeicher von Zitaten basierend auf einer Abfrage abruft.
    - Verwende Tool C für Fragen nach Definitionen, Zitaten oder offiziellen Aussagen.
    - Gut für: Begriffsdefinitionen, offizielle Richtlinien, exakte Formulierungen.
    
    Tool D (parallel_retrieval): Ein Tool, das alle drei Retrieval-Methoden (Chunks, Summaries, Quotes) parallel ausführt und die Ergebnisse kombiniert.
    - Verwende Tool D für komplexe Fragen, die von verschiedenen Informationsquellen profitieren könnten.
    - Gut für: Erste Anfragen zu einem Thema, mehrteilige Fragen, Fragen mit unklarer Informationsquelle.
    
    Tool E (answer): Ein Tool, das eine Frage aus einem gegebenen Kontext beantwortet.
    - Verwende Tool E NUR, wenn du denkst, dass die aktuelle Aufgabe mit dem aggregierten Kontext {aggregated_context} beantwortet werden kann.
    
    Tool F (create_moodle_course): Ein Tool, das einen Moodle-Kurs erstellt. Du musst den Kontext für den Moodle-Kurs bereitstellen.
    - Verwende Tool F, wenn du denkst, dass die aktuelle Aufgabe einen Moodle-Kurs basierend auf dem Kontext erstellen sollte.
    
    WICHTIG: Für den ersten Informationsabruf oder wenn noch keine Informationsabruf-Tools verwendet wurden, verwende IMMER Tool D (parallel_retrieval), um einen umfassenden Überblick zu bekommen. Prüfe anhand von {past_steps} und {last_tool}, ob bereits Informationen abgerufen wurden.
    
    Du erhältst auch das zuletzt verwendete Tool {last_tool}.
    Wenn {last_tool} "retrieve_chunks", "retrieve_summaries" oder "retrieve_quotes" war und keine relevanten Informationen gefunden wurden, verwende Tool D (parallel_retrieval).
    
    Du hast auch die bisherigen Schritte {past_steps}, die du nutzen kannst, um Entscheidungen zu treffen und den Kontext der Aufgabe zu verstehen.
    Du hast auch die ursprüngliche Frage des Benutzers {question}, die du nutzen kannst, um Entscheidungen zu treffen und den Kontext der Aufgabe zu verstehen.
    
    Wenn du dich für Tool A, B, C oder D entscheidest, gib die Abfrage aus, die für das Tool verwendet werden soll, und gib auch das relevante Tool aus.
    Wenn du dich für Tool E entscheidest, gib die Frage aus, die für das Tool verwendet werden soll, den Kontext und auch, dass das zu verwendende Tool Tool E ist.
    Wenn du dich für Tool F entscheidest, gib den Kontext aus und auch, dass das zu verwendende Tool Tool F ist.
    
    Gib deine Entscheidung im JSON-Format aus.
    """

    task_handler_prompt = PromptTemplate(
        template=task_handler_prompt_template,
        input_variables=["curr_task", "aggregated_context", "last_tool", "past_steps", "question"],
    )

    task_handler_llm = get_llm()
    task_handler_chain = task_handler_prompt | task_handler_llm.with_structured_output(
        TaskHandlerOutput,  
        method="function_calling",  # Explizit function_calling verwenden
        strict=True
    )

    if not state["plan"]:
        # If there are no more steps in the plan, we're done
        state["tool"] = "done"
        return

    curr_task = state["plan"].pop(0)  # Get the next task and remove it from the plan
    
    result = task_handler_chain.invoke({
        "curr_task": curr_task,
        "aggregated_context": state["aggregated_context"],
        "last_tool": state.get("tool", ""),
        "past_steps": state["past_steps"],
        "question": state["question"]
    })

    state["query_to_retrieve_or_answer"] = result.query

    # Überprüfe, ob ein gültiges Tool zurückgegeben wurde
    valid_tools = ["retrieve_chunks", "retrieve_summaries", "retrieve_quotes", "parallel_retrieval", "answer", "create_moodle_course"]
    
    if not result.tool or result.tool.strip() == "" or result.tool not in valid_tools:
        # Wenn kein gültiges Tool zurückgegeben wurde, verwende standardmäßig parallel_retrieval
        await cl.Message(content=f"⚠️ Kein gültiges Tool erkannt. Verwende standardmäßig paralleles Retrieval.").send()
        result.tool = "parallel_retrieval"
    
    # Prüfe, ob bereits ein Retrieval-Tool verwendet wurde
    retrieval_tools = ["retrieve_chunks", "retrieve_summaries", "retrieve_quotes", "parallel_retrieval"]
    past_retrieval_tools = [step for step in state.get("past_tool_usage", []) if step in retrieval_tools]
    
    # Wenn noch kein Retrieval-Tool verwendet wurde und das ausgewählte Tool ein Retrieval-Tool ist,
    # verwende standardmäßig parallel_retrieval für den ersten Retrieval-Schritt
    if not past_retrieval_tools and result.tool in retrieval_tools and result.tool != "parallel_retrieval":
        await cl.Message(content=f"🔄 Erster Informationsabruf: Verwende paralleles Retrieval anstelle von {result.tool}").send()
        result.tool = "parallel_retrieval"
    
    # Aktualisiere die Liste der verwendeten Tools
    if "past_tool_usage" not in state:
        state["past_tool_usage"] = []
    state["past_tool_usage"].append(result.tool)
    
    if result.tool == "answer":
        state["curr_context"] = result.curr_context  
        state["tool"] = "answer"
    else:
        state["tool"] = result.tool

         
    state["past_steps"].append(curr_task)

    # Log the decision for debugging
    cl.Task(title=f"Task: {curr_task}", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Chosen Tool: {state['tool']}", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Query: {state['query_to_retrieve_or_answer']}", status=cl.TaskStatus.DONE)

    return state