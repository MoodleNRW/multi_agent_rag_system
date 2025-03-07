import os
import logging
from dotenv import load_dotenv
from models.openai_models import get_open_ai, get_open_ai_json
from typing import Optional

# Versuche, die Groq-Modelle zu importieren
try:
    from models.groq_models import get_groq, get_groq_json
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logging.warning("Groq-Modelle sind nicht verfügbar. Bitte installieren Sie langchain-groq.")

# Versuche, die Ollama-Modelle zu importieren
try:
    from models.ollama_models import get_ollama, get_ollama_json
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.warning("Ollama-Modelle sind nicht verfügbar. Bitte installieren Sie langchain-ollama.")

# Versuche, die Claude-Modelle zu importieren
try:
    from models.claude_models import get_claude, get_claude_json
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    logging.warning("Claude-Modelle sind nicht verfügbar. Bitte installieren Sie langchain-anthropic.")

# Lade Umgebungsvariablen
load_dotenv()

def get_llm(temperature: float = 0, model_provider: Optional[str] = None, model_name: Optional[str] = None, json_model: bool = False):
    """
    Gibt eine LLM-Instanz basierend auf den angegebenen Parametern zurück.
    
    Args:
        temperature: Die Temperatur für die Generierung (0 = deterministisch, 1 = kreativ)
        model_provider: Der Anbieter des Modells (openai, groq, ollama, claude)
        model_name: Der Name des Modells
        json_model: Ob das Modell JSON-Ausgabe unterstützen soll
        
    Returns:
        Eine LLM-Instanz
    """
    # Wenn kein Anbieter angegeben ist, verwende die Umgebungsvariable oder den Standardwert
    if model_provider is None:
        model_provider = os.getenv('MODEL_PROVIDER', 'openai').lower()
    
    # Wenn kein Modellname angegeben ist, verwende die Umgebungsvariable oder den Standardwert
    if model_name is None:
        if model_provider == 'openai':
            model_name = os.getenv('OPENAI_MODEL_NAME', 'gpt-4o')
        elif model_provider == 'groq':
            model_name = os.getenv('GROQ_MODEL_NAME', 'llama3-70b-8192')
        elif model_provider == 'ollama':
            model_name = os.getenv('OLLAMA_MODEL_NAME', 'llama3.2:3b')
        elif model_provider == 'claude':
            model_name = os.getenv('CLAUDE_MODEL_NAME', 'claude-3-opus-20240229')
    
    # URL für benutzerdefinierte Endpunkte
    url = os.getenv(f'{model_provider.upper()}_API_URL', "")
    # Wähle den entsprechenden Modellanbieter
    if model_provider == 'openai':
        return get_open_ai_json(model=model_name, url=url, temperature=temperature) if json_model else get_open_ai(model=model_name, url=url, temperature=temperature)
    elif model_provider == 'groq' and GROQ_AVAILABLE:
        return get_groq_json(model=model_name, temperature=temperature) if json_model else get_groq(model=model_name, temperature=temperature)
    elif model_provider == 'ollama' and OLLAMA_AVAILABLE:
        return get_ollama_json(model=model_name, temperature=temperature) if json_model else get_ollama(model=model_name, temperature=temperature)
    elif model_provider == 'claude' and CLAUDE_AVAILABLE:
        return get_claude_json(model=model_name, temperature=temperature) if json_model else get_claude(model=model_name, temperature=temperature)
    else:
        # Fallback auf OpenAI, wenn der angegebene Anbieter nicht verfügbar ist
        if model_name == 'ollama':
            return get_ollama_json(model=model_name, temperature=temperature) if json_model else get_ollama(model=model_name, temperature=temperature)
        else:
            logging.warning(f"Modellanbieter {model_provider} ist nicht verfügbar. Verwende OpenAI als Fallback.")
            return get_open_ai_json(model=os.getenv('OPENAI_MODEL_NAME', 'gpt-4o'), temperature=temperature) if json_model else get_open_ai(model=os.getenv('OPENAI_MODEL_NAME', 'gpt-4o'), temperature=temperature)
        # if self.selected_model_name == 'groq':
        #     return GroqJSONModel(
        #         model=self.model,
        #         temperature=self.temperature
        #     ) if json_model else GroqModel(
        #         model=self.model,
        #         temperature=self.temperature
        #     )
        # if self.selected_model_name == 'claude':
        #     return ClaudJSONModel(
        #         model=self.model,
        #         temperature=self.temperature
        #     ) if json_model else ClaudModel(
        #         model=self.model,
        #         temperature=self.temperature
        #     )   