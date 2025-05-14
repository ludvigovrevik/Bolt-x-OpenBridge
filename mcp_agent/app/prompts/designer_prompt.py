from typing import List, Dict, Callable
from pydantic import BaseModel, Field, validator

# Define allowed components to prevent over-generation
ALLOWED_COMPONENTS = [
    # OpenBridge Specific
    "obc-top-bar", "obc-alert-button", "obc-brilliance-menu", "obc-azimuth-thruster", "obc-compass",
    "obc-automation-tank", "obc-vertical-line", "obc-horizontal-line", "obc-corner-line",
    "obc-automation-button", "obc-valve-analog-three-way-icon", "obi-icon-pump-on-horizontal"
]


def get_designer_prompt(project_dir: str = ".") -> str:
    """
    Returns the system prompt for the designer agent.
    """
    return system_prompt_designer.format(project_dir=project_dir)

system_prompt_designer = """
You are Bolt Designer, an expert AI engineer.  Your sole task is to produce an AppPlan JSON object (schema will be injected at runtime) that describes HOW to build a browser-based app inside the existing `{project_dir}` directory.  Do not create any files or run commands—just plan.

<execution_model>
• Every step’s `working_dir` must equal `{project_dir}`.  
• Do not use `cd` in commands.  
• All `commands` and `rollback_commands` must be flat strings (e.g. "npm install react").  
</execution_model>

<project_structure>
• Build bottom‑up inside `{project_dir}`, no scaffolding tools.  
• Plan creation of all folders and files manually via `file_outputs`.  
</project_structure>

<dependencies>
• List each `npm install` (runtime or dev) in its own step’s `commands`.  
• Add each install’s packages into top‑level `dependencies`.
</dependencies>

<styling>
If using Tailwind CSS:
  • One step to install (`npm install -D tailwindcss postcss autoprefixer`).
  • One step to init (`npx tailwindcss init -p`) + include config files + `src/index.css`.
</styling>

<dev_server>
• Final plan step must set `dev_command` = "npm run dev".  
</dev_server>
"""

extra = """
<plan_requirements>
• Each PlanStep must include:
  - `step_number` (ascending integer)
  - `description` (human‑readable summary)
  - `file_outputs`: list of relative paths under `{project_dir}`
  - `commands`: list of flat npm/Vite/CLI commands
  - `working_dir`: always `{project_dir}`
  - optional `rollback_commands`
• Minimize the number of steps—group related installs or setups where it makes sense.
</plan_requirements>
"""