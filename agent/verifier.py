import asyncio
import chainlit as cl
from langsmith import traceable
from .state import PlanExecute
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field
from typing import List

class CanBeAnsweredResult(BaseModel):
    """Output schema for checking if the question can be answered."""
    answer_status: str = Field(description="Status der Beantwortbarkeit: 'fully_answered', 'partially_answered', oder 'not_answered'")
    explanation: str = Field(description="Explanation for the answer status.")

@traceable(pass_config=False)
@cl.step(name="Check Answerability", type="process")
async def can_be_answered(state: PlanExecute):
    """
    Determines if the original question can be fully answered, partially answered (descriptive info only),
    or not answered based on the aggregated filtered context.
    Args:
        state: The current state of the plan execution.
    Returns:
        'can_be_answered_already', 'partially_answered', or 'cannot_be_answered_yet'.
    """
    state["curr_state"] = "can_be_answered_check"

    question = state["question"]
    context = state.get("aggregated_filtered_context", "") # Use filtered context

    if not context or not context.strip():
        await cl.Message(content="Aggregated context is empty. Cannot answer yet.").send()
        # If context is empty, we definitely cannot answer.
        return "cannot_be_answered_yet"

    # Updated prompt to differentiate between full, partial, and no answer
    prompt_template = """Given the following context:
{context}

Consider the question: '{question}'

Determine the answerability status based *only* on the provided context:
1.  **fully_answered**: The context contains all the specific information needed to completely answer the question (e.g., if the question asks for specific code and the context provides it).
2.  **partially_answered**: The context contains relevant descriptive information, explanations, or pointers related to the question, but lacks the specific detail needed for a *full* answer (e.g., it describes an API but doesn't provide the exact code example asked for, or mentions the code is available elsewhere like a support portal).
3.  **not_answered**: The context does not contain any relevant information to even partially address the question.

Provide the status ('answer_status') and a brief explanation.
    """

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["question", "context"],
    )

    llm = get_llm(temperature=0)
    chain = prompt | llm.with_structured_output(
        CanBeAnsweredResult,
        method="function_calling",
        strict=True
    )

    try:
        input_data = {"question": question, "context": context}
        output = chain.invoke(input_data)

        status = output.answer_status
        explanation = output.explanation
        await cl.Message(content=f"Answerability Check: {status} ({explanation[:100]}...)").send()

        if status == 'fully_answered':
            await cl.Message(content="Question can be fully answered.").send()
            return "can_be_answered_already"
        elif status == 'partially_answered':
            await cl.Message(content="Question can be partially answered (descriptive info found).").send()
            return "partially_answered" # New return value
        else: # status == 'not_answered'
            await cl.Message(content="Question cannot be answered yet (no relevant info found).").send()
            return "cannot_be_answered_yet"

    except Exception as e:
        await cl.Message(content=f"Error during answerability check: {e}. Assuming cannot be answered yet.").send()
        return "cannot_be_answered_yet"