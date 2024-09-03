
from agent.state import AgentGraphState
from agent.nodes import anonymize_question_chain



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
    print("--------------------")
    anonymized_question_output = anonymize_question_chain.invoke(state['question'])
    anonymized_question = anonymized_question_output["anonymized_question"]
    # print(f'anonimized_querry: {anonymized_question}')
    # print("--------------------")
    # mapping = anonymized_question_output["mapping"]
    state["anonymized_question"] = anonymized_question
    # state["mapping"] = mapping
    return state


# def deanonymize_queries(state: AgentGraphState):
#     """
#     De-anonymizes the plan.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         The updated state with the de-anonymized plan.
#     """
#     state["curr_state"] = "de_anonymize_plan"
#     print("De-anonymizing plan")
#     print("--------------------")
#     deanonimzed_plan = de_anonymize_plan_chain.invoke({"plan": state["plan"], "mapping": state["mapping"]})
#     state["plan"] = deanonimzed_plan.plan
#     print(f'de-anonimized_plan: {deanonimzed_plan.plan}')
#     return state


# def plan_step(state: AgentGraphState):
#     """
#     Plans the next step.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         The updated state with the plan.
#     """
#     state["curr_state"] = "planner"
#     print("Planning step")
#     pprint("--------------------")
#     plan = planner.invoke({"question": state['anonymized_question']})
#     state["plan"] = plan.steps
#     print(f'plan: {state["plan"]}')
#     return state





# def break_down_plan_step(state: AgentGraphState):
#     """
#     Breaks down the plan steps into retrievable or answerable tasks.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         The updated state with the refined plan.
#     """
#     state["curr_state"] = "break_down_plan"
#     print("Breaking down plan steps into retrievable or answerable tasks")
#     pprint("--------------------")
#     refined_plan = break_down_plan_chain.invoke(state["plan"])
#     state["plan"] = refined_plan.steps
#     return state



# def replan_step(state: AgentGraphState):
#     """
#     Replans the next step.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         The updated state with the plan.
#     """
#     state["curr_state"] = "replan"
#     print("Replanning step")
#     pprint("--------------------")
#     inputs = {"question": state["question"], "plan": state["plan"], "past_steps": state["past_steps"], "aggregated_context": state["aggregated_context"]}
#     output = replanner.invoke(inputs)
#     state["plan"] = output['plan']['steps']
#     return state


# def can_be_answered(state: AgentGraphState):
#     """
#     Determines if the question can be answered.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         whether the original question can be answered or not.
#     """
#     state["curr_state"] = "can_be_answered_already"
#     print("Checking if the ORIGINAL QUESTION can be answered already")
#     pprint("--------------------")
#     question = state["question"]
#     context = state["aggregated_context"]
#     inputs = {"question": question, "context": context}
#     output = can_be_answered_already_chain.invoke(inputs)
#     if output.can_be_answered == True:
#         print("The ORIGINAL QUESTION can be fully answered already.")
#         pprint("--------------------")
#         print("the aggregated context is:")
#         print(text_wrap(state["aggregated_context"]))
#         print("--------------------")
#         return "can_be_answered_already"
#     else:
#         print("The ORIGINAL QUESTION cannot be fully answered yet.")
#         pprint("--------------------")
#         return "cannot_be_answered_yet"



# def run_task_handler_chain(state: AgentGraphState):
#     """ Run the task handler chain to decide which tool to use to execute the task.
#     Args:
#        state: The current state of the plan execution.
#     Returns:
#        The updated state of the plan execution.
#     """
#     state["curr_state"] = "task_handler"
#     print("the current plan is:")
#     print(state["plan"])
#     print("--------------------") 

#     if not state['past_steps']:
#         state["past_steps"] = []

#     curr_task = state["plan"][0]

#     inputs = {"curr_task": curr_task,
#                "aggregated_context": state["aggregated_context"],
#                 "last_tool": state["tool"],
#                 "past_steps": state["past_steps"],
#                 "question": state["question"]}
    
#     output = task_handler_chain.invoke(inputs)
  
#     state["past_steps"].append(curr_task)
#     state["plan"].pop(0)

#     if output.tool == "retrieve_chunks":
#         state["query_to_retrieve_or_answer"] = output.query
#         state["tool"]="retrieve_chunks"
    
#     elif output.tool == "retrieve_summaries":
#         state["query_to_retrieve_or_answer"] = output.query
#         state["tool"]="retrieve_summaries"

