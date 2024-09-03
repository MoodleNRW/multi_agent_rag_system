from typing import List, TypedDict, Annotated
#from langgraph.graph.message import add_messages

# Define the state object for the agent graph
class AgentGraphState(TypedDict):
    curr_state: str
    question: str
    anonymized_question: str
    query_to_retrieve_or_answer: str
    plan: List[str]
    past_steps: List[str]
    mapping: dict 
    curr_context: str
    aggregated_context: str
    tool: str
    response: str

# Define the nodes in the agent graph
# def get_agent_graph_state(state: AgentGraphState, state_key: str):
#     key_mapping = {
#         "project_manager": "project_manager_response",
#     }

#     if state_key.endswith("_all"):
#         base_key = state_key.split("_")[0]
#         return state.get(key_mapping.get(base_key))

#     if state_key.endswith("_latest"):
#         base_key = state_key.split("_")[0]
#         response = state.get(key_mapping.get(base_key))
#         if response:
#             return response[-1]
#         else:
#             return response

#     return None

# state = {
#     "user_question":"",
#     "project_manager_response": [],
#     "router_response": [],
#     "final_reports": [],
#     "end_chain": []
# }