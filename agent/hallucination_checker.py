import chainlit as cl
from langchain_core.pydantic_v1 import BaseModel, Field
from models.models_wrapper import get_llm
from langchain.prompts import PromptTemplate
from .state import PlanExecute
import logging

logger = logging.getLogger(__name__)

class IsGroundedOnFacts(BaseModel):
    """
    Output-Schema für die Überprüfung, ob eine Antwort auf Fakten basiert.
    """
    grounded_on_facts: bool = Field(description="Antwort ist in den Fakten begründet, 'ja' oder 'nein'")
    explanation: str = Field(description="Erklärung, warum die Antwort in den Fakten begründet ist oder nicht")

@cl.step(name="Halluzinationsprüfung", type="process")
async def is_answer_grounded_on_context(state: PlanExecute):
    """
    Bestimmt, ob die Antwort auf die Frage in den Fakten begründet ist.
    
    Args:
        state: Ein Dictionary mit dem Kontext und der Antwort.
    """
    state["curr_state"] = "hallucination_check"
    logger.info("=== HALLUZINATIONSPRÜFUNG WIRD AUFGERUFEN ===")
    
    is_grounded_on_facts_prompt_template = """Du bist ein Faktenprüfer, der feststellt, ob die gegebene Antwort {answer} im gegebenen Kontext {context} begründet ist.
    Es ist nicht wichtig, ob die Antwort sinnvoll ist, solange sie im Kontext begründet ist.
    
    Analysiere sorgfältig, ob alle Behauptungen in der Antwort durch Informationen im Kontext unterstützt werden.
    
    Wenn die Antwort Informationen enthält, die nicht im Kontext zu finden sind, handelt es sich um eine Halluzination.
    Wenn die Antwort nur Informationen enthält, die im Kontext zu finden sind, ist sie in den Fakten begründet.
    
    Gib deine Analyse in einem strukturierten Format zurück:
    - grounded_on_facts: Ein boolescher Wert (true/false), der angibt, ob die Antwort vollständig im Kontext begründet ist
    - explanation: Eine detaillierte Erklärung deiner Analyse
    """
    
    is_grounded_on_facts_prompt = PromptTemplate(
        template=is_grounded_on_facts_prompt_template,
        input_variables=["context", "answer"],
    )
    
    is_grounded_on_facts_llm = get_llm(temperature=0)
    is_grounded_on_facts_chain = is_grounded_on_facts_prompt | is_grounded_on_facts_llm.with_structured_output(IsGroundedOnFacts, strict=True)
    
    context = state["context"] if "context" in state else state["aggregated_context"]
    answer = state["response"]
    
    result = is_grounded_on_facts_chain.invoke({"context": context, "answer": answer})
    grounded_on_facts = result.grounded_on_facts
    
    # Log the decision for debugging
    cl.Task(title="Halluzinationsprüfung", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Ergebnis: {'Faktenbasiert' if grounded_on_facts else 'Halluzination'}", status=cl.TaskStatus.DONE)
    cl.Task(title=f"Erklärung: {result.explanation}", status=cl.TaskStatus.DONE)
    
    if not grounded_on_facts:
        return "hallucination"
    else:
        return "grounded_on_context" 