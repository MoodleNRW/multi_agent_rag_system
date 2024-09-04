import chainlit as cl
from .state import PlanExecute

@cl.step(name="Anonymize Query", type="process")
async def anonymize_queries(state: PlanExecute):
    # Implementation here
    # This is where you would implement the logic to anonymize the question
    state["anonymized_question"] = state["question"].replace("Specific Name", "PERSON")
    state["mapping"] = {"PERSON": "Specific Name"}
    return state

@cl.step(name="Deanonymize Plan", type="process")
async def deanonymize_queries(state: PlanExecute):
    # Implementation here
    # This is where you would implement the logic to deanonymize the plan
    for i, step in enumerate(state["plan"]):
        for key, value in state["mapping"].items():
            state["plan"][i] = step.replace(key, value)
    return state