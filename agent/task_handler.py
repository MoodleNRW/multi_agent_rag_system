import chainlit as cl
from .state import PlanExecute

@cl.step(name="Task Handler", type="process")
async def run_task_handler_chain(state: PlanExecute):
    # Implementation here
    # This is where you would implement the logic to decide the next task
    current_step = state["plan"][0]
    if "Retrieve" in current_step:
        state["tool"] = "retrieve"
        state["query_to_retrieve_or_answer"] = current_step
    else:
        state["tool"] = "answer"
        state["query_to_retrieve_or_answer"] = state["question"]
    return state