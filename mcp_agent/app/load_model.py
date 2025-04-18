from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_community.callbacks import get_openai_callback
from langchain_anthropic import ChatAnthropic

import os
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()


# Initialize default Gemini model
model = ChatGoogleGenerativeAI(
    model="gemini-pro",
    temperature=0,
    max_tokens=None,
    timeout=60,
    max_retries=2,
    api_key=os.getenv('GOOGLE_API_KEY')
)

def load_model(model_name, tools=None, prompt=None, parser=None):
    """Load the model dynamically based on the parameter."""
    # Initialize the model based on the model_name
    if 'gemini' in model_name:
        model = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            max_tokens=None,  # Limit output tokens
            timeout=60,
            max_retries=2,
            api_key=os.getenv('GOOGLE_API_KEY')
            )
    elif 'claude' in model_name:
        model = ChatAnthropic(
            model=model_name,
            temperature=0,
            max_tokens_to_sample=8192,
            streaming=True,
            anthropic_api_key=os.getenv('ANTHROPIC_API_KEY')
        )
    else:
        model = ChatOpenAI(
            model=model_name,
            temperature=0,
            max_tokens=None,  # Limit output tokens
            streaming=True,
            api_key=os.getenv('OPENAI_API_KEY')
            )

    # Bind tools if provided
    if tools:
        model = model.bind_tools(tools)

    if prompt:
        # Return a simple Prompt → Model chain, no structured-output
        return prompt | model

    # Configure structured output if parser is provided
    if parser:
        from langchain_core.output_parsers import PydanticOutputParser
        output_parser = PydanticOutputParser(pydantic_object=parser)
        return model.with_structured_output(parser)

    # Default chain without parser
    return model
