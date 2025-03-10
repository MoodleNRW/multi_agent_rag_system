# agent/graph.py

import chainlit as cl
from langgraph.graph import StateGraph, END
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from langsmith import traceable


from pydantic import BaseModel, Field
from typing import List

from .state import PlanExecute
from .anonymizer import anonymize_queries, deanonymize_queries
from .task_handler import run_task_handler_chain
from .retriever import (
    run_qualitative_chunks_retrieval_workflow,
    run_qualitative_summaries_retrieval_workflow,
    run_qualitative_quotes_retrieval_workflow,
    run_parallel_retrieval_workflow,
    run_faq_check_workflow,
    check_content_grounding
)
from .tools import run_moodle_tool_workflow
from .answerer import run_qualtative_answer_workflow, run_qualtative_answer_workflow_for_final_answer
from .verifier import can_be_answered
from .hallucination_checker import is_answer_grounded_on_context
from .relevance_checker import is_relevant_content

    # Definiere das Output-Schema
class KeepRelevantContent(BaseModel):
    relevant_content: str = Field(description="Der relevante Inhalt aus den abgerufenen Dokumenten, der für die Anfrage relevant ist.")
    
# Neuer gemeinsamer Node für die Relevanzprüfung nach dem Retrieval
@traceable(pass_config=False)
@cl.step(name="Keep Only Relevant Content", type="process")
async def keep_only_relevant_content(state: PlanExecute):
    """
    Behält nur den relevanten Inhalt aus den abgerufenen Dokumenten.
    
    Args:
        state: Der aktuelle Zustand der Plan-Ausführung.
    Returns:
        Der aktualisierte Zustand mit dem relevanten Inhalt.
    """
    state["curr_state"] = "keep_only_relevant_content"
    
    # Extrahiere die benötigten Felder aus dem Zustand
    question = state["question"]
    context = state["context"] if "context" in state else state["aggregated_context"]
    
    # Prompt-Template für die Filterung relevanter Inhalte
    keep_only_relevant_content_prompt_template = """Du erhältst eine Anfrage: {query} und abgerufene Dokumente: {retrieved_documents} aus einem Vektorspeicher.
    Du musst alle nicht relevanten Informationen herausfiltern, die keine wichtigen Informationen zur {query} liefern.
    Dein Ziel ist es lediglich, die nicht relevanten Informationen herauszufiltern.
    Du kannst Teile von Sätzen entfernen, die nicht relevant für die Anfrage sind, oder ganze Sätze, die nicht relevant für die Anfrage sind.
    FÜGE KEINE NEUEN INFORMATIONEN HINZU, DIE NICHT IN DEN ABGERUFENEN DOKUMENTEN ENTHALTEN SIND.
    Gib nur den gefilterten relevanten Inhalt aus.
    """
    
    keep_only_relevant_content_prompt = PromptTemplate(
        template=keep_only_relevant_content_prompt_template,
        input_variables=["query", "retrieved_documents"],
    )
    
    keep_only_relevant_content_llm = get_llm(temperature=0)
    keep_only_relevant_content_chain = keep_only_relevant_content_prompt | keep_only_relevant_content_llm.with_structured_output(
        KeepRelevantContent, 
        method="function_calling",
        strict=True
    )
    
    # Eingabedaten für das LLM-Modell
    input_data = {
        "query": question,
        "retrieved_documents": context
    }
    
    # Aufruf des LLM zur Filterung der Inhalte
    await cl.Message(content=f"Behalte nur relevante Inhalte für die Anfrage: '{question}'").send()
    output = keep_only_relevant_content_chain.invoke(input_data)
    relevant_content = output.relevant_content
    
    # Prüfe, ob der relevante Inhalt im ursprünglichen Kontext verankert ist
    is_grounded = await check_content_grounding(relevant_content, context)
    
    # Wenn der Inhalt nicht verankert ist, wiederholen wir die Anfrage mit einem angepassten Prompt
    if not is_grounded and relevant_content.strip():
        await cl.Message(content="Der gefilterte Inhalt enthält möglicherweise nicht im Original enthaltene Informationen. Versuche erneut zu filtern...").send()
        
        # Modifiziertes Prompt für strengere Filterung
        stricter_prompt_template = """Du erhältst eine Anfrage: {query} und abgerufene Dokumente: {retrieved_documents} aus einem Vektorspeicher.
        WICHTIG: Deine Ausgabe darf AUSSCHLIESSLICH Informationen enthalten, die wortwörtlich oder sinngemäß in den abgerufenen Dokumenten vorhanden sind.
        
        Filtere alle nicht relevanten Informationen heraus, die keine wichtigen Informationen zur {query} liefern.
        Du kannst Teile von Sätzen oder ganze Sätze entfernen, die nicht relevant für die Anfrage sind.
        Stelle sicher, dass jede Information in deiner Ausgabe direkt aus den abgerufenen Dokumenten stammt.
        Gib nur den gefilterten relevanten Inhalt aus.
        """
        
        stricter_prompt = PromptTemplate(
            template=stricter_prompt_template,
            input_variables=["query", "retrieved_documents"],
        )
        
        stricter_chain = stricter_prompt | keep_only_relevant_content_llm.with_structured_output(
            KeepRelevantContent, 
            method="function_calling",
            strict=True
        )
        
        output = stricter_chain.invoke(input_data)
        relevant_content = output.relevant_content
    
    # Speichere den gefilterten Inhalt im Zustand
    if not "aggregated_context" in state or state["aggregated_context"] == "":
        state["aggregated_context"] = relevant_content
    else:
        state["aggregated_context"] += f"\n\n{relevant_content}"
    
    # Ist der gefilterte Inhalt leer (keine relevanten Inhalte gefunden)?
    if not relevant_content.strip():
        await cl.Message(content="Keine relevanten Inhalte gefunden. Versuche mit anderen Quellen.").send()
        state["relevance_status"] = "not_grounded_on_the_original_context"
        
        # Bei keinen relevanten Inhalten wechsle zur nächsten Abrufmethode
        if state["tool"] == "retrieve_chunks":
            state["tool"] = "retrieve_summaries"
        elif state["tool"] == "retrieve_summaries":
            state["tool"] = "retrieve_quotes"
        elif state["tool"] == "retrieve_quotes" or state["tool"] == "parallel_retrieval":
            # Wenn alle einzelnen Retrieval-Methoden und paralleles Retrieval keine relevanten Ergebnisse liefern,
            # versuche es mit einer allgemeineren Abfrage im parallelen Retrieval
            state["tool"] = "parallel_retrieval"
            # Generalisiere die Abfrage
            state["query_to_retrieve_or_answer"] = f"Allgemeine Informationen zu: {question}"
    else:
        await cl.Message(content=f"Relevante Inhalte gefunden und zum Kontext hinzugefügt.").send()
        state["relevance_status"] = "grounded_on_the_original_context"
    
    # Gebe den aktualisierten Zustand zurück
    return state

