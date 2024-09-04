import chainlit as cl
from .state import PlanExecute

@cl.step(name="Verify Answer", type="process")
async def can_be_answered(state: PlanExecute):
    # Implementation here
    # This is where you would implement the logic to verify if the question can be answered
    if len(state["aggregated_context"]) > 100:  # This is a simplistic check
        return "can_be_answered_already"
    else:
        return "cannot_be_answered_yet"