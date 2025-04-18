from pydantic import BaseModel, Field
from ..utils import make_structured_prompt # Changed import path
from pathlib import Path
prompts_dir = Path(__file__).resolve().parent.parent / "prompts"

class TestReport(BaseModel):
    status: str = Field(description="'pass' or 'fail'")
    failed_tests: list[str]

# Load modular prompt components
with open(prompts_dir / 'system_constraints.md') as f:
    system_constraints = f.read()
with open(prompts_dir / 'formatting_info.md') as f:
    formatting_rules = f.read()
with open(prompts_dir / 'reasoning_guidelines.md') as f:
    testing_guide = f.read()

system_prompt = f"""{system_constraints}

{formatting_rules}

{testing_guide}

Write Playwright tests that:
1. Load the built site
2. Assert no console errors
3. Verify web components are properly defined
4. Ensure Lighthouse accessibility score ≥ 90"""

tester_prompt, (tester_parser, _) = make_structured_prompt(
    TestReport,
    system_prompt
)
