from agent.action import anonymize, deanonymize
from agent.state import AgentGraphState

def anonymize_queries(state: AgentGraphState):
    """
    Anonymizes the question.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the anonymized question and mapping.
    """
    state["curr_state"] = "anonymize_question"
    print("Anonymizing question")
    pprint("--------------------")
    anonymized_question_output = anonymize_question(state['question'])
    anonymized_question = anonymized_question_output["anonymized_question"]
    print(f'anonymized_query: {anonymized_question}')
    pprint("--------------------")
    mapping = anonymized_question_output["mapping"]
    state["anonymized_question"] = anonymized_question
    state["mapping"] = mapping
    return state

def plan_step(state: AgentGraphState):
    """
    Plans the next step.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the plan.
    """
    state["curr_state"] = "planner"
    print("Planning step")
    pprint("--------------------")
    plan = generate_plan(state['anonymized_question'])
    state["plan"] = plan
    print(f'plan: {state["plan"]}')
    return state

def deanonymize_queries(state: AgentGraphState):
    """
    De-anonymizes the plan.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the de-anonymized plan.
    """
    state["curr_state"] = "deanonymize_plan"
    print("De-anonymizing plan")
    pprint("--------------------")
    deanonimized_plan = deanonymize_plan(state["plan"], state["question"])
    state["plan"] = deanonimized_plan
    print(f'de-anonymized_plan: {deanonimized_plan}')
    return state

def break_down_plan_step(state: AgentGraphState):
    """
    Breaks down the plan steps into retrievable or answerable tasks.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the refined plan.
    """
    state["curr_state"] = "break_down_plan"
    print("Breaking down plan steps into retrievable or answerable tasks")
    pprint("--------------------")
    refined_plan = break_down_plan(state["plan"])
    state["plan"] = refined_plan
    return state

# Example of processing a question
def execute_full_process(state: AgentGraphState):
    state = anonymize_queries(state)
    state = plan_step(state)
    state = deanonymize_queries(state)
    state = break_down_plan_step(state)
    return state