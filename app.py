import chainlit as cl
from config_manager import ConfigManager
from agent.execution import execute_plan_and_print_steps
from agent.graph import compile_workflow

# Initialize ConfigManager
config_manager = ConfigManager()

@cl.on_chat_start
async def start():
    settings = await config_manager.load_settings()
    chat_settings = cl.ChatSettings(settings)
    await chat_settings.send()

@cl.on_settings_update
async def update_settings(settings):
    await config_manager.update_settings(settings)

@cl.on_message
async def main(message: cl.Message):
    api_key = config_manager.get_setting_value("OPENAI_API_KEY")
    if not api_key:
        await cl.Message(content="Please set your API key in the settings.").send()
        return
    
    try:
        # Compile the workflow
        plan_and_execute_app = compile_workflow()
        
        # Start the execution of the plan
        response, final_state = execute_plan_and_print_steps(plan_and_execute_app, {"question": message.content})
        
        # Send the final response back to the user
        await cl.Message(content=response).send()

        # Optionally, log the final state for debugging purposes
        print(f'Final state: {final_state}')
    except Exception as e:
        # Handle errors and notify the user
        await cl.Message(content=f"An error occurred: {str(e)}").send()

if __name__ == "__main__":
    cl.run()
