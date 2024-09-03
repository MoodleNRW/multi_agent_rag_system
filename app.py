import chainlit as cl
from openai import OpenAI
import langgraph
from textwrap import wrap as text_wrap
from config_manager import ConfigManager
from agent.graph import compile_workflow

base_url = "https://api.openai.com/v1"
config_manager = ConfigManager(base_url)

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
    model = config_manager.get_setting_value("ACTIVEMODEL")
    temperature = float(config_manager.get_setting_value("TEMPERATURE"))
    max_tokens = int(config_manager.get_setting_value("MAXTOKENS"))

    if not api_key:
        await cl.Message(content="Please set your API key in the settings.").send()
        return
    
    # if not model:
    #     await cl.Message(content="Please select a model in the settings before sending a message.").send()
    #     return

    # Ensure temperature and max_tokens are set
    if temperature is None:
        temperature = 0.7  # Default temperature
    if max_tokens is None:
        max_tokens = 4000  # Default max tokens
    
    msg = cl.Message(content=message)
    
    try:
        input = {"question": message.content}
        final_answer, final_state = execute_plan_and_print_steps(input)
        await cl.Message(content=final_answer).send()
        print(f'final state: {final_state}')
        await msg.update()
    except Exception as e:
        await cl.Message(content=f"An error occurred: {str(e)}").send()


@cl.step(type="llm")
def execute_plan_and_print_steps(inputs, recursion_limit=45):
    """
    Execute the plan and print the steps.
    Args:
        inputs: The inputs to the plan.
        recursion_limit: The recursion limit.
    Returns:
        The response and the final state.
    """
    
    config = {"recursion_limit": recursion_limit}

    try:    
        for plan_output in compile_workflow().stream(inputs, config=config):
            for _, agent_state_value in plan_output.items():
                pass
                print(f' curr step: {agent_state_value}')
        response = agent_state_value['response']
    except langgraph.pregel.GraphRecursionError:
        response = "The answer wasn't found in the data."
    final_state = agent_state_value

    return response, final_state


if __name__ == "__main__":
    cl.run()