async def create_agent_graph():
    agent_workflow = StateGraph(PlanExecute)

    # Add nodes
    agent_workflow.add_node("anonymize_question", anonymize_queries)
    agent_workflow.add_node("planner", plan_step)
    agent_workflow.add_node("break_down_plan_to_retrieve_or_answer", break_down_plan_step)
    agent_workflow.add_node("de_anonymize_plan", deanonymize_queries)
    agent_workflow.add_node("task_handler", run_task_handler_chain)
    agent_workflow.add_node("check_faq", run_faq_check_workflow)
    agent_workflow.add_node("retrieve_chunks", run_qualitative_chunks_retrieval_workflow)
    agent_workflow.add_node("retrieve_summaries", run_qualitative_summaries_retrieval_workflow)
    agent_workflow.add_node("retrieve_quotes", run_qualitative_quotes_retrieval_workflow)
    agent_workflow.add_node("parallel_retrieval", run_parallel_retrieval_workflow)
    agent_workflow.add_node("call_moodle_tool", run_moodle_tool_workflow)
    agent_workflow.add_node("answer", run_qualtative_answer_workflow)
    agent_workflow.add_node("get_final_answer", run_qualtative_answer_workflow_for_final_answer)
    agent_workflow.add_node("rewrite_question", rewrite_question)
    agent_workflow.add_node("check_hallucination", check_answer_hallucination)
    agent_workflow.add_node("keep_only_relevant_content", keep_only_relevant_content)
    agent_workflow.add_node("replan", replan_step)
    agent_workflow.add_node("decide_faq_path", decide_faq_path)

    # Set entry point
    agent_workflow.set_entry_point("anonymize_question")

    # Add edges
    agent_workflow.add_edge("anonymize_question", "planner")
    agent_workflow.add_edge("planner", "de_anonymize_plan")
    agent_workflow.add_edge("de_anonymize_plan", "break_down_plan_to_retrieve_or_answer")
    agent_workflow.add_edge("break_down_plan_to_retrieve_or_answer", "task_handler")

    # Add conditional edges for task handler
    agent_workflow.add_conditional_edges(
        "task_handler",
        retrieve_or_answer,
        {
            "chosen_tool_is_check_faq": "check_faq",
            "chosen_tool_is_retrieve_chunks": "retrieve_chunks",
            "chosen_tool_is_retrieve_summaries": "retrieve_summaries",
            "chosen_tool_is_retrieve_quotes": "retrieve_quotes",
            "chosen_tool_is_parallel_retrieval": "parallel_retrieval",
            "chosen_tool_is_create_moodle_course": "call_moodle_tool",
            "chosen_tool_is_answer": "answer"
        }
    )

    # Konditionale Kanten für den neu hinzugefügten keep_only_relevant_content Node
    agent_workflow.add_conditional_edges(
        "keep_only_relevant_content",
        lambda x: x["relevance_status"],
        {
            "grounded_on_the_original_context": "replan",
            "not_grounded_on_the_original_context": "rewrite_question"
        }
    )

    # Ändere die Halluzinationsprüfung, um den neuen check_hallucination-Knoten zu nutzen
    agent_workflow.add_conditional_edges(
        "answer",
        check_answer_hallucination,
        {
            "grounded_on_context": "replan",
            "hallucination": "rewrite_question"
        }
    )

    # Kante vom rewrite_question zurück zum task_handler
    agent_workflow.add_edge("rewrite_question", "task_handler")

    agent_workflow.add_edge("call_moodle_tool", "replan")

    # Add conditional edges for replan
    agent_workflow.add_conditional_edges(
        "replan",
        can_be_answered,
        {
            "can_be_answered_already": "get_final_answer",
            "cannot_be_answered_yet": "break_down_plan_to_retrieve_or_answer"
        }
    )

    # Add conditional edges for final answer hallucination check
    agent_workflow.add_conditional_edges(
        "get_final_answer",
        check_answer_hallucination,
        {
            "grounded_on_context": END,
            "hallucination": "replan"
        }
    )

    # Füge die Entscheidungsfunktion zum Workflow hinzu
    agent_workflow.add_edge("check_faq", "decide_faq_path")
    agent_workflow.add_conditional_edges(
        "decide_faq_path",
        lambda x: x["routing"],
        {
            "direct_to_answer": END,
            "back_to_task_handler": "task_handler"
        }
    )

    # Neue einheitliche Kanten für das Retrieval
    agent_workflow.add_edge("retrieve_chunks", "keep_only_relevant_content")
    agent_workflow.add_edge("retrieve_summaries", "keep_only_relevant_content")
    agent_workflow.add_edge("retrieve_quotes", "keep_only_relevant_content")
    agent_workflow.add_edge("parallel_retrieval", "keep_only_relevant_content")

    return agent_workflow

