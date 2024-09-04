# agent/answerer.py

from typing import TypedDict
import chainlit as cl
from .state import PlanExecute
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

# Define the QuestionAnswerFromContext model and the CoT chain
class QuestionAnswerFromContext(BaseModel):
    answer_based_on_content: str = Field(description="Generates an answer to a query based on a given context.")

# LLM setup for answering questions using chain of thought reasoning
question_answer_from_context_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)

question_answer_cot_prompt_template = """
Examples of Chain-of-Thought Reasoning

Example 1
Context: Mary is taller than Jane. Jane is shorter than Tom. Tom is the same height as David.
Question: Who is the tallest person?
Reasoning Chain:
The context tells us Mary is taller than Jane
It also says Jane is shorter than Tom
And Tom is the same height as David
So the order from tallest to shortest is: Mary, Tom/David, Jane
Therefore, Mary must be the tallest person

Example 2
Context: Harry was reading a book about magic spells. One spell allowed the caster to turn a person into an animal for a short time. Another spell could levitate objects.
A third spell created a bright light at the end of the caster's wand.
Question: Based on the context, if Harry cast these spells, what could he do?
Reasoning Chain:
The context describes three different magic spells
The first spell allows turning a person into an animal temporarily
The second spell can levitate or float objects
The third spell creates a bright light
If Harry cast these spells, he could turn someone into an animal for a while, make objects float, and create a bright light source
So based on the context, if Harry cast these spells he could transform people, levitate things, and illuminate an area

Instructions: For the question below, provide your answer by first showing your step-by-step reasoning process, breaking down the problem into a chain of thought before arriving at the final answer, just like in the previous examples.

Context: {context}
Question: {question}
"""

question_answer_from_context_cot_prompt = PromptTemplate(
    template=question_answer_cot_prompt_template,
    input_variables=["context", "question"],
)

# Chain that combines the prompt template with the LLM and structured output
question_answer_from_context_cot_chain = question_answer_from_context_cot_prompt | question_answer_from_context_llm.with_structured_output(QuestionAnswerFromContext)


# Answer question function with CoT reasoning
def answer_question_from_context(state):
    """
    Answers a question from a given context using Chain-of-Thought reasoning.

    Args:
        state: The current state of the process which contains the question and context.

    Returns:
        A dictionary containing the answer, context, and question.
    """
    question = state["question"]
    context = state.get("aggregated_context", state["context"])

    input_data = {
        "question": question,
        "context": context
    }

    print("Answering the question from the retrieved context using CoT reasoning...")

    # Use the Chain-of-Thought reasoning process
    output = question_answer_from_context_cot_chain.invoke(input_data)
    answer = output.answer_based_on_content
    print(f'answer before checking hallucination: {answer}')
    
    return {"answer": answer, "context": context, "question": question}


# Define the is_grounded_on_facts model and chain
class is_grounded_on_facts(BaseModel):
    """
    Output schema for the grounded-on-facts check.
    """
    grounded_on_facts: bool = Field(description="Answer is grounded in the facts, 'yes' or 'no'")

is_grounded_on_facts_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)

is_grounded_on_facts_prompt_template = """You are a fact-checker that determines if the given answer {answer} is grounded in the given context {context}.
You don't mind if it doesn't make sense, as long as it is grounded in the context.
Output a JSON containing the answer to the question, and apart from the JSON format, don't output any additional text.
"""

is_grounded_on_facts_prompt = PromptTemplate(
    template=is_grounded_on_facts_prompt_template,
    input_variables=["context", "answer"],
)

# Chain that combines the prompt template with the LLM and structured output
is_grounded_on_facts_chain = is_grounded_on_facts_prompt | is_grounded_on_facts_llm.with_structured_output(is_grounded_on_facts)


# Function to check if the answer is grounded in context
def is_answer_grounded_on_context(state):
    """Determines if the answer to the question is grounded in the facts.
    
    Args:
        state: A dictionary containing the context and answer.
    """
    print("Checking if the answer is grounded in the facts...")
    context = state["context"]
    answer = state["answer"]
    
    result = is_grounded_on_facts_chain.invoke({"context": context, "answer": answer})
    grounded_on_facts = result.grounded_on_facts
    if not grounded_on_facts:
        print("The answer is hallucination.")
        return "hallucination"
    else:
        print("The answer is grounded in the facts.")
        return "grounded on context"


# Define the state model using TypedDict
class QualitativeAnswerGraphState(TypedDict):
    """
    Represents the state of our qualitative answer graph.
    """
    question: str
    context: str
    answer: str


# Define the workflow graph using StateGraph
qualitative_answer_workflow = StateGraph(QualitativeAnswerGraphState)

# Add the node that calls the answer function
qualitative_answer_workflow.add_node("answer_question_from_context", answer_question_from_context)

# Add conditional edges to handle grounded vs hallucination cases
qualitative_answer_workflow.add_conditional_edges(
    "answer_question_from_context",
    is_answer_grounded_on_context,
    {"hallucination": "answer_question_from_context", "grounded on context": END}
)

# Compile the workflow graph
qualitative_answer_workflow_app = qualitative_answer_workflow.compile()


# Chainlit step to run the workflow for generating an answer
@cl.step(name="Generate Answer", type="tool")
async def run_qualtative_answer_workflow(state: PlanExecute):
    """
    Run the qualitative answer workflow to generate an answer.
    
    Args:
        state: The current state of the plan execution.
    
    Returns:
        The state with the updated aggregated context and answer.
    """
    
    state["curr_state"] = "answer"

    # Now this will use the answer_question_from_context CoT logic.
    response = answer_question_from_context(state)
    
    state["response"] = response["answer"]
    state["aggregated_context"] += f"\nGenerated answer: {response['answer']}"

    return state


# Chainlit step to generate the final answer after synthesizing all the context
@cl.step(name="Generate Final Answer", type="tool")
async def run_qualtative_answer_workflow_for_final_answer(state: PlanExecute):
    """
    Generate a final answer by synthesizing all the information gathered.
    
    Args:
        state: The current state of the plan execution.
    
    Returns:
        The final comprehensive answer.
    """
    final_answer_prompt_template = """Based on all the information we've gathered, please provide a final, comprehensive answer to the original question.

    Original question: {question}
    Aggregated context: {aggregated_context}

    Please synthesize all the information and provide a detailed, accurate, and complete answer to the original question.
    Keep URLs and references to the original sources in the answer.
    """

    final_answer_prompt = PromptTemplate(
        template=final_answer_prompt_template,
        input_variables=["question", "aggregated_context"],
    )

    final_answer_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=4000)
    final_answer_chain = final_answer_prompt | final_answer_llm

    response = final_answer_chain.invoke({
        "question": state["question"],
        "aggregated_context": state["aggregated_context"]
    })

    state["response"] = response.content

    return state
