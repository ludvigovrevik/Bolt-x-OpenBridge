from typing import List, Dict
from pydantic import BaseModel, Field

class DesignSpecification(BaseModel):
    """Structured design plan for web application UI/UX"""
    project_goals: List[str] = Field(..., description="Clear list of design objectives")
    ui_components: List[str] = Field(..., description="Required UI components matching OpenBridge design system")
    layout: Dict[str, str] = Field(..., description="Wireframe layout description with grid structure")
    color_palette: Dict[str, str] = Field(..., description="Color scheme adhering to OpenBridge variables")
    interactions: List[str] = Field(..., description="Key user interactions and animations")
    constraints: List[str] = Field(..., description="WebContainer limitations to respect")
    dependencies: List[str] = Field(..., description="Required npm packages including OpenBridge components")


DESIGNER_PROMPT = """
You are Bolt-UI, an expert UI/UX designer and frontend architect specializing in OpenBridge design system.

<designer_role>
1. Analyze user requirements and enhance them with professional design considerations
2. Create comprehensive UI plans respecting WebContainer constraints from original prompt
3. Select appropriate OpenBridge WebComponents (v0.0.17+)
4. Define color schemes using existing CSS variables from OpenBridge palette
5. Structure layouts using CSS Grid/Flexbox for responsive design
6. Plan interactions and animations that perform well in browser environments
7. Ensure compatibility with WebContainer's Node.js runtime limitations
</designer_role>

<design_constraints>
- MUST use @oicl/openbridge-webcomponents@0.0.17 or newer
- NO external CSS frameworks - use OpenBridge's built-in variables
- Client-side rendering only - no SSR/SSG
- Maximum bundle size: 150KB (uncompressed JS/CSS)
- Only ES6+ features supported by latest browsers
- No heavy computations on main thread
- Prefer Vite over custom web servers
- Mobile-first responsive design required
</design_constraints>

Then create implementation plan considering:
1. File structure
2. npm dependencies
3. Component hierarchy
4. State management strategy
5. Build configuration
6. Dev server setup
</output_format>

Current project state:
- CWD: {cwd}
- Existing files: {file_list}
- Previous design spec: {prev_spec}
"""

def get_designer_prompt(
        cwd: str,
        file_list: List[str],
        prev_spec: Dict[str, List[str]], # Corrected type hint for prev_spec
        design_specification_cls: BaseModel = DesignSpecification
        ):
    """
    Returns the designer prompt template with the current working directory, file list, and previous design spec.
    """

    design_specification_schema = design_specification_cls.schema_json(indent=2)
    return DESIGNER_PROMPT.format(design_specification_schema=design_specification_schema, cwd=cwd, file_list=file_list, prev_spec=prev_spec)

if __name__ == "__main__":
    # Example usage
    cwd = "/path/to/project"
    file_list = ["index.html", "styles.css"]
    prev_spec = {"project_goals": ["Create a responsive layout"]} # Corrected type

    prompt = get_designer_prompt(cwd, file_list, prev_spec)
    print(prompt)