from typing import List, TypedDict, Optional

class PlanExecute(TypedDict, total=False):
    curr_state: str
    question: str
    anonymized_question: str
    query_to_retrieve_or_answer: str
    plan: List[str]
    past_steps: List[str]
    past_tool_usage: List[str]  # Liste der bisher verwendeten Tools
    mapping: dict 
    curr_context: str
    aggregated_context: str
    tool: str
    response: str
    routing: str  # Routing-Information für bedingte Kanten im Workflow
    direct_to_answer: bool  # Flag für direkte Weiterleitung zur Antwort
    relevance_status: str  # Status der Relevanz des abgerufenen Inhalts
    error: str  # Fehlerinformationen