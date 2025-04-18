from typing import List, Dict, Callable
from pydantic import BaseModel, Field, validator

# Define allowed components to prevent over-generation
ALLOWED_COMPONENTS = [
    # OpenBridge Specific
    "obc-top-bar", "obc-alert-button", "obc-brilliance-menu", "obc-azimuth-thruster", "obc-compass",
    "obc-automation-tank", "obc-vertical-line", "obc-horizontal-line", "obc-corner-line",
    "obc-automation-button", "obc-valve-analog-three-way-icon", "obi-icon-pump-on-horizontal"
]

# Maximum number of components to prevent overloading
MAX_COMPONENTS = 8 # Keep this limit reasonable

class DesignSpecification(BaseModel):
    """Structured design plan for web application UI/UX"""
    project_goals: List[str] = Field(...,
                   description="Clear list of design objectives and user stories")
    ui_components: List[str] = Field(...,
                   description="Required UI components from OpenBridge design system",
                   max_items=MAX_COMPONENTS)

    @validator('ui_components')
    def validate_components(cls, v):
        invalid_components = [c for c in v if c not in ALLOWED_COMPONENTS]
        if invalid_components:
            raise ValueError(f"Invalid components: {invalid_components}. Use only from allowed list: {ALLOWED_COMPONENTS}")
        if len(v) > MAX_COMPONENTS:
            raise ValueError(f"Too many components: {len(v)}. Maximum allowed: {MAX_COMPONENTS}")
        return v

    layout: List[str] = Field(...,
                   description="CSS layout rules formatted as ['breakpoint:css-grid/flex-declaration', ...]")
    color_palette: List[str] = Field(...,
                   description="Color scheme using OpenBridge CSS variables formatted as ['--var-name: value', ...]")
    interactions: List[str] = Field(...,
                   description="User interactions and performance-optimized animations")
    constraints: List[str] = Field(...,
                   description="WebContainer limitations and technical constraints")
    dependencies: List[str] = Field(...,
                   description="Required npm packages with exact versions")
    file_structure: List[str] = Field(...,
                   description="Required files and directories relative to CWD")
    build_config: List[str] = Field(...,
                   description="Vite configuration parameters as ['configKey=value', ...]")
    dev_setup: List[str] = Field(...,
                   description="Development server setup and startup commands")

# Define required Vite configuration parameters (adjust if not using Vite)
REQUIRED_VITE_CONFIG = [
    "build.outDir",
    "build.rollupOptions",
    "plugins",
    "server.port"
] # Keep this, but note it might not apply to all setups

DESIGNER_PROMPT = f"""
You are Bolt-UI, an expert UI/UX designer and frontend architect specializing in OpenBridge design system and WebContainer environments.

<component_limitations>
IMPORTANT: You must select components ONLY from this approved list: {ALLOWED_COMPONENTS}
Maximum number of components allowed: {MAX_COMPONENTS}
Exceeding these limits will cause build failures and performance issues.
</component_limitations>

<vite_configuration_requirements>
If using Vite, your design MUST include configuration for these parameters: {REQUIRED_VITE_CONFIG}
Ensure proper configuration for WebContainer compatibility. If using a different setup (like live-server), adapt accordingly.
</vite_configuration_requirements>

<design_requirements>
1. Current Project State:
   - CWD: {{cwd}}
   - Existing Files: {{file_list}}
   - Previous Specification: {{prev_spec}}

2. Required Output:
   - Full implementation-ready design specification using the DesignSpecification model.
   - Must include ALL fields from the model format.
   - Technical details must match WebContainer constraints (no native binaries, Python stdlib only, prefer Node.js scripts, Vite or live-server).
   - Component versions must match OpenBridge requirements (@oicl/openbridge-webcomponents@0.0.17+).
   - Adhere strictly to OpenBridge setup: theme/size attributes, Noto Sans font setup (including download command), CSS variable import, component JS imports (lowercase attributes for top-bar/alert-button, no alert-bell icon import, default top-bar/brilliance menu with JS logic).
   - Ensure body background uses `var(--container-background-color)`.
   - For diagrams: Use absolute positioning with calc() and relative container; ensure alignment with top-bar.
</design_requirements>

<design_constraints>
- Strictly use @oicl/openbridge-webcomponents@0.0.17+
- ES modules only (no CommonJS)
- Build system: Vite OR live-server (determine based on context or user request)
- WebContainer limitations apply (no pip, no C++/native binaries)
</design_constraints>

<output_instructions>
1. Generate complete specification using JSON format conforming to the DesignSpecification model.
2. Validate against the provided schema (ALLOWED_COMPONENTS, MAX_COMPONENTS).
3. Ensure technical feasibility in WebContainer.
4. Include implementation-ready configuration details (dependencies, file structure, build/dev setup).
5. Maintain consistency with previous spec iterations if provided.
6. Prioritize visual accuracy if image/Figma input is given.
</output_instructions>

<reasoning_and_planning_guidelines>
  **CRITICAL: Before generating the design specification JSON, you MUST perform a detailed reasoning and planning step.** This involves:

  1.  **Analyze Inputs Thoroughly:**
      - **Visuals (Image/Figma):** Examine images/Figma. Identify components, layout, text, colors, icons. Prioritize matching visuals. Extract layout details.
      - **Code:** Review existing code. Understand structure, functionality. Note existing variables, functions, components.
      - **Text Description:** Parse user request for requirements, constraints, functionality.
  2.  **Synthesize Requirements:** Combine insights. Prioritize visual source (Image > Figma > Text) unless user specifies otherwise. Resolve conflicts.
  3.  **Identify Components:** List needed OpenBridge components (e.g., `<obc-tank>`). Check availability against `ALLOWED_COMPONENTS`. Note custom elements/interactions.
  4.  **Plan Implementation Details (for Design Spec fields):**
      - **Layout:** Define CSS grid/flex rules per breakpoint. For diagrams, specify absolute positioning strategy.
      - **Color Palette:** List required OpenBridge CSS variables (e.g., `--container-background-color`).
      - **Interactions:** Describe animations, user flows, theme switching logic.
      - **Constraints:** Reiterate relevant WebContainer/OpenBridge limits (lowercase attributes, icon exclusions, etc.).
      - **Dependencies:** List exact npm packages and versions (e.g., `@oicl/openbridge-webcomponents@0.0.17`, `live-server` or `vite`).
      - **File Structure:** Define necessary files/directories (e.g., `public/fonts`, `public/css`, `public/js`).
      - **Build Config:** Specify Vite parameters (if using Vite).
      - **Dev Setup:** Detail `npm install` and `npm run dev` (or `live-server`) commands, including font download command.
  5.  **Pre-computation:** Calculate coordinates, sizes, etc., needed for the design spec.

  **Output the Plan:** Briefly summarize this plan *before* generating the JSON specification.
</reasoning_and_planning_guidelines>
"""

def get_designer_prompt(
        cwd: str,
        file_list: List[str],
        prev_spec: Dict[str, List[str]], # Corrected type hint for prev_spec
        ):
    """
    Returns the designer prompt template with the current working directory, file list, and previous design spec.
    """
    return DESIGNER_PROMPT.format(cwd=cwd, file_list=file_list, prev_spec=prev_spec)

if __name__ == "__main__":
    # Example usage
    cwd = "/path/to/project"
    file_list = ["index.html", "styles.css"]
    prev_spec = {"project_goals": ["Create a responsive layout"]} # Corrected type

    prompt = get_designer_prompt(cwd, file_list, prev_spec)
    print(prompt)