async def compile_workflow():
    graph = await create_agent_graph()
    workflow = graph.compile()
    return workflow

#todo move to a separate file
class Plan(BaseModel):
    """Plan to follow in future"""
    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )
@traceable(pass_config=False)
@cl.step(name="Plan Step", type="process")
async def plan_step(state: PlanExecute):
    """
    Plans the next step.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the plan.
    """
    state["curr_state"] = "planner"

    planner_prompt = """For the given query {question}, come up with a simple step by step plan of how to figure out the answer. 
    
    This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. 
    If the question is very simple and can be answered directly, the plan should only include a single step to answer the question.
    The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.

    Output the plan as a list of steps in JSON format.
    """

    planner_prompt = PromptTemplate(
        template=planner_prompt,
        input_variables=["question"], 
    )

    planner_llm = get_llm()

    planner = planner_prompt | planner_llm.with_structured_output(
        Plan, 
        method="function_calling",
        strict=True
    )

    result = planner.invoke({"question": state["anonymized_question"]})

    state["plan"] = result.steps

    return state

@traceable(pass_config=False)
@cl.step(name="Break Down Plan", type="process")
async def break_down_plan_step(state: PlanExecute):
    """
    Breaks down the plan steps into retrievable or answerable tasks.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the refined plan.
    """
    state["curr_state"] = "break_down_plan"

    break_down_plan_prompt_template = """You receive a plan {plan} which contains a series of steps to follow in order to answer a query. 
    You need to go through the plan and refine it according to these criteria:
    1. Every step has to be able to be executed by either:
        i. checking the FAQ database for a matching answer
        ii. retrieving relevant information from a vector store of chunks
        iii. retrieving relevant information from a vector store of chapter summaries
        iv. retrieving relevant information from a vector store of quotes
        v. answering a question from a given context.
        vi. creating a moodle course.
    2. Every step should contain all the information needed to execute it.
    3. Break down any step that is too broad or complex into multiple, more specific steps.
    4. Ensure that the steps are in a logical order and build upon each other.
    5. The final step should always be about synthesizing the information to answer the original question.

    Output the refined plan as a list of detailed steps in JSON format.
    """

    break_down_plan_prompt = PromptTemplate(
        template=break_down_plan_prompt_template,
        input_variables=["plan"],
    )

    break_down_plan_llm = get_llm()
    break_down_plan_chain = break_down_plan_prompt | break_down_plan_llm.with_structured_output(
        Plan,  
        method="function_calling",
        strict=True
    )

    result = break_down_plan_chain.invoke({"plan": state["plan"]})

    state["plan"] = result.steps
    
    # Setze standardmäßig das parallel_retrieval Tool für den ersten Schritt
    state["tool"] = "parallel_retrieval"
    
    # Log für Debugging
    await cl.Message(content=f"🔄 Standardmäßig wird mit paralleler Retrieval-Methode begonnen").send()

    return state

