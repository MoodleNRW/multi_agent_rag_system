#todo delete

import langgraph
from textwrap import wrap as text_wrap
import chainlit as cl

@cl.step(type="tool")
def execute_plan_and_print_steps(compiled_workflow, inputs, recursion_limit=45):
    """
    Execute the plan and print the steps.
    Args:
        compiled_workflow: The application or workflow to be executed.
        inputs: The inputs to the plan.
        recursion_limit: The recursion limit.
    Returns:
        The response and the final state.
    """
    
    config = {"recursion_limit": recursion_limit}
    try:    
        for plan_output in compiled_workflow.stream(inputs, config=config):
            for _, agent_state_value in plan_output.items():
                pass
                print(f' curr step: {agent_state_value}')
        response = agent_state_value['response']
    except langgraph.pregel.GraphRecursionError:
        response = "The answer wasn't found in the data."
    final_state = agent_state_value
    return response, final_state