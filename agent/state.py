from typing import List, Dict, TypedDict, Optional

class PlanExecute(TypedDict):
    curr_state: Optional[str]
    question: str  # Initial question should likely not be optional
    anonymized_question: Optional[str]
    query_to_retrieve_or_answer: Optional[str]
    plan: Optional[List[str]]
    past_steps: Optional[List[str]]
    past_tool_usage: List[str]  # Liste der bisher verwendeten Tools
    mapping: Optional[Dict[str, str]]
    curr_context: Optional[str] # Context for the current 'answer' step if used directly
    aggregated_context: Optional[str] # Remove or comment out old aggregation field
    tool: Optional[str]
    response: Optional[Dict] # Final response structure
    routing: Optional[str]  # Routing-Information für bedingte Kanten im Workflow
    direct_to_answer: Optional[bool]  # Flag für direkte Weiterleitung zur Antwort
    relevance_status: Optional[str] # Status from keep_only_relevant_content step ('found_relevant_content', 'no_relevant_content_found', 'no_context_to_filter')
    error: str  # Fehlerinformationen
    raw_context: Optional[str]  # Context from the last retrieval step
    aggregated_filtered_context: Optional[str] # Aggregated filtered context over steps
    prev_tool: Optional[str]
    faq_check_count: Optional[int]