# agent/retriever.py

import chainlit as cl
from .state import PlanExecute

@cl.step(name="Retrieve Chunks", type="tool")
async def run_qualitative_chunks_retrieval_workflow(state: PlanExecute):
    # Here you would typically use your vector store to retrieve relevant chunks
    # For this example, we'll simulate the retrieval
    query = state["query_to_retrieve_or_answer"]
    chunks_retriever = cl.user_session.get("retrievers")["chunks"]
    #todo
    # docs = chunks_retriever.get_relevant_documents(query)
    
    # retrieved_info = " ".join(doc.page_content for doc in docs)
    state["curr_context"] += f"Retrieved chunk information: Moodle ist super." #todo {retrieved_info} 
    state["aggregated_context"] += state["curr_context"]

    return state

@cl.step(name="Retrieve Summaries", type="tool")
async def run_qualitative_summaries_retrieval_workflow(state: PlanExecute):
    query = state["query_to_retrieve_or_answer"]
    summaries_retriever = cl.user_session.get("retrievers")["summaries"]
    # docs = summaries_retriever.get_relevant_documents(query)
    
    # retrieved_info = " ".join(f"{doc.page_content} (Chapter {doc.metadata['chapter']})" for doc in docs)
    state["curr_context"] += f"Retrieved summary information: Moodle ist super!! " #{retrieved_info}
    state["aggregated_context"] += state["curr_context"]

    return state

@cl.step(name="Retrieve Quotes", type="tool")
async def run_qualitative_quotes_retrieval_workflow(state: PlanExecute):
    query = state["query_to_retrieve_or_answer"]
    quotes_retriever = cl.user_session.get("retrievers")["quotes"]
    # docs = quotes_retriever.get_relevant_documents(query)
    
    # retrieved_info = " ".join(doc.page_content for doc in docs)
    state["curr_context"] += f"Retrieved quote information: Moodle ist super!"#{retrieved_info} 
    state["aggregated_context"] += state["curr_context"]

    return state