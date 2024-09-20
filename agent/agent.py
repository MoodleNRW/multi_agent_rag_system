from models.openai_models import get_open_ai, get_open_ai_json
# from models.ollama_models import OllamaModel, OllamaJSONModel
# from models.groq_models import GroqModel, GroqJSONModel
# from models.claude_models import ClaudModel, ClaudJSONModel

from agents.state import AgentGraphState

class Agent:
    def __init__(self, state: AgentGraphState, model=None, selected_model_name=None, temperature=0, stop=None,):
        self.state = state
        self.model = model
        self.selected_model_name = selected_model_name
        self.temperature = temperature
        self.stop = stop

    def get_llm(self, json_model=True):
        if self.selected_model_name == 'openai':
            return get_open_ai_json(model=self.model, temperature=self.temperature) if json_model else get_open_ai(model=self.model, temperature=self.temperature)
        # if self.selected_model_name == 'ollama':
        #     return OllamaJSONModel(model=self.model, temperature=self.temperature) if json_model else OllamaModel(model=self.model, temperature=self.temperature)
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

    def update_state(self, key, value):
        self.state = {**self.state, key: value}