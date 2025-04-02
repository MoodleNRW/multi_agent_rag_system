import chainlit as cl
from langsmith import traceable
from pydantic import BaseModel, Field
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from .state import PlanExecute
import logging

logger = logging.getLogger(__name__)

class IsGroundedOnFactsResult(BaseModel):
    """Schema for the fact-checking result."""
    grounded_on_facts: bool = Field(description="Whether the answer is grounded in the provided facts (context). True or False.")

@traceable(pass_config=False)
@cl.step(name="Check Hallucination", type="process")
async def is_answer_grounded_on_context(state: PlanExecute):
    """
    Checks if the generated answer (in state['response']) is grounded in the aggregated filtered context.
    Args:
        state: The current state of the plan execution.
    Returns:
        'grounded on context' or 'hallucination'.
    """
    state["curr_state"] = "check_hallucination"

    answer_dict = state.get("response", {})
    answer = answer_dict.get("answer", "")
    context = state.get("aggregated_filtered_context", "")

    if not answer or not answer.strip():
        await cl.Message(content="No answer generated to check for hallucination.").send()
        return "grounded on context"

    if not context or not context.strip():
        await cl.Message(content="Aggregated context empty. Assuming hallucination.").send()
        return "hallucination"

    prompt_template = """You are a fact-checker. Your task is to determine if the statement provided in the 'answer' is factually supported by the information given in the 'context'.
    Only consider the provided context as the source of truth. Do not use external knowledge.
    The answer does not need to be perfectly phrased, but all core claims made in the answer must be traceable back to the context.

    Context:
    {context}

    Answer:
    {answer}

    Is the Answer grounded in the Context?
    Provide a boolean response ('grounded_on_facts').
    """

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "answer"],
    )

    llm = get_llm(temperature=0)
    chain = prompt | llm.with_structured_output(
        IsGroundedOnFactsResult,
        method="function_calling",
        strict=True
    )

    try:
        input_data = {"context": context, "answer": answer}
        output = chain.invoke(input_data)

        if output.grounded_on_facts:
            await cl.Message(content="Answer grounded in context.").send()
            return "grounded on context"
        else:
            await cl.Message(content="Potential Hallucination: Answer not fully grounded in context.").send()
            return "hallucination"
    except Exception as e:
        await cl.Message(content=f"Error during hallucination check: {e}. Assuming hallucination.").send()
        return "hallucination" 