import chainlit as cl
from .state import PlanExecute
import weaviate
from langchain_community.vectorstores import Weaviate
import weaviate.classes as wvc
from datetime import datetime
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI 
from langchain_core.pydantic_v1 import BaseModel, Field
import dotenv
import os
dotenv.load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')

class KeepRelevantContent(BaseModel):
        relevant_content: str = Field(description="The relevant content from the retrieved documents that is relevant to the query.")

keep_only_relevant_content_prompt_template = """you receive a query: {query} and retrieved documents: {retrieved_documents} from a
        vector store.
        You need to filter out all the non relevant information that don't supply important information regarding the {query}. Keep Urls.
        your goal is just to filter out the non relevant information.
        you can remove parts of sentences that are not relevant to the query or remove whole sentences that are not relevant to the query.
        DO NOT ADD ANY NEW INFORMATION THAT IS NOT IN THE RETRIEVED DOCUMENTS.
        output the filtered relevant content.
        Keep URLs and references to the original sources in the answer if they are relevant.
        """

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

    response = weaviate_client.query.get("Content_chunk",["url","content_chunk"]).with_near_text({"concepts": [query]}).with_limit(4).with_additional(["distance"]).do()
    docs = response['data']['Get']['Content_chunk']
    
    # Filter out empty content
    retrieved_info = " ".join(f"{doc['url']}: {doc['content_chunk']}" for doc in docs if doc.get('content_chunk') and doc['content_chunk'].strip())

    
    
    keep_only_relevant_content_prompt = PromptTemplate(
    template=keep_only_relevant_content_prompt_template,
    input_variables=["query", "retrieved_documents"],
)
    
    keep_only_relevant_content_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    keep_only_relevant_content_chain = keep_only_relevant_content_prompt | keep_only_relevant_content_llm.with_structured_output(KeepRelevantContent)

    input_data = {
        "query": state["question"],
        "retrieved_documents": retrieved_info
    }

    output = keep_only_relevant_content_chain.invoke(input_data)
    relevant_content = output.relevant_content
    relevant_content = "".join(relevant_content)
    print("RRR",relevant_content)

    state["curr_context"] += f"Retrieved chunk information: {relevant_content}"
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

    response = weaviate_client.query.get("Content_summary",["url","content_summary"]).with_near_text({"concepts": [query]}).with_limit(4).with_additional(["distance"]).do()
    docs = response['data']['Get']['Content_summary']
    
    # Filter out empty content
    retrieved_info = " ".join(f"{doc['url']}: {doc['content_summary']}" for doc in docs if doc.get('content_summary') and doc['content_summary'].strip())
    
    keep_only_relevant_content_prompt = PromptTemplate(
    template=keep_only_relevant_content_prompt_template,
    input_variables=["query", "retrieved_documents"],
)
    
    keep_only_relevant_content_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    keep_only_relevant_content_chain = keep_only_relevant_content_prompt | keep_only_relevant_content_llm.with_structured_output(KeepRelevantContent)

    input_data = {
        "query": state["question"],
        "retrieved_documents": retrieved_info
    }

    output = keep_only_relevant_content_chain.invoke(input_data)
    relevant_content = output.relevant_content
    relevant_content = "".join(relevant_content)
    print("RRRR",relevant_content)

    state["curr_context"] += f"Retrieved chunk information: {relevant_content}"
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

    response = weaviate_client.query.get("Content_chunk",["url","content_chunk"]).with_near_text({"concepts": [query]}).with_limit(4).with_additional(["distance"]).do()
    docs = response['data']['Get']['Content_chunk']
    
    # Filter out empty content
    retrieved_info = " ".join(f"{doc['url']}: {doc['content_chunk']}" for doc in docs if doc.get('content') and doc['content'].strip())
    
    keep_only_relevant_content_prompt = PromptTemplate(
    template=keep_only_relevant_content_prompt_template,
    input_variables=["query", "retrieved_documents"],
)
    
    keep_only_relevant_content_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    keep_only_relevant_content_chain = keep_only_relevant_content_prompt | keep_only_relevant_content_llm.with_structured_output(KeepRelevantContent)

    input_data = {
        "query": state["question"],
        "retrieved_documents": retrieved_info
    }

    output = keep_only_relevant_content_chain.invoke(input_data)
    relevant_content = output.relevant_content
    relevant_content = "".join(relevant_content)

    state["curr_context"] += f"Retrieved chunk information: {relevant_content}"
    state["aggregated_context"] += state["curr_context"]

    return state