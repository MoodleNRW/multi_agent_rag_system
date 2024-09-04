# config/config_manager.py

import os
from dotenv import load_dotenv, set_key
import chainlit as cl
from chainlit.input_widget import InputWidget, TextInput, Slider, Select
from typing import List, Dict, Any

class ConfigManager:
    def __init__(self):
        load_dotenv()
        self.settings: List[InputWidget] = []
        self.env_path = os.path.join(os.path.dirname(__file__), "..", ".env")

    @staticmethod
    def update_env_file(env_path: str, key: str, value: Any):
        if value is not None:
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
        # self.settings.append(TextInput(
        #     id="OPENAI_API_KEY",
        #     label="OpenAI API Key",
        #     initial=api_key,
        #     placeholder="Enter your OpenAI API Key here"
        # ))

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

        return self.settings

    async def update_settings(self, new_settings: Dict[str, Any]):
        current_settings = cl.user_session.get("settings", {})
        current_settings.update(new_settings)
        cl.user_session.set("settings", current_settings)

        for key, value in new_settings.items():
            self.update_env_file(self.env_path, key.upper(), value)

        load_dotenv(self.env_path, override=True)

        await self.load_settings()

        chat_settings = cl.ChatSettings(self.settings)
        await chat_settings.send()

    def get_setting_value(self, key: str) -> Any:
        env_value = self.get_env_value(key)
        if env_value:
            return env_value
        
        current_settings = cl.user_session.get("settings", {})
        return current_settings.get(key)