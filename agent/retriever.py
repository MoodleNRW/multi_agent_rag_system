import chainlit as cl
from .state import PlanExecute

@cl.step(name="Retrieve Chunks", type="tool")
async def run_qualitative_chunks_retrieval_workflow(state: PlanExecute):
    # Implementation here
    # This is where you would implement the logic to retrieve chunks
    state["curr_context"] += "Retrieved chunk information. "
    return state

@cl.step(name="Retrieve Summaries", type="tool")
async def run_qualitative_summaries_retrieval_workflow(state: PlanExecute):
    # Implementation here
    # This is where you would implement the logic to retrieve summaries
    state["curr_context"] += "Retrieved summary information. "
    return state

@cl.step(name="Retrieve Quotes", type="tool")
async def run_qualitative_quotes_retrieval_workflow(state: PlanExecute):
    # Implementation here
    # This is where you would implement the logic to retrieve quotes
    state["curr_context"] += "Retrieved quote information. "
    return state