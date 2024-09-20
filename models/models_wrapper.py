from models.openai_models import get_open_ai, get_open_ai_json

def get_llm(temperature = 0):
        #todo from settings
        model_provider = "openai"
        model_name = "gpt-4o"
        url = ""
        json_model=False


        if model_provider == 'openai':
            return get_open_ai_json(model = model_name, url = url, temperature=temperature) if json_model else get_open_ai(model = model_name,url = url, temperature=temperature)
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