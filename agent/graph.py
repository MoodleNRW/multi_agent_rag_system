# agent/graph.py

import chainlit as cl
from langgraph.graph import StateGraph, END
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate

from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List

from .state import PlanExecute
from .anonymizer import anonymize_queries, deanonymize_queries
from .task_handler import run_task_handler_chain
from .retriever import run_qualitative_chunks_retrieval_workflow, run_qualitative_summaries_retrieval_workflow, run_qualitative_quotes_retrieval_workflow
from .tools import run_moodle_tool_workflow
from .answerer import run_qualtative_answer_workflow, run_qualtative_answer_workflow_for_final_answer
from .verifier import can_be_answered

async def create_agent_graph():
    agent_workflow = StateGraph(PlanExecute)

    # Add nodes
    agent_workflow.add_node("anonymize_question", anonymize_queries)
    agent_workflow.add_node("planner", plan_step)
    agent_workflow.add_node("de_anonymize_plan", deanonymize_queries)
    agent_workflow.add_node("break_down_plan", break_down_plan_step)
    agent_workflow.add_node("task_handler", run_task_handler_chain)
    agent_workflow.add_node("retrieve_chunks", run_qualitative_chunks_retrieval_workflow)
    agent_workflow.add_node("retrieve_summaries", run_qualitative_summaries_retrieval_workflow)
    agent_workflow.add_node("retrieve_quotes", run_qualitative_quotes_retrieval_workflow)
    agent_workflow.add_node("call_moodle_tool", run_moodle_tool_workflow)
    agent_workflow.add_node("answer", run_qualtative_answer_workflow)
    agent_workflow.add_node("replan", replan_step)
    agent_workflow.add_node("get_final_answer", run_qualtative_answer_workflow_for_final_answer)

    # Set entry point
    agent_workflow.set_entry_point("anonymize_question")

    # Add edges
    agent_workflow.add_edge("anonymize_question", "planner")
    agent_workflow.add_edge("planner", "de_anonymize_plan")
    agent_workflow.add_edge("de_anonymize_plan", "break_down_plan")
    agent_workflow.add_edge("break_down_plan", "task_handler")

    # Add conditional edges
    agent_workflow.add_conditional_edges(
        "task_handler",
        retrieve_or_answer,
        {
            "chosen_tool_is_retrieve_chunks": "retrieve_chunks",
            "chosen_tool_is_retrieve_summaries": "retrieve_summaries",
            "chosen_tool_is_retrieve_quotes": "retrieve_quotes",
            "chose_tool_is_create_moodle_course": "call_moodle_tool",
            "chosen_tool_is_answer": "answer"
        }
    )

    agent_workflow.add_edge("retrieve_chunks", "replan")
    agent_workflow.add_edge("retrieve_summaries", "replan")
    agent_workflow.add_edge("retrieve_quotes", "replan")
    agent_workflow.add_edge("answer", "replan")

    agent_workflow.add_conditional_edges(
        "replan",
        can_be_answered,
        {
            "can_be_answered_already": "get_final_answer",
            "cannot_be_answered_yet": "break_down_plan"
        }
    )

    agent_workflow.add_edge("get_final_answer", END)

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

    planner = planner_prompt | planner_llm.with_structured_output(Plan, strict = True)

    result = planner.invoke({"question": state["anonymized_question"]})

    state["plan"] = result.steps

    return state

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
        i. retrieving relevant information from a vector store of chunks
        ii. retrieving relevant information from a vector store of chapter summaries
        iii. retrieving relevant information from a vector store of quotes
        iv. answering a question from a given context.
        v. creating a moodle course.
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
    break_down_plan_chain = break_down_plan_prompt | break_down_plan_llm.with_structured_output(Plan,  strict = True)

    result = break_down_plan_chain.invoke({"plan": state["plan"]})

    state["plan"] = result.steps

    return state

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
    replan_chain = replan_prompt | replan_llm.with_structured_output(Plan,  strict = True)

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
    if state["tool"] == "retrieve_chunks":
        return "chosen_tool_is_retrieve_chunks"
    elif state["tool"] == "retrieve_summaries":
        return "chosen_tool_is_retrieve_summaries"
    elif state["tool"] == "retrieve_quotes":
        return "chosen_tool_is_retrieve_quotes"
    elif state["tool"] == "create_moodle_course":
        return "chose_tool_is_create_moodle_course"
    elif state["tool"] == "answer":
        return "chosen_tool_is_answer"
    else:
        raise ValueError("Invalid tool was outputed. Must be either 'retrieve' or 'answer_from_context'")  