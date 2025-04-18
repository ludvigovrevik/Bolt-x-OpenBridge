from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage

def make_structured_prompt(schema, system_text: str):
    """
    Build a ChatPromptTemplate + PydanticOutputParser that works with both
    older and newer LangChain versions.
    """
    # Instantiating with a keyword argument for latest LangChain/Pydantic v2
    parser = PydanticOutputParser(pydantic_object=schema)

    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content=system_text + "\n\n" + parser.get_format_instructions()
            )
        ]
    )
    
    # Gemini format converter (now separate from prompt)
    def format_to_gemini(prompt_text: str) -> dict:
        if not isinstance(prompt_text, str):
            raise ValueError(f"Expected string input, got {type(prompt_text)}")
        return {
            "contents": [{
                "role": "USER",
                "parts": [{"text": prompt_text}]
            }]
        }
    
    return prompt, (parser, format_to_gemini)
