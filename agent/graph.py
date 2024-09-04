# agent/graph.py

import chainlit as cl
from langgraph.graph import StateGraph, END
from .state import PlanExecute
from .anonymizer import anonymize_queries, deanonymize_queries
from .task_handler import run_task_handler_chain
from .retriever import run_qualitative_chunks_retrieval_workflow, run_qualitative_summaries_retrieval_workflow, run_qualitative_quotes_retrieval_workflow
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

@cl.step(name="Plan Step", type="process")
async def plan_step(state: PlanExecute):
    # Implementation of planning step
    # This is where you would implement the logic to create a plan based on the anonymized question
    plan = ["Step 1: Analyze question", "Step 2: Retrieve relevant information", "Step 3: Formulate answer"]
    state["plan"] = plan
    return state

@cl.step(name="Break Down Plan", type="process")
async def break_down_plan_step(state: PlanExecute):
    # Implementation of breaking down plan step
    # This is where you would implement the logic to break down the plan into more detailed steps
    detailed_plan = []
    for step in state["plan"]:
        detailed_plan.extend([f"{step} - Substep A", f"{step} - Substep B"])
    state["plan"] = detailed_plan
    return state

@cl.step(name="Replan", type="process")
async def replan_step(state: PlanExecute):
    # Implementation of replanning step
    # This is where you would implement the logic to adjust the plan based on new information
    state["plan"] = [step for step in state["plan"] if step not in state["past_steps"]]
    if not state["plan"]:
        state["plan"] = ["Final step: Synthesize information"]
    return state

@cl.step(name="Decide Retrieval or Answer", type="process")
async def retrieve_or_answer(state: PlanExecute):
    # Implementation of retrieve or answer decision
    # This is where you would implement the logic to decide whether to retrieve more information or answer
    if "Retrieve" in state["plan"][0]:
        if "chunks" in state["plan"][0]:
            return "chosen_tool_is_retrieve_chunks"
        elif "summaries" in state["plan"][0]:
            return "chosen_tool_is_retrieve_summaries"
        else:
            return "chosen_tool_is_retrieve_quotes"
    else:
        return "chosen_tool_is_answer"