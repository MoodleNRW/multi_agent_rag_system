from langgraph.graph import StateGraph, END
from agent.state import AgentGraphState
from agent.tools import anonymize_queries, run_qualtative_answer_workflow_for_final_answer

def create_graph():
    agent_workflow = StateGraph(AgentGraphState)

    # Add the anonymize node
    agent_workflow.add_node("anonymize_question", anonymize_queries)

    # Add the plan node
    agent_workflow.add_node("planner", plan_step)

    # Add the break down plan node

    agent_workflow.add_node("break_down_plan", break_down_plan_step)

    # Add the deanonymize node
    agent_workflow.add_node("de_anonymize_plan", deanonymize_queries)

    # Add the qualitative chunks retrieval node
    agent_workflow.add_node("retrieve_chunks", run_qualitative_chunks_retrieval_workflow)

    # Add the qualitative summaries retrieval node
    agent_workflow.add_node("retrieve_summaries", run_qualitative_summaries_retrieval_workflow)

    # Add the qualitative book quotes retrieval node
    agent_workflow.add_node("retrieve_book_quotes", run_qualitative_book_quotes_retrieval_workflow)

    # Add the qualitative answer node
    agent_workflow.add_node("answer", run_qualtative_answer_workflow)

    # Add the task handler node
    agent_workflow.add_node("task_handler", run_task_handler_chain)

    # Add a replan node
    agent_workflow.add_node("replan", replan_step)

    #Add answer from context node
    agent_workflow.add_node("get_final_answer", run_qualtative_answer_workflow_for_final_answer)

    # Set the entry point
    agent_workflow.set_entry_point("anonymize_question")

    # From anonymize we go to plan
    agent_workflow.add_edge("anonymize_question", "get_final_answer")

    # From plan we go to deanonymize
    agent_workflow.add_edge("planner", "de_anonymize_plan")

    # From deanonymize we go to break down plan

    agent_workflow.add_edge("de_anonymize_plan", "break_down_plan")

    # From break_down_plan we go to task handler
    agent_workflow.add_edge("break_down_plan", "task_handler")

    # From task handler we go to either retrieve or answer
    agent_workflow.add_conditional_edges("task_handler", retrieve_or_answer, {"chosen_tool_is_retrieve_chunks": "retrieve_chunks", "chosen_tool_is_retrieve_summaries":
                                                                            "retrieve_summaries", "chosen_tool_is_retrieve_quotes": "retrieve_book_quotes", "chosen_tool_is_answer": "answer"})

    # After retrieving we go to replan
    agent_workflow.add_edge("retrieve_chunks", "replan")

    agent_workflow.add_edge("retrieve_summaries", "replan")

    agent_workflow.add_edge("retrieve_book_quotes", "replan")

    # After answering we go to replan
    agent_workflow.add_edge("answer", "replan")

    # After replanning we check if the question can be answered, if yes we go to get_final_answer, if not we go to task_handler
    agent_workflow.add_conditional_edges("replan",can_be_answered, {"can_be_answered_already": "get_final_answer", "cannot_be_answered_yet": "break_down_plan"})

    # After getting the final answer we end
    agent_workflow.add_edge("get_final_answer", END)


    return agent_workflow


def compile_workflow():
    graph = create_graph()
    workflow = graph.compile()
    #display_graph(workflow)
    return workflow