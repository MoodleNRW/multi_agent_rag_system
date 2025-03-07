"""
Ollama-Modellimplementierung für das Multi-Agent-RAG-System.
"""

import os
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# Versuche, die Ollama-Modelle zu importieren
try:
    from langchain_ollama import ChatOllama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

def get_ollama(temperature=0, model='llama3.2:3b', response_format=None):
    """
    Gibt eine Ollama-LLM-Instanz zurück.
    
    Args:
        temperature: Die Temperatur für die Generierung (0 = deterministisch, 1 = kreativ)
        model: Der Name des Modells
        response_format: Das Format der Antwort
        
    Returns:
        Eine Ollama-LLM-Instanz
    """
    if not OLLAMA_AVAILABLE:
        raise ImportError("Ollama-Modelle sind nicht verfügbar. Bitte installieren Sie langchain-ollama.")
    
    kwargs = {
        'model': model,
        'temperature': temperature,
        'max_tokens': 4000
    }
    
    if response_format:
        kwargs['model_kwargs'] = {"response_format": response_format}
    
    llm = ChatOllama(**kwargs)
    return llm

def get_ollama_json(temperature=0, model='llama3.2:3b'):
    """
    Gibt eine Ollama-LLM-Instanz zurück, die JSON-Ausgabe unterstützt.
    
    Args:
        temperature: Die Temperatur für die Generierung (0 = deterministisch, 1 = kreativ)
        model: Der Name des Modells
        
    Returns:
        Eine Ollama-LLM-Instanz mit JSON-Ausgabe
    """
    return get_ollama(
        temperature=temperature,
        model=model,
        response_format={"type": "json_object"}
    ) 