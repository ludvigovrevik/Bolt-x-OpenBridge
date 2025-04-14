from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_community.callbacks import get_openai_callback
import os
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

def load_model(model_name, tools=None, prompt=None, parser=False):
    """Load the model dynamically based on the parameter."""
    # Initialize the model based on the model_name
    if 'gemini' in model_name:
        model = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            max_tokens=1000,  # Limit output tokens
            timeout=60,
            max_retries=2)
    else:
        model = ChatOpenAI(
            model=model_name,
            temperature=0,
            max_tokens=None,  # Limit output tokens
            streaming=True)

    # Bind tools if provided
    if tools:
        model = model.bind_tools(tools)

    if prompt:
        chain = prompt | model
        return chain

    # Create a chain based on the parser parameter
    if parser:
        chain = prompt | model | parser
        return chain

    # Default chain without parser
    return model