from pydantic import BaseModel, Field
from typing import List
import chainlit as cl
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from .state import PlanExecute

class SupportSummary(BaseModel):
    """Summary for the support employee"""
    question: str = Field(description="The original question")
    relevant_information: str = Field(
        description="Any relevant information retrieved that can help answer the question"
    )
    issues_encountered: str = Field(description="Any issues or errors that were encountered")
    suggestions: str = Field(description="Suggestions on how to proceed to answer the question")


@cl.step(name="Support Summary", type="tool")
async def support_summary_step(state: PlanExecute):
    """
    Generates a summary for the support employee based on the current state.
    Args:
        state: The current state of the process.
    Returns:
        The updated state with the support summary.
    """
    # Define the prompt template
    support_summary_prompt_template = """You are a helpful assistant summarizing the current state for a support employee.

Current state:
- Current state: {curr_state}
- Original question: {question}
- Anonymized question: {anonymized_question}
- Query to retrieve or answer: {query_to_retrieve_or_answer}
- Plan: {plan}
- Past steps: {past_steps}
- Mapping: {mapping}
- Current context: {curr_context}
- Aggregated context: {aggregated_context}
- Tool: {tool}
- Response: {response}

Please provide a concise summary that can help a support employee understand the issue and answer the user's question.

The summary should include:

- 'question': The original question.
- 'relevant_information': Any relevant information retrieved that can help answer the question.
- 'issues_encountered': Any issues or errors that were encountered.
- 'suggestions': Suggestions on how to proceed to answer the question.

Output the summary in JSON format as per the schema:

{{
    "question": string,
    "relevant_information": string,
    "issues_encountered": string,
    "suggestions": string
}}

"""

    # Create the prompt template
    support_summary_prompt = PromptTemplate(
        template=support_summary_prompt_template,
        input_variables=[
            "curr_state",
            "question",
            "anonymized_question",
            "query_to_retrieve_or_answer",
            "plan",
            "past_steps",
            "mapping",
            "curr_context",
            "aggregated_context",
            "tool",
            "response"
        ],
    )

    # Get the LLM
    llm = get_llm()

    # Create the chain with structured output
    support_summary_chain = support_summary_prompt | llm.with_structured_output(SupportSummary, strict=True)

    # Invoke the chain
    result = support_summary_chain.invoke({
        "curr_state": state["curr_state"],
        "question": state["question"],
        "anonymized_question": state["anonymized_question"],
        "query_to_retrieve_or_answer": state["query_to_retrieve_or_answer"],
        "plan": state["plan"],
        "past_steps": state["past_steps"],
        "mapping": state["mapping"],
        "curr_context": state["curr_context"],
        "aggregated_context": state["aggregated_context"],
        "tool": state["tool"],
        "response": state["response"]
    })

    # Log the summary
    cl.Task(title="Support Summary", status=cl.TaskStatus.DONE)
    cl.Message(content=str(result))

    # Update the state with the summary

    return result