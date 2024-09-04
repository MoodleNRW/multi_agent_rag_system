import chainlit as cl
from .state import PlanExecute
import weaviate
from langchain_community.vectorstores import Weaviate
import weaviate.classes as wvc
from datetime import datetime
import dotenv
import os
dotenv.load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')

@cl.step(name="Retrieve Chunks", type="tool")
async def run_qualitative_chunks_retrieval_workflow(state: PlanExecute):
    """
    Run the qualitative chunks retrieval workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    state["curr_state"] = "retrieve_chunks"

    query = state["query_to_retrieve_or_answer"]
    
    # Initialize the Weaviate client
    weaviate_client = weaviate.Client("http://localhost:8090", additional_headers = {
        "X-OpenAI-Api-Key": API_KEY
    })

    response = weaviate_client.query.get("Content_chunks",["url","content"]).with_near_text({"concepts": [query]}).with_limit(4).with_additional(["distance"]).do()
    docs = response['data']['Get']['Content_chunks']
    
    # Filter out empty content
    retrieved_info = " ".join(f"{doc['url']}: {doc['content_chunk']}" for doc in docs if doc.get('content_chunk') and doc['content_chunk'].strip())
    
    state["curr_context"] += f"Retrieved chunk information: {retrieved_info}"
    state["aggregated_context"] += state["curr_context"]

    return state

@cl.step(name="Retrieve Summaries", type="tool")
async def run_qualitative_summaries_retrieval_workflow(state: PlanExecute):
    """
    Run the qualitative summaries retrieval workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    state["curr_state"] = "retrieve_summaries"
    
    query = state["query_to_retrieve_or_answer"]
    
    # Initialize the Weaviate client
    weaviate_client = weaviate.Client("http://localhost:8090", additional_headers = {
        "X-OpenAI-Api-Key": API_KEY
    })

    response = weaviate_client.query.get("Content_summary",["url","content"]).with_near_text({"concepts": [query]}).with_limit(4).with_additional(["distance"]).do()
    docs = response['data']['Get']['Content_summary']
    
    # Filter out empty content
    retrieved_info = " ".join(f"{doc['url']}: {doc['content_summary']}" for doc in docs if doc.get('content_summary') and doc['content_summary'].strip())
    
    state["curr_context"] += f"Retrieved chunk information: {retrieved_info}"
    state["aggregated_context"] += state["curr_context"]

    return state
@cl.step(name="Retrieve Quotes", type="tool")
async def run_qualitative_quotes_retrieval_workflow(state: PlanExecute):
    """
    Run the qualitative quotes retrieval workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    state["curr_state"] = "retrieve_quotes"

    query = state["query_to_retrieve_or_answer"]
    
    # Initialize the Weaviate client
    weaviate_client = weaviate.Client("http://localhost:8090", additional_headers = {
        "X-OpenAI-Api-Key": API_KEY
    })

    response = weaviate_client.query.get("Content",["url","content"]).with_near_text({"concepts": [query]}).with_limit(4).with_additional(["distance"]).do()
    docs = response['data']['Get']['Content']
    
    # Filter out empty content
    retrieved_info = " ".join(f"{doc['url']}: {doc['content']}" for doc in docs if doc.get('content') and doc['content'].strip())
    
    state["curr_context"] += f"Retrieved chunk information: {retrieved_info}"
    state["aggregated_context"] += state["curr_context"]

    return state