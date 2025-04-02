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
import json # For pretty printing context

    # Definiere das Output-Schema
class KeepRelevantContent(BaseModel):
    relevant_content: str = Field(description="The relevant content from the retrieved documents that is relevant to the query.")
    
# Neuer gemeinsamer Node für die Relevanzprüfung nach dem Retrieval
@traceable(pass_config=False)
@cl.step(name="Keep Only Relevant Content", type="process")
async def keep_only_relevant_content(state: PlanExecute):
    """
    Filters the most recently retrieved context ('raw_context') to keep only relevant parts.

    Args:
        state: The current state of the plan execution. Must contain 'question' and 'raw_context'.
    Returns:
        The updated state with 'aggregated_filtered_context' updated and 'relevance_status' set.
    """
    state["curr_state"] = "keep_only_relevant_content"

    # Extrahiere die benötigten Felder aus dem Zustand
    question = state["question"]
    # Use the newly retrieved raw context
    raw_context = state.get("raw_context", "")

    if not raw_context or not raw_context.strip():
        # Keep this message
        await cl.Message(content="No context retrieved in the previous step to filter.").send()
        state["relevance_status"] = "no_context_to_filter"
        # Ensure aggregated_filtered_context exists
        if "aggregated_filtered_context" not in state:
            state["aggregated_filtered_context"] = ""
        return state

    # Simplified English Prompt (closer to the reference notebook)
    keep_only_relevant_content_prompt_template = """You receive a query: {query} and retrieved documents: {retrieved_documents} from a
 vector store.
 You need to filter out all the non relevant information that doesn't supply important information regarding the {query}.
 Your goal is just to filter out the non relevant information.
 You can remove parts of sentences that are not relevant to the query or remove whole sentences that are not relevant to the query.
 DO NOT ADD ANY NEW INFORMATION THAT IS NOT IN THE RETRIEVED DOCUMENTS.
 Output the filtered relevant content. If no content is relevant, output an empty string.
    """

    keep_only_relevant_content_prompt = PromptTemplate(
        template=keep_only_relevant_content_prompt_template,
        input_variables=["query", "retrieved_documents"],
    )

    keep_only_relevant_content_llm = get_llm(temperature=0)
    keep_only_relevant_content_chain = keep_only_relevant_content_prompt | keep_only_relevant_content_llm.with_structured_output(
        KeepRelevantContent,
        method="function_calling",
        strict=True # Keep strict for now, maybe relax if needed
    )

    # Eingabedaten für das LLM-Modell
    input_data = {
        "query": question,
        "retrieved_documents": raw_context # Filter the latest raw context
    }

    # Remove generic start message
    # await cl.Message(content=f"Filtering retrieved content for query: '{question}'").send()
    try:
        output = keep_only_relevant_content_chain.invoke(input_data)
        relevant_content = output.relevant_content
    except Exception as e:
        # Keep error message
        await cl.Message(content=f"Error during content filtering: {e}. Skipping filtering.").send()
        relevant_content = raw_context # Fallback: use raw context if filtering fails

    # Remove the grounding check and retry logic for now to simplify
    # is_grounded = await check_content_grounding(relevant_content, raw_context)
    # ... (removed retry block) ...

    # Initialize aggregated_filtered_context if it doesn't exist
    if "aggregated_filtered_context" not in state or state["aggregated_filtered_context"] is None:
        state["aggregated_filtered_context"] = ""

    # Speichere den gefilterten Inhalt im Zustand (appending to the filtered aggregate)
    if relevant_content and relevant_content.strip():
        state["aggregated_filtered_context"] += f"\n\n{relevant_content}"
        # Keep result message
        await cl.Message(content=f"Relevant content found and added to aggregated context.").send()
        state["relevance_status"] = "found_relevant_content"
    else:
        # Keep result message
        await cl.Message(content="No relevant content found in this retrieved batch.").send()
        state["relevance_status"] = "no_relevant_content_found"

    # Clear raw_context after processing
    state["raw_context"] = ""

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
            "found_relevant_content": "replan",
            "no_relevant_content_found": "replan",
            "no_context_to_filter": "replan"
        }
    )

    # Conditional edges after the intermediate "answer" node
    agent_workflow.add_conditional_edges(
        "answer",
        is_answer_grounded_on_context,
        {
            "grounded on context": "replan",
            "hallucination": "rewrite_question"
        }
    )

    # Kante vom rewrite_question zurück zum task_handler
    agent_workflow.add_edge("rewrite_question", "task_handler")

    agent_workflow.add_edge("call_moodle_tool", "replan")

    # Conditional edges AFTER replan
    agent_workflow.add_conditional_edges(
        "replan",
        can_be_answered, # This function now returns one of three strings
        {
            "can_be_answered_already": "get_final_answer",
            "partially_answered": "get_final_answer", # Also go to final answer for partial
            "cannot_be_answered_yet": "break_down_plan_to_retrieve_or_answer" # Loop back if needed
        }
    )

    # Final answer path should already be using is_answer_grounded_on_context
    agent_workflow.add_conditional_edges(
         "get_final_answer",
         is_answer_grounded_on_context,
         {
             "grounded on context": END,
             "hallucination": END
         }
     )

    # Füge die Entscheidungsfunktion zum Workflow hinzu
    agent_workflow.add_edge("check_faq", "decide_faq_path")
    agent_workflow.add_conditional_edges(
        "decide_faq_path",
        lambda x: x["routing"],
        {
            "direct_to_answer": "replan",
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
    Replans the next step based on the current state, using the aggregated filtered context.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the potentially revised plan.
    """
    state["curr_state"] = "replan"
    aggregated_context = state.get("aggregated_filtered_context", "")
    current_plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])
    original_question = state.get("question", "")

    if not current_plan:
        await cl.Message(content="Plan empty. Checking answerability...").send()
        return state

    replan_prompt_template = """Given the current state of our question-answering process, we need to update the remaining plan.

    Original question: {question}
    Current remaining plan steps: {plan}
    Steps already completed: {past_steps}
    Current aggregated context based on completed steps:
    {aggregated_context}

    Based on this information, please refine the *remaining* plan steps.
    - Analyze if the remaining steps are still necessary given the current context.
    - Remove redundant steps.
    - Add new steps if the context reveals a need for a different approach.
    - If the question can likely be answered with the current context and the remaining plan involves just answering, keep the final answer step.
    - If the question seems answerable now, but the plan still has retrieval steps, update the plan to just include the final answer step.
    - Ensure the plan always leads towards answering the original question.
    - Do not include steps that have already been completed in {past_steps}.

    Output the updated list of remaining plan steps in JSON format.
    """

    replan_prompt = PromptTemplate(
        template=replan_prompt_template,
        input_variables=["question", "plan", "past_steps", "aggregated_context"],
    )

    replan_llm = get_llm(temperature=0)
    replan_chain = replan_prompt | replan_llm.with_structured_output(
        Plan, # Assuming Plan model is defined (List[str])
        method="function_calling",
        strict=True
    )

    try:
        input_data = {
            "question": original_question,
            "plan": current_plan,
            "past_steps": past_steps,
            "aggregated_context": aggregated_context
        }
        result = replan_chain.invoke(input_data)
        updated_plan = result.steps

        state["plan"] = updated_plan

        # Keep result message
        await cl.Message(content=f"Updated Plan: {updated_plan}").send()
    except Exception as e:
        await cl.Message(content=f"Error during replanning: {e}. Keeping existing plan.").send()
        if "plan" not in state:
             state["plan"] = []

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