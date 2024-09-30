# agent/task_handler.py

import chainlit as cl
from .state import PlanExecute
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

class TaskHandlerOutput(BaseModel):
    """Output schema for the task handler."""
    query: str = Field(description="The query to be either retrieved from the vector store, the question that should be answered from context or to be used to create a moodle course.")
    curr_context: str = Field(description="The context to be based on in order to answer the query or create a moodle course.")
    tool: str = Field(description="The tool to be used should be either retrieve_chunks, retrieve_summaries, retrieve_quotes, answer_from_context or create_moodle_course.")

@cl.step(name="Task Handler", type="process")
async def run_task_handler_chain(state: PlanExecute):
    """ Run the task handler chain to decide which tool to use to execute the task.
    Args:
       state: The current state of the plan execution.
    Returns:
       The updated state of the plan execution.
    """
    state["curr_state"] = "task_handler"

    task_handler_prompt_template = """You are a task handler that receives a task {curr_task} and have to decide which tool to use to execute the task.
    You have the following tools at your disposal:
    Tool A: a tool that retrieves relevant information from a vector store of chunks based on a given query.
    - use Tool A when you think the current task should search for information in the chunks.
    Tool B: a tool that retrieves relevant information from a vector store of chapter summaries based on a given query.
    - use Tool B when you think the current task should search for information in the chapter summaries.
    Tool C: a tool that retrieves relevant information from a vector store of quotes from the based on a given query.
    - use Tool C when you think the current task should search for information in the quotes.
    Tool D: a tool that answers a question from a given context.
    - use Tool D ONLY when you think the current task can be answered by the aggregated context {aggregated_context}
    Tool E: a tool that creates a moodle course. You have to provide the context for the moodle course. You dont need to use retrieve_chunks, retrieve_summaries, retrieve_quotes, or answer_from_context if you choose this tool.
    - use Tool E when you think the current task should create a moodle course based on the context.

    You also receive the last tool used {last_tool}
    If {last_tool} was retrieve_chunks, use other tools than Tool A.

    You also have the past steps {past_steps} that you can use to make decisions and understand the context of the task.
    You also have the initial user's question {question} that you can use to make decisions and understand the context of the task.
    If you decide to use Tools A, B or C, output the query to be used for the tool and also output the relevant tool.
    If you decide to use Tool D, output the question to be used for the tool, the context, and also that the tool to be used is Tool D.
    If you decide to use Tool E, output the context and also that the tool to be used is Tool E.

    Output your decision in JSON format.
    """

    task_handler_prompt = PromptTemplate(
        template=task_handler_prompt_template,
        input_variables=["curr_task", "aggregated_context", "last_tool", "past_steps", "question"],
    )

    task_handler_llm = get_llm()
    task_handler_chain = task_handler_prompt | task_handler_llm.with_structured_output(TaskHandlerOutput,  strict = True)

    if not state["plan"]:
        # If there are no more steps in the plan, we're done
        state["tool"] = "done"
        return

    curr_task = state["plan"].pop(0)  # Get the next task and remove it from the plan
    
    result = task_handler_chain.invoke({
        "curr_task": curr_task,
        "aggregated_context": state["aggregated_context"],
        "last_tool": state.get("tool", ""),
        "past_steps": state["past_steps"],
        "question": state["question"]
    })

    state["query_to_retrieve_or_answer"] = result.query

    if result.tool == "answer_from_context":
        state["curr_context"] = result.curr_context  
        state["tool"] = "answer"
    else:
        state["tool"] = result.tool

         
    state["past_steps"].append(curr_task)

    # Log the decision for debugging
    cl.Task(title=f"Task: {curr_task}", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Chosen Tool: {state['tool']}", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Query: {state['query_to_retrieve_or_answer']}", status=cl.TaskStatus.DONE)

    return state