# agent/answerer.py

import chainlit as cl
import asyncio
from typing import List, Tuple, Dict
from .state import PlanExecute
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langsmith import traceable
import time

class QuestionAnswerFromContext(BaseModel):
    """
    Output-Schema für die Antwortgenerierung.
    """
    reasoning: str = Field(description="Der Gedankengang zur Beantwortung der Frage.")
    answer_based_on_content: str = Field(description="Die endgültige Antwort auf die Frage, basierend auf dem Kontext.")


@traceable(pass_config=False)
@cl.step(name="Generate Answer from Context", type="llm")
async def run_qualtative_answer_workflow(state: PlanExecute):
    """
    Generates an answer based on the provided context (typically state['curr_context']).
    Used for intermediate answers within the plan.
    
    Args:
        state: The current state of the plan execution.
        
    Returns:
        The state with the generated answer added to 'aggregated_filtered_context'.
    """
    state["curr_state"] = "answer"

    question = state["query_to_retrieve_or_answer"]
    context = state.get("curr_context", "")

    if not context or not context.strip():
        await cl.Message(content="No context provided for intermediate answer generation. Skipping.").send()
        if "aggregated_filtered_context" not in state:
            state["aggregated_filtered_context"] = ""
        return state

    question_answer_cot_prompt_template = """
    # Beispiele für Chain-of-Thought-Reasoning

    ## Beispiel 1
    Kontext: Maria ist größer als Jana. Jana ist kleiner als Tom. Tom ist gleich groß wie David.
    Frage: Wer ist die größte Person?
    Gedankengang:
    Der Kontext sagt uns, dass Maria größer als Jana ist.
    Es heißt auch, dass Jana kleiner als Tom ist.
    Und Tom ist gleich groß wie David.
    Die Reihenfolge von groß nach klein ist also: Maria, Tom/David, Jana.
    Daher muss Maria die größte Person sein.

    ## Beispiel 2
    Kontext: In der Moodle-Dokumentation wird beschrieben, dass Kurse in Kategorien organisiert werden können. Administratoren können Kategorien erstellen und Kursleiter können ihre Kurse in diesen Kategorien platzieren. Außerdem können Kurse verschiedene Formate haben, wie z.B. Wochenformat oder Themenformat.
    Frage: Wie organisiert Moodle Kurse?
    Gedankengang:
    Der Kontext beschreibt, wie Kurse in Moodle organisiert werden.
    Es wird erwähnt, dass Kurse in Kategorien organisiert werden können.
    Administratoren können diese Kategorien erstellen.
    Kursleiter können dann ihre Kurse in diesen Kategorien platzieren.
    Zusätzlich können Kurse verschiedene Formate haben, wie Wochen- oder Themenformat.
    Die Antwort ist also: Moodle organisiert Kurse in Kategorien, die von Administratoren erstellt werden, und Kurse können verschiedene Formate wie Wochen- oder Themenformat haben.

    ## Beispiel 3
    Kontext: Die Moodle-Plattform wurde 2002 von Martin Dougiamas gegründet.
    Frage: Wann wurde die Moodle-App für iOS veröffentlicht?
    Gedankengang:
    Der Kontext enthält nur Informationen darüber, wann Moodle gegründet wurde (2002) und von wem (Martin Dougiamas).
    Es gibt keine Informationen darüber, wann die Moodle-App für iOS veröffentlicht wurde.
    Ohne zusätzlichen Kontext kann diese Frage nicht beantwortet werden.
    
    Wende Chain-of-Thought-Reasoning auf die folgende Frage an. Arbeite schrittweise und beantworte die Frage, nur wenn ausreichend Informationen im Kontext vorhanden sind.
    
    Kontext:
    {context}
    
    Frage:
    {question}
    """
    
    question_answer_from_context_cot_prompt = PromptTemplate(
        template=question_answer_cot_prompt_template,
        input_variables=["context", "question"],
    )
    
    question_answer_from_context_cot_llm = get_llm(temperature=0)
    question_answer_from_context_cot_chain = question_answer_from_context_cot_prompt | question_answer_from_context_cot_llm.with_structured_output(
        QuestionAnswerFromContext,
        method="function_calling",
        strict=True
    )
    
    try:
        input_data = {"question": question, "context": context}
        output = question_answer_from_context_cot_chain.invoke(input_data)
        intermediate_answer = output.answer_based_on_content

        await cl.Message(content=f"Intermediate Answer generated (added to context).").send()

        if "aggregated_filtered_context" not in state or state["aggregated_filtered_context"] is None:
            state["aggregated_filtered_context"] = ""
        state["aggregated_filtered_context"] += f"\\n\\nIntermediate Answer to '{question}': {intermediate_answer}"

    except Exception as e:
        await cl.Message(content=f"Error during intermediate answer generation: {e}. Skipping.").send()

    state["curr_context"] = ""
    return state

@traceable(pass_config=False)
@cl.step(name="Generate Final Answer", type="llm")
async def run_qualtative_answer_workflow_for_final_answer(state: PlanExecute):
    state["curr_state"] = "get_final_answer"

    question = state["question"]
    context = state.get("aggregated_filtered_context", "")
    answerability = state.get("answerability_status", "can_be_answered_already") # Default to full answer attempt if status missing

    await cl.Message(content=f"Generating final answer (status: {answerability})...").send()

    if not context or not context.strip():
        await cl.Message(content="Aggregated context is empty. Cannot generate final answer.").send()
        state["response"] = {"answer": "I could not find enough information to answer the question based on the provided documents."}
        return state

    # Adjust prompt based on whether the answer should be full or partial
    if answerability == "partially_answered":
        final_prompt_template = (
            "Based on the following accumulated information:\n{context}\n\n" + 
            "While the context doesn't seem to contain the *exact* specific detail requested (e.g., a concrete code snippet), " +
            "please synthesize the available relevant information to provide the best possible partial answer to the question: {question}\n\n" + 
            "Explain what information *is* available and clearly state what specific details are missing or where they might be found " +
            "(if mentioned in the context, e.g., 'examples available on the support portal').\n" +
            "Use a Chain-of-Thought reasoning process."
        )
    else: # Assume 'can_be_answered_already' or unknown defaults to full answer attempt
        final_prompt_template = (
            "Based on the following accumulated information:\n{context}\n\n" +
            "Provide a comprehensive final answer to the question: {question}\n\n" +
            "Use a Chain-of-Thought reasoning process to arrive at the answer."
        )

    final_answer_prompt = PromptTemplate(
        template=final_prompt_template,
        input_variables=["context", "question"],
    )

    final_answer_llm = get_llm(temperature=0.1)
    final_answer_chain = final_answer_prompt | final_answer_llm.with_structured_output(
        QuestionAnswerFromContext, # Still expect a single 'answer' field
        method="function_calling",
        strict=True
    )

    try:
        input_data = {"question": question, "context": context}
        output = final_answer_chain.invoke(input_data)
        final_answer = output.answer_based_on_content
        state["response"] = {"answer": final_answer}
    except Exception as e:
        await cl.Message(content=f"Error during final answer generation: {e}.").send()
        state["response"] = {"answer": f"An error occurred while generating the final answer: {e}"}

    return state