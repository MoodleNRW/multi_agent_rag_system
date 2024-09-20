import os
import chainlit as cl
from config.config_manager import ConfigManager
from agent.state import PlanExecute
from agent.graph import compile_workflow
from vector_stores.retriever import create_retrievers

# Initialize ConfigManager
config_manager = ConfigManager()

@cl.on_chat_start
async def start():
    # Load and send settings
    settings = await config_manager.load_settings()
    chat_settings = cl.ChatSettings(settings)
    await chat_settings.send()
    
    # Initialize vector store retrievers
    chunks_retriever, summaries_retriever, quotes_retriever = create_retrievers()
    cl.user_session.set("retrievers", {
        "chunks": chunks_retriever,
        "summaries": summaries_retriever,
        "quotes": quotes_retriever
    })
    
    # Send welcome message
    await cl.Message(content="Welcome! I'm ready to answer your questions about Moodle ✅. What would you like to know or do?").send()

@cl.on_settings_update
async def update_settings(settings):
    await config_manager.update_settings(settings)

@cl.on_message
async def main(message: cl.Message):
    openai_api_key = config_manager.get_setting_value("OPENAI_API_KEY")
    
    if not openai_api_key:
        await cl.Message(content="Please set your OpenAI API key in the settings.").send()
        return
    
    try:
        await process_message(message.content)
    except Exception as e:
        await cl.Message(content=f"An error occurred: {str(e)}").send()

@cl.step(name="Process Message", type="process")
async def process_message(message_content: str):
    # Compile the workflow
    workflow = await compile_workflow()
    
    # Initialize the state
    initial_state = PlanExecute(
        question=message_content,
        anonymized_question="",
        query_to_retrieve_or_answer="",
        plan=[],
        past_steps=[],
        mapping={},
        curr_context="",
        aggregated_context="",
        tool="",
        response=""
    )
    
    # Execute the workflow
    async for step_output in workflow.astream(initial_state):
        first_key = next(iter(step_output))
        await update_ui(step_output[first_key])
    
    # Send the final response
    final_response = step_output[first_key].get("response", "I couldn't generate a response. Please try rephrasing your question.")
    await cl.Message(content=final_response).send()

async def update_ui(step_output):
    current_state = step_output.get("curr_state", "")
    print("UPDATE UI", step_output)
    if current_state in ["retrieve_chunks", "retrieve_summaries", "retrieve_quotes"]:
        await cl.Message(content=f"Retrieving information: {current_state}").send()
    elif current_state == "answer":
        await cl.Message(content="Generating answer based on retrieved information...").send()
    elif current_state == "planner":
        await cl.Message(content="Planning next steps...").send()
    elif current_state == "anonymize_question":
        await cl.Message(content="Anonymizing the question...").send()
    elif current_state == "de_anonymize_plan":
        await cl.Message(content="De-anonymizing the plan...").send()
    elif current_state == "break_down_plan":
        await cl.Message(content="Breaking down the plan into smaller steps...").send()
    elif current_state == "task_handler":
        await cl.Message(content="Deciding on the next action...").send()
    elif current_state == "replan":
        await cl.Message(content="Adjusting the plan based on new information...").send()
    elif current_state == "get_final_answer":
        await cl.Message(content="Preparing the final answer...").send()

    # You can add more detailed logging here if needed
    cl.Task(title=current_state, status=cl.TaskStatus.RUNNING)

if __name__ == "__main__":
    cl.run()