@traceable(pass_config=False)
@cl.step(name="Replan", type="process")
async def replan_step(state: PlanExecute):
    """
    Replans the next step.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the plan.
    """
    state["curr_state"] = "replan"

    replan_prompt_template = """Given the current state of our question-answering process, we need to update our plan.

    Original question: {question}
    Current plan: {plan}
    Steps completed: {past_steps}
    Current aggregated context: {aggregated_context}

    Based on this information, please update the plan. If further steps are needed, provide only those steps.
    Do not include steps that have already been completed.
    If the question can be fully answered with the current information, the plan should only include a step to formulate the final answer.

    Output the updated plan as a list of steps in JSON format.
    """

    replan_prompt = PromptTemplate(
        template=replan_prompt_template,
        input_variables=["question", "plan", "past_steps", "aggregated_context"],
    )

    replan_llm = get_llm()
    replan_chain = replan_prompt | replan_llm.with_structured_output(
        Plan,  
        method="function_calling",
        strict=True
    )

    result = replan_chain.invoke({
        "question": state["question"],
        "plan": state["plan"],
        "past_steps": state["past_steps"],
        "aggregated_context": state["aggregated_context"]
    })

    state["plan"] = result.steps

    # Log the updated plan for debugging
    cl.Task(title="Updated Plan", status=cl.TaskStatus.DONE)
    for i, step in enumerate(state["plan"], 1):
        cl.Task(title=f"Step {i}: {step}", status=cl.TaskStatus.DONE)

    return state

