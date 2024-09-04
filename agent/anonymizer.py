import chainlit as cl
from langchain_core.pydantic_v1 import BaseModel, Field
from .state import PlanExecute
from langchain_openai import ChatOpenAI 
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import Dict

class AnonymizeQuestion(BaseModel):
    """Anonymized question and mapping."""
    anonymized_question : str = Field(description="Anonymized question.")
    mapping: dict = Field(description="Mapping of original name entities to variables.")
    explanation: str = Field(description="Explanation of the action.")

class DeAnonymizePlan(BaseModel):
    """Possible results of the action."""
    plan: list = Field(description="Plan to follow in future. with all the variables replaced with the mapped words.")

@cl.step(name="Anonymize Query", type="tool")
async def anonymize_queries(state: PlanExecute):
    anonymize_question_parser = JsonOutputParser(pydantic_object=AnonymizeQuestion)

    anonymize_question_prompt_template = """ You are a question anonymizer. The input You receive is a string containing several words that
    construct a question {question}. Your goal is to changes all name entities in the input to variables, and remember the mapping of the original name entities to the variables.
    ```example1:
            if the input is \"who is harry potter?\" the output should be \"who is X?\" and the mapping should be {{\"X\": \"harry potter\"}} ```
    ```example2:
            if the input is \"how did the bad guy played with the alex and rony?\"
            the output should be \"how did the X played with the Y and Z?\" and the mapping should be {{\"X\": \"bad guy\", \"Y\": \"alex\", \"Z\": \"rony\"}}```
    you must replace all name entities in the input with variables, and remember the mapping of the original name entities to the variables.
    output the anonymized question and the mapping in a json format. {format_instructions}"""

    anonymize_question_prompt = PromptTemplate(
        template=anonymize_question_prompt_template,
        input_variables=["question"],
        partial_variables={"format_instructions": anonymize_question_parser.get_format_instructions()
        },
    )

    anonymize_question_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=4000, )
    anonymize_question_chain = anonymize_question_prompt | anonymize_question_llm | anonymize_question_parser

    print(state["question"])
    result = anonymize_question_chain.invoke({"question": state["question"]})
    print(result)
    # Here's the change: we're now accessing the result as a dictionary
    state["anonymized_question"] = result["anonymized_question"]
    state["mapping"] = result["mapping"]
    
    return state

@cl.step(name="Deanonymize Plan", type="tool")
async def deanonymize_queries(state: PlanExecute):
    de_anonymize_plan_prompt_template = """You receive a list of tasks: {plan}, where some of the words are replaced with mapped variables. You also receive
    the mapping for those variables to words {mapping}. Replace all the variables in the list of tasks with the mapped words. If no variables are present,
    return the original list of tasks. In any case, just output the updated list of tasks in a json format as described here, without any additional text apart from the JSON."""

    de_anonymize_plan_prompt = PromptTemplate(
        template=de_anonymize_plan_prompt_template,
        input_variables=["plan", "mapping"],
    )

    de_anonymize_plan_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    de_anonymize_plan_chain = de_anonymize_plan_prompt | de_anonymize_plan_llm.with_structured_output(DeAnonymizePlan)

    result = de_anonymize_plan_chain.invoke({"plan": state["plan"], "mapping": state["mapping"]})

    state["plan"] = result.plan

    return state
