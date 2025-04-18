from pydantic import BaseModel, Field
from ..utils import make_structured_prompt # Changed import path
from pathlib import Path
prompts_dir = Path(__file__).resolve().parent.parent / "prompts"

class FilePatch(BaseModel):
    filename: str
    code: str

# Load modular prompt components
with open(prompts_dir / 'system_constraints.md') as f:
    system_constraints = f.read()
with open(prompts_dir / 'openbridge_defaults.md') as f:
    component_defaults = f.read()
with open(prompts_dir / 'formatting_info.md') as f:
    formatting_rules = f.read()

system_prompt = f"""{system_constraints}

{component_defaults}

{formatting_rules}

For ONE component at a time, emit vanilla Web-Component (Lit optional) code ≤ 200 loc.
Follow OpenBridge design patterns and WebContainer constraints."""

implementer_prompt, (impl_parser, _) = make_structured_prompt(
    FilePatch,
    system_prompt
)