#     elif output.tool == "retrieve_quotes":
#         state["query_to_retrieve_or_answer"] = output.query
#         state["tool"]="retrieve_quotes"

    
#     elif output.tool == "answer_from_context":
#         state["query_to_retrieve_or_answer"] = output.query
#         state["curr_context"] = output.curr_context
#         state["tool"]="answer"
#     else:
#         raise ValueError("Invalid tool was outputed. Must be either 'retrieve' or 'answer_from_context'")
#     return state  



# def retrieve_or_answer(state: AgentGraphState):
#     """Decide whether to retrieve or answer the question based on the current state.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         updates the tool to use .
#     """
#     state["curr_state"] = "decide_tool"
#     print("deciding whether to retrieve or answer")
#     if state["tool"] == "retrieve_chunks":
#         return "chosen_tool_is_retrieve_chunks"
#     elif state["tool"] == "retrieve_summaries":
#         return "chosen_tool_is_retrieve_summaries"
#     elif state["tool"] == "retrieve_quotes":
#         return "chosen_tool_is_retrieve_quotes"
#     elif state["tool"] == "answer":
#         return "chosen_tool_is_answer"
#     else:
#         raise ValueError("Invalid tool was outputed. Must be either 'retrieve' or 'answer_from_context'")  

# def run_qualitative_chunks_retrieval_workflow(state):
#     """
#     Run the qualitative chunks retrieval workflow.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         The state with the updated aggregated context.
#     """
#     state["curr_state"] = "retrieve_chunks"
#     print("Running the qualitative chunks retrieval workflow...")
#     question = state["query_to_retrieve_or_answer"]
#     inputs = {"question": question}
#     for output in qualitative_chunks_retrieval_workflow_app.stream(inputs):
#         for _, _ in output.items():
#             pass 
#         print("--------------------")
#     if not state["aggregated_context"]:
#         state["aggregated_context"] = ""
#     state["aggregated_context"] += output['relevant_context']
#     return state

# def run_qualitative_summaries_retrieval_workflow(state):
#     """
#     Run the qualitative summaries retrieval workflow.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         The state with the updated aggregated context.
#     """
#     state["curr_state"] = "retrieve_summaries"
#     print("Running the qualitative summaries retrieval workflow...")
#     question = state["query_to_retrieve_or_answer"]
#     inputs = {"question": question}
#     for output in qualitative_summaries_retrieval_workflow_app.stream(inputs):
#         for _, _ in output.items():
#             pass 
#         print("--------------------")
#     if not state["aggregated_context"]:
#         state["aggregated_context"] = ""
#     state["aggregated_context"] += output['relevant_context']
#     return state

# def run_qualitative_book_quotes_retrieval_workflow(state):
#     """
#     Run the qualitative book quotes retrieval workflow.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         The state with the updated aggregated context.
#     """
#     state["curr_state"] = "retrieve_book_quotes"
#     print("Running the qualitative book quotes retrieval workflow...")
#     question = state["query_to_retrieve_or_answer"]
#     inputs = {"question": question}
#     for output in qualitative_book_quotes_retrieval_workflow_app.stream(inputs):
#         for _, _ in output.items():
#             pass 
#         print("--------------------")
#     if not state["aggregated_context"]:
#         state["aggregated_context"] = ""
#     state["aggregated_context"] += output['relevant_context']
#     return state
   


# def run_qualtative_answer_workflow(state):
#     """
#     Run the qualitative answer workflow.
#     Args:
#         state: The current state of the plan execution.
#     Returns:
#         The state with the updated aggregated context.
#     """
#     state["curr_state"] = "answer"
#     print("Running the qualitative answer workflow...")
#     question = state["query_to_retrieve_or_answer"]
#     context = state["curr_context"]
#     inputs = {"question": question, "context": context}
#     for output in qualitative_answer_workflow_app.stream(inputs):
#         for _, _ in output.items():
#             pass 
#         print("--------------------")
#     if not state["aggregated_context"]:
#         state["aggregated_context"] = ""
#     state["aggregated_context"] += output["answer"]
#     return state

def run_qualtative_answer_workflow_for_final_answer(state):
    """
    Run the qualitative answer workflow for the final answer.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated response.
    """
    state["curr_state"] = "get_final_answer"
    print("Running the qualitative answer workflow for final answer...")
    question = state["question"]
    #context = state["aggregated_context"]
    inputs = {"question": question, "context": "TODO Hier wird Vectordb retrieved"}
    # for output in qualitative_answer_workflow_app.stream(inputs):
    #     for _, value in output.items():
    #         pass  
    #     print("--------------------")
    state["response"] = "Test  run_qualtative_answer_workflow_for_final_answer...."#value
    return state
