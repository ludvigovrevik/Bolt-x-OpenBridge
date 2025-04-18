from pydantic import BaseModel, Field
from pathlib import Path
from ..utils import make_structured_prompt # Changed import path

prompts_dir = Path(__file__).resolve().parent.parent / "prompts"

class Verdict(BaseModel):
    action: str = Field(description="'accept' or 'revise'")
    reason: str

# Load modular prompt components
with open(prompts_dir / 'system_constraints.md') as f:
    system_constraints = f.read()
with open(prompts_dir / 'formatting_info.md') as f:
    formatting_rules = f.read()
with open(prompts_dir / 'reasoning_guidelines.md') as f:
    verification_guide = f.read()

system_prompt = f"""{system_constraints}

{formatting_rules}

{verification_guide}

Accept only if:
- All tests pass 
- No lint errors present
- Follows OpenBridge patterns
Otherwise return 'revise' with the single highest-impact fix."""

verifier_prompt, (ver_parser, _) = make_structured_prompt(
    Verdict,
    system_prompt
)
