import chainlit as cl
from langsmith import traceable
from .state import PlanExecute
import weaviate
from weaviate.connect import ConnectionParams
import weaviate.classes as wvc
from datetime import datetime
import dotenv
import os
import logging
import asyncio
from vector_stores.retriever import ensure_global_client, ensure_global_retrievers
from ui.faq_ui import search_faq_database, show_save_to_faq_option
from pydantic import BaseModel, Field
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableParallel

dotenv.load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@traceable(pass_config=False)
@cl.step(name="Check FAQ", type="retrieval")
async def run_faq_check_workflow(state: PlanExecute):
    """
    Überprüft zuerst die FAQ-Datenbank auf eine passende Antwort.
    
    Args:
        state: Der aktuelle Zustand der Plan-Ausführung.
    Returns:
        Der aktualisierte Zustand mit der FAQ-Antwort, falls gefunden.
    """
    state["curr_state"] = "check_faq"
    query = state["query_to_retrieve_or_answer"]
    
    logger.info(f"Überprüfe FAQ-Datenbank für Anfrage: {query}")
    await cl.Message(content="🔍 Überprüfe FAQ-Datenbank...").send()
    
    faq_retriever = ensure_global_retrievers().get("faq")
    if not faq_retriever:
        await cl.Message(content="FAQ retriever not available. Proceeding with other methods.").send()
        state["direct_to_answer"] = False
        state["raw_context"] = ""
        state["routing"] = "back_to_task_handler"
        return state

    faq_docs = faq_retriever.get_relevant_documents(query)

    if faq_docs:
        faq_answer = faq_docs[0].page_content
        await cl.Message(content=f"FAQ Answer Found: {faq_answer}").send()
        # Add FAQ answer to the aggregated filtered context directly
        if "aggregated_filtered_context" not in state or state["aggregated_filtered_context"] is None:
            state["aggregated_filtered_context"] = ""
        state["aggregated_filtered_context"] += f"\n\nFAQ Answer: {faq_answer}"
        state["direct_to_answer"] = True
        state["response"] = {"answer": faq_answer} # Set response directly for FAQ
        state["raw_context"] = "" # No raw context to filter
        state["routing"] = "direct_to_answer"
    else:
        await cl.Message(content="No matching FAQ found. Proceeding with other methods.").send()
        state["direct_to_answer"] = False
        state["raw_context"] = ""
        state["routing"] = "back_to_task_handler"

    return state

@traceable(pass_config=False)
@cl.step(name="Retrieve Chunks", type="retrieval")
async def run_qualitative_chunks_retrieval_workflow(state: PlanExecute):
    """
    Retrieves relevant context from book chunks.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated raw context.
    """
    state["curr_state"] = "retrieve_chunks"
    question = state["query_to_retrieve_or_answer"]
    await cl.Message(content=f"Retrieving chunks for query: '{question}'").send()

    chunks_retriever = ensure_global_retrievers().get("chunks")
    if not chunks_retriever:
        await cl.Message(content="Error: Chunk retriever not available.").send()
        state["raw_context"] = ""
        return state

    docs = chunks_retriever.get_relevant_documents(question)
    raw_retrieved_content = " ".join(doc.page_content for doc in docs)

    state["raw_context"] = raw_retrieved_content
    # Removed direct update to aggregated_context
    return state

@traceable(pass_config=False)
@cl.step(name="Retrieve Summaries", type="retrieval")
async def run_qualitative_summaries_retrieval_workflow(state: PlanExecute):
    """
    Retrieves relevant context from chapter summaries.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated raw context.
    """
    state["curr_state"] = "retrieve_summaries"
    question = state["query_to_retrieve_or_answer"]
    await cl.Message(content=f"Retrieving summaries for query: '{question}'").send()

    summaries_retriever = ensure_global_retrievers().get("summaries")
    if not summaries_retriever:
        await cl.Message(content="Error: Summary retriever not available.").send()
        state["raw_context"] = ""
        return state

    docs_summaries = summaries_retriever.get_relevant_documents(question)
    raw_retrieved_content = " ".join(
        f"{doc.page_content} (Source: Summary {doc.metadata.get('summary_id', '')})" for doc in docs_summaries
    )
    state["raw_context"] = raw_retrieved_content
    # Removed direct update to aggregated_context
    return state

