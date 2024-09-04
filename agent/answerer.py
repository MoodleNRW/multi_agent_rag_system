# agent/answerer.py

import chainlit as cl
from .state import PlanExecute
from langchain_openai import ChatOpenAI 
from langchain.prompts import PromptTemplate

@cl.step(name="Generate Answer", type="tool")
async def run_qualtative_answer_workflow(state: PlanExecute):
    """Generates an answer to a given question based on the provided context."""
    
    answer_prompt_template = """Based on the following context, please answer the question.
    Context: {context}
    Question: {question}
    Please provide a detailed and accurate answer based solely on the information given in the context.
    """

    answer_prompt = PromptTemplate(
        template=answer_prompt_template,
        input_variables=["context", "question"],
    )

    answer_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    answer_chain = answer_prompt | answer_llm

    response = answer_chain.invoke({
        "context": state["curr_context"],
        "question": state["query_to_retrieve_or_answer"]
    })

    state["response"] = response.content
    state["aggregated_context"] += f"\nGenerated answer: {response.content}"

    return state

@cl.step(name="Generate Final Answer", type="tool")
async def run_qualtative_answer_workflow_for_final_answer(state: PlanExecute):
    final_answer_prompt_template = """Based on all the information we've gathered, please provide a final, comprehensive answer to the original question.

    Original question: {question}
    Aggregated context: {aggregated_context}

    Please synthesize all the information and provide a detailed, accurate, and complete answer to the original question.
    Keep Urls and references to the original sources in the answer.
    """

    final_answer_prompt = PromptTemplate(
        template=final_answer_prompt_template,
        input_variables=["question", "aggregated_context"],
    )

    final_answer_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    final_answer_chain = final_answer_prompt | final_answer_llm

    response = final_answer_chain.invoke({
        "question": state["question"],
        "aggregated_context": state["aggregated_context"]
    })

    state["response"] = response.content

    return state