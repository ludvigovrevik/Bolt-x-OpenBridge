# graph.py
from typing import TypedDict, Annotated, Union, Sequence, Optional, Dict, List, Any
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from .load_model import load_model
import json
import operator
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from .prompts.designer_prompt import get_designer_prompt, DesignSpecification
from .load_model import load_model
from .prompts.artifact_prompt import get_prompt


class FileSpecification(BaseModel):
    path: str
    purpose: str
    dependencies: List[str] = Field(default_factory=list)

# Define the structure we want for each file
class ListFileSpecification(BaseModel):
    file: List[FileSpecification] = Field(..., description="List of file specifications")

class AgentState(BaseModel):
    """State of the agent."""
    cwd: str = Field(default=".", description="Current working directory")
    messages: Annotated[Sequence[BaseMessage], operator.add]
    human_input: Optional[list[BaseMessage]] = None
    agent_outcome: Union[AgentAction, AgentFinish, None] = None
    return_direct: bool = False
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]  = Field(default_factory=list)
    model_name : str = "gpt-4.1"  # Default model name
    """Extended state with design specifications"""

class EnhancedAgentState(AgentState):
    """Extended state with design specifications"""
    design_spec: Optional[DesignSpecification] = None
    current_files: Dict[str, str] = Field(default_factory=dict)
    implementation_plan: List[str] = Field(default_factory=list)
    files_to_generate: ListFileSpecification = Field(default_factory=list)  # Will contain FileSpecification objects
    pending_files: List[str] = Field(default_factory=list)
    completed_files: List[str] = Field(default_factory=list)
    current_file_focus: Optional[str] = None


def create_agent_graph(tools=None, checkpointer=None):
    workflow = StateGraph(EnhancedAgentState)

    async def design_spec_generator(state: EnhancedAgentState, config: RunnableConfig):
        # Generate structured design spec
        human_input = state.messages[-1]
        system_prompt = get_designer_prompt(
            cwd=state.cwd,
            file_list=list(state.current_files.keys()),
            prev_spec={} if state.design_spec is None else state.design_spec.dict()
        )

        input = [
            SystemMessage(content=system_prompt),
        ] + state.messages

        struct_llm = load_model(model_name=state.model_name, parser=DesignSpecification)
        design_spec_cls = await struct_llm.ainvoke(input)

        return {
            "design_spec": design_spec_cls,
            "human_input": [human_input],
            }

    async def implementation_planner(state: EnhancedAgentState, config: RunnableConfig):
        """Generate list of files needed based on design spec"""
        if not state.design_spec:
            return {"messages": [AIMessage(content="Design specification missing. Please provide requirements first.")]}

        system_prompt = """Based on the design specification, create a detailed list of files that need to be implemented.
        For each file, provide:
        1. File path/name
        2. Purpose of the file
        3. Dependencies and relationships with other files

        Format your response as a list of objects, where each object has:
        - path: the file path/name
        - purpose: description of the file's purpose
        - dependencies: list of other files it depends on

        Be comprehensive and ensure all necessary files for the complete implementation are included.
        """

        input = [
            SystemMessage(content=system_prompt),
            SystemMessage(content=f"Design Specification: {state.design_spec.schema_json()}"),
        ] + state.messages

        # Generate file implementation plan with proper parsing
        struct_llm = load_model(model_name=state.model_name, parser=ListFileSpecification)
        files_specification = await struct_llm.ainvoke(input)

        # Update state with files that need to be created
        return {
            "files_to_generate": files_specification.file,  # Store the list of files
            "pending_files": [file.path for file in files_specification.file],  # Access the path attribute from each file spec
            "messages": [AIMessage(content=f"Created implementation plan with {len(files_specification.file)} files to generate.")]
        }

    async def file_selector(state: EnhancedAgentState, config: RunnableConfig):
        """Select next file to implement from pending files"""
        if not state.pending_files:
            return {"messages": [AIMessage(content="All files have been generated.")], "current_file_focus": None}

        next_file = state.pending_files[0]
        pending_files = state.pending_files[1:]  # Remove the selected file

        file_details = next((file for file in state.files_to_generate if file.path == next_file), None)

        return {
            "current_file_focus": next_file,
            "pending_files": pending_files,
            "messages": [AIMessage(content=f"Working on file: {next_file}\nPurpose: {file_details.purpose if file_details else 'N/A'}")],
        }


    class  FileGeneratorState

    async def file_generator(state: EnhancedAgentState, config: RunnableConfig):
        """Generate content for the current focus file"""
        if not state.current_file_focus:
            return {"messages": [AIMessage(content="No file selected for generation.")]}

        file_path = state.current_file_focus
        file_details = next((file for file in state.files_to_generate if file.path == file_path), None)

        # Convert Pydantic model to dict if it exists, otherwise use empty dict
        file_details_dict = file_details.dict() if file_details else {}

        system_prompt = get_prompt(
            cwd=state.cwd,
            tools=[],
            file_details=file_details_dict,
            design_specification=state.design_spec.model_dump() if state.design_spec else None,
            )

        input = [
            SystemMessage(content=system_prompt),
        ] + state.human_input

        # Generate file content
        implementation_llm = load_model(model_name=state.model_name)
        file_content = await implementation_llm.ainvoke(input)

        # Update current_files with the new implementation
        current_files = state.current_files.copy()
        current_files[file_path] = file_content

        # Add to completed files
        completed_files = state.completed_files.copy() if hasattr(state, 'completed_files') else []
        completed_files.append(file_path)

        return {
            "current_files": current_files,
            "completed_files": completed_files,
            "messages": [file_content],
        }

    def should_continue_implementation(state: EnhancedAgentState):
        """Determine if we need to continue generating files or end the graph"""
        if state.pending_files:
            return "continue"
        else:
            return "end"

    # Add nodes to the workflow
    workflow.add_node("design_spec_generator", design_spec_generator)
    workflow.add_node("implementation_planner", implementation_planner)
    workflow.add_node("file_selector", file_selector)
    workflow.add_node("file_generator", file_generator)

    # Define workflow logic
    workflow.set_entry_point("design_spec_generator")
    workflow.add_edge("design_spec_generator", "implementation_planner")

    # Add conditional edge for file generation loop
    workflow.add_edge("implementation_planner", "file_selector")

    workflow.add_edge("file_selector", "file_generator")

    # After generating a file, decide whether to continue or end
    workflow.add_conditional_edges(
        "file_generator",
        should_continue_implementation,
        {
            "continue": "file_selector",  # Loop back to select next file
            "end": END
        }
    )


    return workflow.compile(checkpointer=checkpointer)