@traceable(pass_config=False)
@cl.step(name="Retrieve Quotes", type="retrieval")
async def run_qualitative_quotes_retrieval_workflow(state: PlanExecute):
    """
    Retrieves relevant context from book quotes.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated raw context.
    """
    state["curr_state"] = "retrieve_quotes"
    question = state["query_to_retrieve_or_answer"]
    await cl.Message(content=f"Retrieving quotes for query: '{question}'").send()

    quotes_retriever = ensure_global_retrievers().get("quotes")
    if not quotes_retriever:
        await cl.Message(content="Error: Quotes retriever not available.").send()
        state["raw_context"] = ""
        return state

    docs_book_quotes = quotes_retriever.get_relevant_documents(question)
    raw_retrieved_content = " ".join(doc.page_content for doc in docs_book_quotes)

    state["raw_context"] = raw_retrieved_content
    # Removed direct update to aggregated_context
    return state

@traceable(pass_config=False)
@cl.step(name="Parallel Retrieval", type="retrieval")
async def run_parallel_retrieval_workflow(state: PlanExecute):
    """
    Retrieves relevant context from chunks, summaries, and quotes in parallel (conceptually).
    
    Args:
        state: Der aktuelle Zustand der Plan-Ausführung.
    Returns:
        Der aktualisierte Zustand mit den kombinierten Retrieval-Ergebnissen.
    """
    state["curr_state"] = "parallel_retrieval"
    question = state["query_to_retrieve_or_answer"]
    await cl.Message(content=f"Performing parallel retrieval for query: '{question}'").send()

    retrievers = ensure_global_retrievers()
    chunks_retriever = retrievers.get("chunks")
    summaries_retriever = retrievers.get("summaries")
    quotes_retriever = retrievers.get("quotes")

    all_raw_context = []

    if chunks_retriever:
        chunk_docs = chunks_retriever.get_relevant_documents(question)
        all_raw_context.append(" ".join(doc.page_content for doc in chunk_docs))

    if summaries_retriever:
        summary_docs = summaries_retriever.get_relevant_documents(question)
        all_raw_context.append(" ".join(f"{doc.page_content} (Source: Summary {doc.metadata.get('summary_id', '')})" for doc in summary_docs))

    if quotes_retriever:
        quote_docs = quotes_retriever.get_relevant_documents(question)
        all_raw_context.append(" ".join(doc.page_content for doc in quote_docs))

    state["raw_context"] = "\n\n".join(filter(None, all_raw_context))
    # Removed direct update to aggregated_context
    return state

async def check_content_grounding(distilled_content, original_context):
    """
    Überprüft, ob der gefilterte Inhalt im ursprünglichen Kontext verankert ist.
    
    Args:
        distilled_content: Der gefilterte Inhalt.
        original_context: Der ursprüngliche Kontext.
    
    Returns:
        Boolean: True, wenn der Inhalt verankert ist, sonst False.
    """
    # Falls der Inhalt leer ist, ist er per Definition verankert
    if not distilled_content.strip():
        return True
    
    class IsGrounded(BaseModel):
        grounded: bool = Field(description="Gibt an, ob der gefilterte Inhalt im ursprünglichen Kontext verankert ist.")
        explanation: str = Field(description="Erläuterung, warum der Inhalt verankert ist oder nicht.")
    
    prompt_template = """Du erhältst gefilterten Inhalt: {distilled_content} und den ursprünglichen Kontext: {original_context}.
    Prüfe, ob der gefilterte Inhalt tatsächlich im ursprünglichen Kontext verankert ist.
    Der gefilterte Inhalt sollte keine Informationen enthalten, die nicht zumindest sinngemäß im ursprünglichen Kontext vorhanden sind.
    
    Setze 'grounded' auf true, wenn der Inhalt vollständig im Kontext verankert ist.
    Setze 'grounded' auf false, wenn der Inhalt Informationen enthält, die nicht im Kontext enthalten sind.
    """
    
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["distilled_content", "original_context"],
    )
    
    from models.models_wrapper import get_llm
    llm = get_llm(temperature=0)
    chain = prompt | llm.with_structured_output(
        IsGrounded, 
        method="function_calling",
        strict=True
    )
    
    input_data = {
        "distilled_content": distilled_content,
        "original_context": original_context
    }
    
    result = chain.invoke(input_data)
    return result.grounded