import os
from dotenv import load_dotenv, set_key
import chainlit as cl
from chainlit.input_widget import InputWidget, TextInput, Slider, Select
import requests
import json
from typing import List, Dict, Any

class ConfigManager:
    def __init__(self, base_url: str):
        load_dotenv()
        self.base_url = base_url
        self.settings: List[InputWidget] = []
        self.env_path = os.path.join(os.path.dirname(__file__), ".env")

    @staticmethod
    def update_env_file(env_path: str, key: str, value: Any):
        if value is not None:
            # Konvertiere numerische Werte zu ihrem korrekten Typen
            if isinstance(value, (int, float)):
                set_key(env_path, key, str(value))
            else:
                set_key(env_path, key, value)

    @staticmethod
    def get_env_value(key: str) -> str:
        return os.getenv(key, "")
    async def load_settings(self) -> List[InputWidget]:
        current_settings = cl.user_session.get("settings", {})
        self.settings = []

        api_key = current_settings.get("OPENAI_API_KEY", self.get_env_value("OPENAI_API_KEY"))
        self.settings.append(TextInput(
            id="OPENAI_API_KEY",
            label="OPENAI API Key",
            initial=api_key,
            placeholder="Enter your OpenAi API Key here"
        ))

        temperature = float(current_settings.get("TEMPERATURE", 0.7))

        self.settings.append(Slider(
            id="TEMPERATURE",
            label="Temperature",
            initial=temperature,
            min=0,
            max=2,
            step=0.1
        ))

        max_tokens = int(current_settings.get("MAXTOKENS", 4000))

        self.settings.append(Slider(
            id="MAXTOKENS",
            label="Max Tokens",
            initial=max_tokens,
            min=50,
            max=4000,
            step=50
        ))

        # if api_key:
        #     models = await self.get_available_models(api_key)
        #     if models:
        #         current_model = current_settings.get("ACTIVEMODEL")
        #         if not current_model:
        #             current_model = models[0]  # Set default to the first model if none is selected
        #             current_settings["ACTIVEMODEL"] = current_model
        #             cl.user_session.set("settings", current_settings)

        #         initial_index = models.index(current_model) if current_model in models else 0
        #         self.settings.append(Select(
        #             id="ACTIVEMODEL",
        #             label="Open AI - Model",
        #             values=models,
        #             initial_index=initial_index
        #         ))
        return self.settings

    # async def get_available_models(self, api_key: str) -> List[str]:
    #     try:
    #         url = f"{self.base_url}/models"
    #         headers = {"Authorization": f"Bearer {api_key}"}
    #         response = requests.get(url, headers=headers)
            
    #         if response.status_code == 200:
    #             models = json.loads(response.text)
    #             return [model["id"] for model in models]
    #         else:
    #             await cl.Message(content=f"API Error: {response.status_code} - {response.text}").send()
    #             return []
    #     except Exception as e:
    #         await cl.Message(content=f"Exception occurred: {str(e)}").send()
    #         return []

    async def update_settings(self, new_settings: Dict[str, Any]):
        current_settings = cl.user_session.get("settings", {})
        current_settings.update(new_settings)
        cl.user_session.set("settings", current_settings)

        # Update env file
        for key, value in new_settings.items():
            self.update_env_file(self.env_path, key.upper(), value)

        # Reload environment variables
        load_dotenv(self.env_path, override=True)

        # Reload settings
        await self.load_settings()

        # Update chat settings
        chat_settings = cl.ChatSettings(self.settings)
        await chat_settings.send()

    def get_setting_value(self, key: str) -> Any:
        # First, try to get the value from the environment
        env_value = self.get_env_value(key)
        if env_value is not None:
            return env_value
        
        # If not found in environment, get from session settings
        current_settings = cl.user_session.get("settings", {})
        return current_settings.get(key)