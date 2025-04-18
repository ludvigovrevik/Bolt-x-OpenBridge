from typing import List
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers.pydantic import PydanticOutputParser
from ..utils import make_structured_prompt
from pathlib import Path
from typing import Union

# Helper to log pipeline values
def _log_step(name: str):
    return RunnableLambda(lambda x: (print(f"[planner] {name}: {x}"), x)[1])

class Page(BaseModel):
    slug: str
    title: str 
    description: str

class Spec(BaseModel):
    """
    Low-fidelity site specification.
    pages: List of pages, each defined by:
      - slug: string
      - title: string
      - description: string (free-text user description of the page)
    """
    pages: List[Page] = Field(
        ...,
        description="List of page definitions",
        examples=[[
            {"slug": "home", "title": "Home", "description": "Landing page"},
            {"slug": "about", "title": "About", "description": "Company info"}
        ]]
    )

parser = PydanticOutputParser(pydantic_object=Spec)
format_instructions = parser.get_format_instructions()

prompts_dir = Path(__file__).resolve().parent.parent / "prompts"

# Load modular prompt components
with open(prompts_dir / 'system_constraints.md') as f:
    system_constraints = f.read()
with open(prompts_dir / 'formatting_info.md') as f:
    formatting_rules = f.read()
with open(prompts_dir / 'reasoning_guidelines.md') as f:
    planning_guide = f.read()



system_prompt = f"""{system_constraints}

{formatting_rules}

{planning_guide}

{format_instructions}

If provided, you will receive an `image` variable containing a base64-encoded PNG image. Use it to inform the site structure, page names, and descriptions as needed.

Turn the user's idea into a JSON specification of the site with pages only, without choosing concrete UI components or implementation details.
"""

# Use OpenAI Structured Outputs with GPT-4.1
chat = ChatOpenAI(
  model="gpt-4o",
  temperature=0
)

planner_prompt, (gemini_formatter, _) = make_structured_prompt(
    Spec,
    system_prompt
)

# Create the execution chain with proper function wrapping
chain = (
    planner_prompt
    | RunnableLambda(lambda x: gemini_formatter(x))
    | _log_step("formatted prompt")
    | chat
    | _log_step("chat output")
) 
