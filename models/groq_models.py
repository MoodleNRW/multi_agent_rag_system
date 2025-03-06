"""
Groq-Modellimplementierung für das Multi-Agent-RAG-System.
"""

import os
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# Versuche, die Groq-Modelle zu importieren
try:
    from langchain_groq import ChatGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

def get_groq(temperature=0, model='llama3-70b-8192', response_format=None):
    """
    Gibt eine Groq-LLM-Instanz zurück.
    
    Args:
        temperature: Die Temperatur für die Generierung (0 = deterministisch, 1 = kreativ)
        model: Der Name des Modells
        response_format: Das Format der Antwort
        
    Returns:
        Eine Groq-LLM-Instanz
    """
    if not GROQ_AVAILABLE:
        raise ImportError("Groq-Modelle sind nicht verfügbar. Bitte installieren Sie langchain-groq.")
    
    groq_api_key = os.getenv('GROQ_API_KEY')
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY ist nicht gesetzt. Bitte setzen Sie die Umgebungsvariable.")
    
    kwargs = {
        'model_name': model,
        'temperature': temperature,
        'groq_api_key': groq_api_key,
        'max_tokens': 4000
    }
    
    if response_format:
        kwargs['model_kwargs'] = {"response_format": response_format}
    
    llm = ChatGroq(**kwargs)
    return llm

def get_groq_json(temperature=0, model='llama3-70b-8192'):
    """
    Gibt eine Groq-LLM-Instanz zurück, die JSON-Ausgabe unterstützt.
    
    Args:
        temperature: Die Temperatur für die Generierung (0 = deterministisch, 1 = kreativ)
        model: Der Name des Modells
        
    Returns:
        Eine Groq-LLM-Instanz mit JSON-Ausgabe
    """
    return get_groq(
        temperature=temperature,
        model=model,
        response_format={"type": "json_object"}
    ) 