import chainlit as cl
from langchain_core.pydantic_v1 import BaseModel, Field
from .state import PlanExecute
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import Dict, Optional
import json

class AnonymizeQuestion(BaseModel):
    """Output Schema for the Anonymize Question tool."""
    anonymized_question: str = Field(description="Anonymized question.")
    mapping: Optional[Dict[str, str]] = Field(
        default=None, 
        description="Mapping of original name entities of the question to the variables."
    )    
    explanation: str = Field(description="Explanation of the anonymization process.")

@cl.step(name="Anonymize Query", type="tool")
async def anonymize_queries(state: PlanExecute):
    """
    Anonymizes the question.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the anonymized question and optional mapping.
    """
    state["curr_state"] = "anonymize_question"
    print(state)
    anonymize_question_prompt_template = """
You are an anonymizer for questions within a Moodle Support Ticket system. Your task is to anonymize all named entities (such as names, course names, locations, etc.) in a given support ticket question by replacing them with placeholder variables, while also generating a mapping of these original entities to the placeholders. Additionally, you should provide an explanation of how the anonymization was carried out.

Instructions:
1. Receive a question in the form of a string: {question}.
2. Identify all named entities within the question (e.g., course names, teacher names, or user names).
3. Replace each named entity with placeholder variables (e.g., \"X\", \"Y\", \"Z\").
4. Return the anonymized question, a mapping of original named entities to placeholder variables, and an explanation of the anonymization process.
5. If no named entities are found, return the original question unchanged with an empty mapping and explanation.

Example 1:
Input: \"How do I access Professor Smith's course on Moodle?\"
Output:
- anonymized_question: \"How do I access X's course on Moodle?\"
- mapping: {{\"X\": \"Professor Smith\"}}
- explanation: \"The name 'Professor Smith' was anonymized and replaced with the placeholder 'X'.\"

Example 2:
Input: \"Can you reset my password for the 'Biology 101' course?\"
Output:
- anonymized_question: \"Can you reset my password for the 'X' course?\"
- mapping: {{\"X\": \"Biology 101\"}}
- explanation: \"The course name 'Biology 101' was anonymized and replaced with the placeholder 'X'.\"

Example 3:
Input: \"How can I upload my assignment?\"
Output:
- anonymized_question: \"How can I upload my assignment?\"
- mapping: {{}}
- explanation: \"No named entities were found in the question, so no changes were made.\"

REMEMBER: The anonymized question should be returned in the same format as the input question, with the same punctuation and capitalization.
REMEMBER: The mapping should be a dictionary where the keys are the original named entities and the values are the placeholder variables.
REMEMBER: The explanation should describe how the anonymization was carried out, including which named entities were replaced and with which placeholders.
Format Instructions: {format_instructions}
"""

    anonymize_question_parser = JsonOutputParser(pydantic_object=AnonymizeQuestion)


    anonymize_question_prompt = PromptTemplate(
        template=anonymize_question_prompt_template,
        input_variables=["question"],
        partial_variables={"format_instructions": anonymize_question_parser.get_format_instructions()}
    )

    anonymize_question_llm = get_llm()
    anonymize_question_chain = anonymize_question_prompt | anonymize_question_llm.with_structured_output(AnonymizeQuestion, strict=True)

    result = anonymize_question_chain.invoke({"question": state["question"], "format_instructions": anonymize_question_parser.get_format_instructions()})
    print(result)

    state["anonymized_question"] = result.anonymized_question
    state["mapping"] = result.mapping if result.mapping is not None else {}
    state["explanation"] = result.explanation
    
    return state

class DeAnonymizePlan(BaseModel):
    """Possible results of the action."""
    plan: list = Field(description="Plan to follow in future. with all the variables replaced with the mapped words.")
@cl.step(name="Deanonymize Plan", type="tool")
async def deanonymize_queries(state: PlanExecute):
    """
    De-anonymizes the plan.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the de-anonymized plan.
    """
    state["curr_state"] = "de_anonymize_plan"

    de_anonymize_plan_prompt_template = """You receive a list of tasks: {plan}, where some of the words are replaced with mapped variables. You also receive
    the mapping for those variables to words {mapping}. Replace all the variables in the list of tasks with the mapped words. If no variables are present,
    return the original list of tasks. In any case, just output the updated list of tasks in a json format as described here, without any additional text apart from the JSON."""

    de_anonymize_plan_prompt = PromptTemplate(
        template=de_anonymize_plan_prompt_template,
        input_variables=["plan", "mapping"],
    )

    de_anonymize_plan_llm = get_llm()
    de_anonymize_plan_chain = de_anonymize_plan_prompt | de_anonymize_plan_llm.with_structured_output(DeAnonymizePlan)

    result = de_anonymize_plan_chain.invoke({"plan": state["plan"], "mapping": json.dumps(state["mapping"])})

    state["plan"] = result.plan

    return state