@cl.step(name="Decide Retrieval or Answer", type="process")
async def retrieve_or_answer(state: PlanExecute):
    """Decide whether to retrieve or answer the question based on the current state.
    Args:
        state: The current state of the plan execution.
    Returns:
        updates the tool to use .
    """
    state["curr_state"] = "decide_tool"
    
    # Wenn das Flag direct_to_answer gesetzt ist, gehe direkt zur Antwort
    if state.get("direct_to_answer", False):
        return "chosen_tool_is_answer"
    
    # Wenn der aktuelle Zustand bereits "answer" ist, gehe direkt zur Antwort
    if state["curr_state"] == "answer":
        return "chosen_tool_is_answer"
    
    # Verhindere Endlosschleifen bei check_faq-Aufrufen
    # Wenn die vorherige Funktion check_faq war, sollten wir nicht wieder dorthin gehen
    if state["tool"] == "check_faq" and state.get("prev_tool") == "check_faq":
        # Stattdessen zum parallelen Retrieval wechseln
        state["tool"] = "parallel_retrieval"
        
    # Merke uns die aktuelle tool-Einstellung für die nächste Entscheidung
    state["prev_tool"] = state["tool"]
    
    if state["tool"] == "check_faq":
        return "chosen_tool_is_check_faq"
    elif state["tool"] == "retrieve_chunks":
        return "chosen_tool_is_retrieve_chunks"
    elif state["tool"] == "retrieve_summaries":
        return "chosen_tool_is_retrieve_summaries"
    elif state["tool"] == "retrieve_quotes":
        return "chosen_tool_is_retrieve_quotes"
    elif state["tool"] == "parallel_retrieval":
        return "chosen_tool_is_parallel_retrieval"
    elif state["tool"] == "create_moodle_course":
        return "chosen_tool_is_create_moodle_course"
    elif state["tool"] == "answer":
        return "chosen_tool_is_answer"
    else:
        raise ValueError("Invalid tool was outputed. Must be either 'check_faq', 'retrieve_chunks', 'retrieve_summaries', 'retrieve_quotes', 'parallel_retrieval', 'create_moodle_course' or 'answer'")

# Füge eine Funktion hinzu, um zu entscheiden, welchen Pfad wir von check_faq aus nehmen
@cl.step(name="Decide FAQ Path", type="process")
async def decide_faq_path(state: PlanExecute):
    """Entscheidet, ob wir direkt zur Antwort gehen oder zum Task Handler zurückkehren.
    
    Args:
        state: Der aktuelle Zustand der Plan-Ausführung.
    Returns:
        Der aktualisierte Zustand mit einem Routing-Attribut.
    """
    # Verhindere Endlosschleifen
    if state.get("faq_check_count", 0) > 0:
        # Wenn wir bereits einmal FAQ überprüft haben, gehen wir direkt zum task_handler
        # mit dem Befehl, parallel_retrieval zu verwenden
        state["tool"] = "parallel_retrieval"
        state["routing"] = "back_to_task_handler"
        return state
    
    # Erhöhe den Zähler für FAQ-Überprüfungen
    state["faq_check_count"] = state.get("faq_check_count", 0) + 1
    
    # Füge ein Routing-Attribut zum Zustand hinzu
    state["routing"] = "direct_to_answer" if state.get("direct_to_answer", False) else "back_to_task_handler"
    
    if state["routing"] == "direct_to_answer":
        await cl.Message(content=state["response"]).send()
    # Gib den vollständigen Zustand zurück
    return state

class IsGroundedOnFacts(BaseModel):
    """Ergebnis der Faktenüberprüfung."""
    grounded_on_facts: bool = Field(description="Antwort basiert auf Fakten, 'ja' oder 'nein'")

