from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
load_dotenv()

#todo get prepared models based on settings.. 
def get_open_ai(temperature=0, model='gpt-4o', url="", response_format=None):
    kwargs = {
        'model': model,
        'temperature': temperature,
    }
    if url:
        kwargs['url'] = url
    if response_format:
        kwargs['model_kwargs'] = {"response_format": response_format}

    llm = ChatOpenAI(**kwargs)
    return llm

def get_open_ai_json(temperature=0, model='gpt-4o', url=""):
    return get_open_ai(
        temperature=temperature,
        model=model,
        url=url,
        response_format={"type": "json_object"}
    )
