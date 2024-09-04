import chainlit as cl
from .state import PlanExecute
from langchain_openai import ChatOpenAI 
from langchain.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

class CanBeAnsweredOutput(BaseModel):
    """Output schema for the can_be_answered verifier."""
    can_be_answered: bool = Field(description="Whether the question can be fully answered or not based on the given context.")
    explanation: str = Field(description="An explanation of why the question can or cannot be fully answered.")

@cl.step(name="Verify Answer", type="process")
async def can_be_answered(state: PlanExecute):
    can_be_answered_prompt_template = """You are an AI assistant tasked with determining if a given question can be fully answered based on the provided context.

    Original question: {question}
    Current aggregated context: {context}

    Your task:
    1. Carefully analyze the question and the provided context.
    2. Determine if the context contains enough information to fully answer the original question. If a moodle_course is created, the question can be answered.
    3. Provide a yes/no decision and a brief explanation for your decision.

    Remember:
    - The context must contain all necessary information to provide a complete and accurate answer. If a moodle_course is created, the question can be answered and the context is considered complete.
    - If any crucial information is missing, or if the context only allows for a partial answer, consider it as not fully answerable.

    Output your decision and explanation in JSON format.
    """

    can_be_answered_prompt = PromptTemplate(
        template=can_be_answered_prompt_template,
        input_variables=["question", "context"],
    )

    can_be_answered_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", =2000)
    can_be_answered_chain = can_be_answered_prompt | can_be_answered_llm.with_structured_output(CanBeAnsweredOutput)

    result = can_be_answered_chain.invoke({
        "question": state["question"],
        "context": state["aggregated_context"]
    })

    # Log the decision for debugging
    cl.Task(title="Can be answered?", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Decision: {'Yes' if result.can_be_answered else 'No'}", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Explanation: {result.explanation}", status=cl.TaskStatus.DONE)

    if result.can_be_answered:
        return "can_be_answered_already"
    else:
        return "cannot_be_answered_yet"