async def check_answer_hallucination(state: PlanExecute):
    """
    Überprüft, ob die generierte Antwort auf den gegebenen Fakten basiert oder eine Halluzination ist.
    
    Args:
        state: Der aktuelle Zustand der Plan-Ausführung.
    Returns:
        "hallucination", wenn die Antwort nicht auf Fakten basiert, sonst "grounded_on_context".
    """
    state["curr_state"] = "check_hallucination"
    
    answer = state["response"] if "response" in state else state["answer"]
    context = state["aggregated_context"] if "aggregated_context" in state else state["context"]
    
    await cl.Message(content="Überprüfe, ob die Antwort auf den gegebenen Fakten basiert...").send()
    
    # Prompt für die Überprüfung der Faktenbasiertheit
    hallucination_check_prompt_template = """Du bist ein Faktenprüfer, der bestimmt, ob die gegebene Antwort {answer} 
    auf dem gegebenen Kontext {context} basiert.
    Es spielt keine Rolle, ob es logisch erscheint, solange es im Kontext verankert ist.
    Ausgabe als JSON mit der Antwort auf die Frage.
    """
    
    hallucination_check_prompt = PromptTemplate(
        template=hallucination_check_prompt_template,
        input_variables=["context", "answer"],
    )
    
    # LLM-Modell für die Faktenprüfung
    hallucination_check_llm = get_llm(temperature=0)
    hallucination_check_chain = hallucination_check_prompt | hallucination_check_llm.with_structured_output(
        IsGroundedOnFacts,
        method="function_calling",
        strict=True
    )
    
    # Invoke the chain
    input_data = {
        "context": context,
        "answer": answer
    }
    
    result = hallucination_check_chain.invoke(input_data)
    grounded = result.grounded_on_facts
    
    if not grounded:
        await cl.Message(content="⚠️ Die Antwort scheint eine Halluzination zu sein und ist nicht vollständig durch den Kontext gestützt.").send()
        return "hallucination"
    else:
        await cl.Message(content="✅ Die Antwort basiert auf den verfügbaren Fakten.").send()
        return "grounded_on_context"  

class RewrittenQuestion(BaseModel):
    """Schema für die umgeschriebene Frage."""
    rewritten_question: str = Field(description="Die verbesserte Frage, optimiert für Vektorsuche.")
    explanation: str = Field(description="Die Erklärung der umgeschriebenen Frage.")

async def rewrite_question(state: PlanExecute):
    """
    Schreibt die gegebene Frage neu, um bessere Suchergebnisse zu erzielen.
    
    Args:
        state: Der aktuelle Zustand der Plan-Ausführung.
    Returns:
        Der aktualisierte Zustand mit der umgeschriebenen Frage.
    """
    state["curr_state"] = "rewrite_question"
    
    question = state["question"] if "query_to_retrieve_or_answer" not in state else state["query_to_retrieve_or_answer"]
    
    await cl.Message(content=f"Schreibe die Frage um, um bessere Suchergebnisse zu erzielen: '{question}'").send()
    
    # Prompt für die Umschreibung der Frage
    rewrite_prompt_template = """Du bist ein Frageumschreiber, der eine Eingabefrage in eine bessere Version 
    umwandelt, die für die Vektorsuche optimiert ist.
    Analysiere die Eingabefrage {question} und versuche, die zugrunde liegende semantische Absicht/Bedeutung zu verstehen.
    
    Die umgeschriebene Frage sollte:
    1. Relevante Schlüsselwörter enthalten
    2. Präziser sein als die Originalfrage
    3. Ambiguitäten auflösen
    4. Auf die wichtigsten Informationsbedürfnisse fokussieren
    
    Gib eine verbesserte Version der Frage und eine Erklärung zurück, warum du die Änderungen vorgenommen hast.
    """
    
    rewrite_prompt = PromptTemplate(
        template=rewrite_prompt_template,
        input_variables=["question"],
    )
    
    # LLM-Modell für die Fragenumschreibung
    rewrite_llm = get_llm(temperature=0)
    rewrite_chain = rewrite_prompt | rewrite_llm.with_structured_output(
        RewrittenQuestion,
        method="function_calling",
        strict=True
    )
    
    # Invoke the chain
    result = rewrite_chain.invoke({"question": question})
    
    # Update the state with the rewritten question
    new_question = result.rewritten_question
    explanation = result.explanation
    
    state["query_to_retrieve_or_answer"] = new_question
    
    await cl.Message(content=f"Umgeschriebene Frage: '{new_question}'\nBegründung: {explanation}").send()
    
    return state  