# agent/task_handler.py

import chainlit as cl
from langsmith import traceable
from typing import Dict, List, Optional
from langchain.prompts import PromptTemplate
import json
from models.models_wrapper import get_llm
from pydantic import BaseModel, Field
from .state import PlanExecute

class TaskHandlerOutput(BaseModel):
    """Output schema for the task handler."""
    query: str = Field(description="The query to be either retrieved from the vector store, the question that should be answered from context or to be used to create a moodle course.")
    curr_context: str = Field(description="The context to be based on in order to answer the query or create a moodle course.")
    tool: str = Field(description="The tool to be used should be either retrieve_chunks, retrieve_summaries, retrieve_quotes, parallel_retrieval, answer or create_moodle_course.")

@traceable(pass_config=False)
@cl.step(name="Task Handler", type="process")
async def run_task_handler_chain(state: PlanExecute):
    """ Run the task handler chain to decide which tool to use to execute the task.
    Args:
       state: The current state of the plan execution.
    Returns:
       The updated state of the plan execution.
    """
    state["curr_state"] = "task_handler"

    task_handler_prompt_template = """You are a Task Handler AI responsible for selecting the most appropriate tool to execute the current task: '{curr_task}'.

### 🧰 AVAILABLE TOOLS:

#### Information Retrieval Tools:
✅ **Tool A (check_faq)**: Searches the FAQ database for matching answers.
   - ALWAYS use this tool FIRST before any other retrieval tools
   - Best for: Frequently asked questions with pre-existing answers

📄 **Tool B (retrieve_chunks)**: Retrieves relevant information from text chunks in the vector store.
   - Best for: Detailed questions requiring precise information, technical details, step-by-step guides, specific error messages

📚 **Tool C (retrieve_summaries)**: Retrieves information from chapter summaries in the vector store.
   - Best for: Overview questions, conceptual understanding, introductions to topics, broader context

💬 **Tool D (retrieve_quotes)**: Retrieves information from quotes in the vector store.
   - Best for: Definition requests, official guidelines, exact wording, policy information

🔄 **Tool E (parallel_retrieval)**: Runs all three retrieval methods (chunks, summaries, quotes) in parallel and combines results.
   - Best for: Complex questions benefiting from multiple information sources, initial topic inquiries, multi-part questions

#### Action Tools:
✏️ **Tool F (answer)**: Directly answers a question using the aggregated context.
   - ONLY use when you have sufficient information in the aggregated context: {aggregated_context}

🏫 **Tool G (create_moodle_course)**: Creates a Moodle course based on provided context.
   - Use when the task explicitly requires creating a Moodle course

### 📋 DECISION PROTOCOL:

1. ALWAYS start with Tool A (check_faq) to check if the question has already been answered
2. If Tool A finds no matching FAQ or fails, use Tool E (parallel_retrieval) for initial information gathering
3. Check {past_steps} and {last_tool} to determine what information has already been retrieved
4. If {last_tool} was "retrieve_chunks", "retrieve_summaries", or "retrieve_quotes" and found no relevant information, use Tool E

### 📊 CONTEXT INFORMATION:

- Last tool used: {last_tool}
- Previous steps taken: {past_steps}
- Original user question: {question}

### 📤 OUTPUT FORMAT:

For Tools A, B, C, D, or E:
```json
{{
  "query": "specific query to use with the tool",
  "curr_context": "",
  "tool": "tool_name" 
}}
```

For Tool F:
```json
{{
  "query": "question to be answered",
  "curr_context": "context to use for answering",
  "tool": "answer"
}}
```

For Tool G:
```json
{{
  "query": "",
  "curr_context": "context for Moodle course creation",
  "tool": "create_moodle_course"
}}
```

Always ensure your output strictly follows the TaskHandlerOutput schema with "query", "curr_context", and "tool" fields.
"""

    task_handler_prompt = PromptTemplate(
        template=task_handler_prompt_template,
        input_variables=["curr_task", "aggregated_context", "last_tool", "past_steps", "question"],
    )

    task_handler_llm = get_llm()
    task_handler_chain = task_handler_prompt | task_handler_llm.with_structured_output(
        TaskHandlerOutput,  
        method="function_calling",  # Explizit function_calling verwenden
        strict=True
    )

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

    # Überprüfe, ob ein gültiges Tool zurückgegeben wurde
    valid_tools = ["check_faq", "retrieve_chunks", "retrieve_summaries", "retrieve_quotes", "parallel_retrieval", "answer", "create_moodle_course"]
    
    if not result.tool or result.tool.strip() == "" or result.tool not in valid_tools:
        # Wenn kein gültiges Tool zurückgegeben wurde, verwende standardmäßig check_faq
        await cl.Message(content=f"⚠️ Kein gültiges Tool erkannt. Überprüfe zuerst die FAQs.").send()
        result.tool = "check_faq"
    
    # Prüfe, ob bereits ein Retrieval-Tool verwendet wurde
    retrieval_tools = ["check_faq", "retrieve_chunks", "retrieve_summaries", "retrieve_quotes", "parallel_retrieval"]
    past_retrieval_tools = [step for step in state.get("past_tool_usage", []) if step in retrieval_tools]
    
    # Wenn noch kein Retrieval-Tool verwendet wurde, starte mit FAQ-Check
    if not past_retrieval_tools and result.tool in retrieval_tools and result.tool != "check_faq":
        await cl.Message(content=f"🔄 Erster Informationsabruf: Überprüfe zuerst die FAQs").send()
        result.tool = "check_faq"
    
    # Aktualisiere die Liste der verwendeten Tools
    if "past_tool_usage" not in state:
        state["past_tool_usage"] = []
    state["past_tool_usage"].append(result.tool)
    
    if result.tool == "answer":
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