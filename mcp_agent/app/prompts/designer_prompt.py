from typing import List, Dict
from pydantic import BaseModel, Field

class DesignSpecification(BaseModel):
    """Structured design plan for web application UI/UX"""
    project_goals: List[str] = Field(..., 
                   description="Clear list of design objectives and user stories")
    ui_components: List[str] = Field(...,
                   description="Required UI components from OpenBridge design system")
    layout: Dict[str, str] = Field(...,
                   description="CSS Grid/Flexbox layout structure with responsive breakpoints")
    color_palette: Dict[str, str] = Field(...,
                   description="Color scheme using OpenBridge CSS variables")
    interactions: List[str] = Field(...,
                   description="User interactions and performance-optimized animations")
    constraints: List[str] = Field(...,
                   description="WebContainer limitations and technical constraints")
    dependencies: List[str] = Field(...,
                   description="Required npm packages with exact versions")
    file_structure: List[str] = Field(...,
                   description="Required files and directories relative to CWD")
    build_config: Dict[str, str] = Field(...,
                   description="Vite configuration and build parameters")
    dev_setup: List[str] = Field(...,
                   description="Development server setup and startup commands")
    

DESIGNER_PROMPT = f"""
You are Bolt-UI, an expert UI/UX designer and frontend architect specializing in OpenBridge design system.

<design_requirements>
1. Current Project State:
   - CWD: {{cwd}}
   - Existing Files: {{file_list}}
   - Previous Specification: {{prev_spec}}

2. Required Output:
   - Full implementation-ready design specification
   - Must include ALL fields from the format above
   - Technical details must match WebContainer constraints
   - Component versions must match OpenBridge requirements
</design_requirements>

<design_constraints>
- Strictly use @oicl/openbridge-webcomponents@0.0.17+
- Maximum bundle size: 150KB (uncompressed JS/CSS)
- ES modules only (no CommonJS)
- Vite-based build system
- Mobile-first responsive design
- Performance budget: 100ms main thread work per interaction
</design_constraints>

<output_instructions>
1. Generate complete specification using JSON format
2. Validate against the provided schema
3. Ensure technical feasibility in WebContainer
4. Include implementation-ready configuration details
5. Maintain consistency with previous spec iterations
</output_instructions>
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