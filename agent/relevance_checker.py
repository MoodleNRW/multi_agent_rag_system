import chainlit as cl
from langchain_core.pydantic_v1 import BaseModel, Field
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from .state import PlanExecute

class Relevance(BaseModel):
    """
    Output-Schema für die Relevanzprüfung.
    """
    is_relevant: bool = Field(description="Ob das Dokument für die Anfrage relevant ist.")
    explanation: str = Field(description="Eine Erklärung, warum das Dokument relevant ist oder nicht.")

@cl.step(name="Relevanzprüfung", type="process")
async def is_relevant_content(state: PlanExecute):
    """
    Bestimmt, ob der abgerufene Inhalt für die Anfrage relevant ist.
    
    Args:
        state: Ein Dictionary mit der Anfrage und dem Kontext.
    """
    state["curr_state"] = "relevance_check"
    
    is_relevant_content_prompt_template = """Du erhältst eine Anfrage: {query} und einen Kontext: {context}, der aus einem Vektorspeicher abgerufen wurde. 
    Du musst bestimmen, ob der Kontext für die Anfrage relevant ist.
    
    Analysiere sorgfältig, ob der Kontext Informationen enthält, die zur Beantwortung der Anfrage beitragen können.
    
    Gib deine Analyse in einem strukturierten Format zurück:
    - is_relevant: Ein boolescher Wert (true/false), der angibt, ob der Kontext für die Anfrage relevant ist
    - explanation: Eine detaillierte Erklärung deiner Analyse
    """
    
    is_relevant_content_prompt = PromptTemplate(
        template=is_relevant_content_prompt_template,
        input_variables=["query", "context"],
    )
    
    is_relevant_content_llm = get_llm(temperature=0)
    is_relevant_content_chain = is_relevant_content_prompt | is_relevant_content_llm.with_structured_output(Relevance, strict=True)
    
    question = state["question"]
    context = state["context"] if "context" in state else state["aggregated_context"]
    
    result = is_relevant_content_chain.invoke({"query": question, "context": context})
    is_relevant = result.is_relevant
    
    # Log the decision for debugging
    cl.Task(title="Relevanzprüfung", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Ergebnis: {'Relevant' if is_relevant else 'Nicht relevant'}", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Erklärung: {result.explanation}", status=cl.TaskStatus.DONE)
    
    if is_relevant:
        return "relevant"
    else:
        return "not_relevant" 