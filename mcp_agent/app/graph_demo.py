# graph.py
from typing import TypedDict, Annotated, Union, Sequence, Optional, Dict, List
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

class AgentState(BaseModel):
    """State of the agent."""
    cwd: str = Field(default=".", description="Current working directory")
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: Union[AgentAction, AgentFinish, None] = None
    return_direct: bool = False
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]  = Field(default_factory=list)
    model_name : str = "gpt-4o"  # Default model name
    """Extended state with design specifications"""

class EnhancedAgentState(AgentState):
    """Extended state with design specifications"""
    design_spec: Optional[DesignSpecification] = None
    current_files: Dict[str, str] = Field(default_factory=dict)
    implementation_plan: List[str] = Field(default_factory=list)


######################## AGENTS ##################################


async def design_analyst(state: EnhancedAgentState, config: RunnableConfig):
    # Get the latest user message
    latest_user_message = state.messages[-1].content if state.messages else ""
    
    # Create a structured prompt for the design analyst
    design_prompt = f"""
    You are analyzing a web application design request to create OpenBridge UI components.
    
    <user_request>
    {latest_user_message}
    </user_request>
    
    <current_state>
    Existing Files: {json.dumps(list(state.current_files.keys()))}
    Previous Design Spec: {json.dumps(state.design_spec.dict() if state.design_spec else {})}
    </current_state>
    
    Enhance this request with professional UI/UX design considerations for an OpenBridge application.
    Focus on component selection, layout structure, and visual coherence.
    """
    llm = load_model(model_name=state.model_name)
    # Call the LLM with this focused prompt
    design_enhanced_prompt = await llm.ainvoke({"prompt": design_prompt})
    
    # Return enhanced design analysis as a system message to be part of the context
    return {"messages": [SystemMessage(content=f"Design Analysis: {design_enhanced_prompt}")]}



async def spec_generator(state: EnhancedAgentState, config: RunnableConfig):
    # Generate structured design spec
    system_prompt = get_designer_prompt(
        cwd=config.get("cwd", "."),
        file_list=list(state.current_files.keys()),
        prev_spec=state.design_spec.dict() if state.design_spec else {}
    )
    
    input = [
        SystemMessage(content=system_prompt),
        *state.messages  # Include all conversation context
    ]
    
    # Use the model with the DesignSpecification parser
    struct_llm = load_model(model_name=state.model_name, parser=DesignSpecification)
    spec = await struct_llm.ainvoke(input)
    
    # Since the model already returns a DesignSpecification object, we can use it directly
    # No need for DesignSpecification(**spec)
    return {"design_spec": spec, "messages": [SystemMessage(content=f"Design specification created successfully.")]}



async def implementation_planner(state: EnhancedAgentState, config: RunnableConfig):
    if not state.design_spec:
        return {"messages": [SystemMessage(content="No design specification available for planning.")]}
    
    planning_prompt = f"""
    You are creating an implementation plan based on the design specification for an OpenBridge web application.
    
    <design_specification>
    {json.dumps(state.design_spec.dict(), indent=2)}
    </design_specification>
    
    Create a step-by-step implementation plan that includes:
    1. File structure
    2. Required dependencies
    3. Component hierarchy
    4. Implementation order
    """
    llm = load_model(model_name=state.model_name)
    # Generate the implementation plan
    plan_result = await llm.ainvoke({"prompt": planning_prompt})
    
    # Create a structured plan
    implementation_steps = plan_result.strip().split("\n")
    
    return {
        "implementation_plan": implementation_steps,
        "messages": [SystemMessage(content=f"Implementation plan created with {len(implementation_steps)} steps.")]
    }



async def agent_with_artifacts(state: EnhancedAgentState, config: RunnableConfig):
    # Ensure we have the necessary design info
    if not state.design_spec:
        return {"messages": [AIMessage(content="I need more information about the design requirements before I can create the implementation.")]}
    
    # Prepare the context with all the design information
    design_context = f"""
    <design_specification>
    Project Goals: {', '.join(state.design_spec.project_goals)}
    UI Components: {', '.join(state.design_spec.ui_components)}
    Layout: {json.dumps(state.design_spec.layout, indent=2)}
    Color Palette: {json.dumps(state.design_spec.color_palette, indent=2)}
    Interactions: {', '.join(state.design_spec.interactions)}
    Constraints: {', '.join(state.design_spec.constraints)}
    Dependencies: {', '.join(state.design_spec.dependencies)}
    </design_specification>
    
    <implementation_plan>
    {'\n'.join(state.implementation_plan if state.implementation_plan else ["No implementation plan available"])}
    </implementation_plan>
    
    <existing_files>
    {json.dumps(list(state.current_files.keys()))}
    </existing_files>
    """
    
    # Create a final prompt that will generate artifacts
    artifact_prompt = get_prompt(
        cwd=state.cwd,
        tools=config.get("tools", [])
    )
    
    # Combine all context into a single message
    full_context = [
        SystemMessage(content=
                      f"{artifact_prompt}\n\n{design_context}"),
    ] + state.messages
    llm = load_model(model_name=state.model_name)
    # Call the model with the artifact-focused prompt
    artifact_result = await llm.ainvoke(full_context)
    
    # Return the result which should contain the boltArtifact structures
    return {"agent_outcome": artifact_result}








def create_agent_graph(llm, tools, prompt, checkpointer=None):
    workflow = StateGraph(EnhancedAgentState)
    
    # Add all nodes
    workflow.add_node("design_analyst", design_analyst)
    workflow.add_node("spec_generator", spec_generator)
    workflow.add_node("implementation_planner", implementation_planner)
    workflow.add_node("agent", agent_with_artifacts)
    workflow.add_node("tools", tool_node)
    
    # Set the flow
    workflow.set_entry_point("design_analyst")
    workflow.add_edge("design_analyst", "spec_generator")
    workflow.add_edge("spec_generator", "implementation_planner")
    workflow.add_edge("implementation_planner", "agent")
    
    # Conditional tool usage after agent
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"continue": "tools", "end": END}
    )
    workflow.add_edge("tools", "agent")
    
    return workflow.compile(checkpointer=checkpointer)