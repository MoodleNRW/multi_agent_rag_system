import chainlit as cl
from .state import PlanExecute

@cl.step(name="Generate Answer", type="tool")
async def run_qualtative_answer_workflow(state: PlanExecute):
    # Implementation here
    # This is where you would implement the logic to generate an answer
    state["response"] = f"Based on the context: {state['curr_context']}, a possible answer is..."
    return state

@cl.step(name="Generate Final Answer", type="tool")
async def run_qualtative_answer_workflow_for_final_answer(state: PlanExecute):
    # Implementation here
    # This is where you would implement the logic to generate the final answer
    state["response"] = f"Final answer based on all gathered information: {state['aggregated_context']}..."
    return state