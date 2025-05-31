from typing import TypedDict, Annotated, Union, Sequence, List, Any, Optional, Dict, Literal
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END, START
from .load_model import load_model
import json
import operator
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig, RunnableLambda
from pydantic import BaseModel, Field
import logging
import asyncio
from langgraph.checkpoint.memory import MemorySaver
# Import designer prompt if needed


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agent_graph")


from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

# Enum for Framework types
class Framework(str, Enum):
    react = "react"
    vue = "vue"
    angular = "angular"
    svelte = "svelte"

# Enhanced PlanStep model
class PlanStep(BaseModel):
    step_number: int
    description: str
    file_outputs: List[str] = Field(
        default_factory=list,
        description="List of file paths created or modified in this step"
    )
    commands: List[str] = Field(
        default_factory=list,
        description="Shell commands required for this step"
    )
    rollback_commands: Optional[List[str]] = Field(
        None, description="Commands to undo this step if it fails"
    )
    is_final_step: Optional[bool] = Field(
        ..., description="Marks the final step, ensuring proper sequence of actions"
    )

# Global AppPlan model with improved structure for managing dependencies and steps
class AppPlan(BaseModel):
    app_name: str
    framework: Framework
    description: str
    dependencies: List[str] = Field(
        ..., description="Top-level npm packages to install, consolidated for efficiency"
    )
    steps: List[PlanStep]

class UIComponent(BaseModel):
    name: str
    props: Dict[str, Any]
    children: Optional[List["UIComponent"]] = []
    file_path: str  # Target file
    type: Literal["component", "page", "layout"]

class AgentBrain(BaseModel):
    evaluation_previous_goal: str  = Field(..., description="concise assessment of the last goal")
    memory: str                    = Field(..., description="cumulative summary of what’s built so far")
    next_goal: str                 = Field(..., description="the next action, or 'DONE' when finished")



class ArtifactFile(BaseModel):
    path: str = Field(..., description="Relative file path")
#    template: str = Field(..., description="Exact file contents as a template string")

class ArtifactAsset(BaseModel):
    path: str = Field(..., description="Relative asset path")
    download_url: str = Field(..., description="URL to fetch the asset from")

class ArtifactSpec(BaseModel):
    artifact_id: str = Field(..., description="Unique ID for the artifact")
    title: str = Field(..., description="Human-readable title")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="package.json dependencies")
    devDependencies: Dict[str, str] = Field(default_factory=dict, description="package.json devDependencies")
    scripts: Dict[str, str] = Field(default_factory=dict, description="package.json scripts")
    files: List[ArtifactFile] = Field(default_factory=list, description="files to create with templates")
    assets: Optional[List[ArtifactAsset]] = Field(default=None, description="optional assets to download")


class AgentState(BaseModel):
    """State of the agent."""
    cwd: str = Field(default=".", description="Current working directory")
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: Union[AgentAction, AgentFinish, None] = None
    return_direct: bool = False
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add] = Field(default_factory=list)
    model_name: str = ""
    test_mode: bool = False  # Flag to indicate if we're in test mode
    test_responses: Optional[List[Dict[str, Any]]] = None  # Predefined responses for testing
    app_plan: Optional[AppPlan] = None  # App plan for the agent
    use_planner: bool = False  # Flag to indicate if we should use the planner
    ui_components: Optional[List[UIComponent]] = None
    step_count: int = 0
    max_steps: int = 1
    agent_brain: Optional[Annotated[list[AgentBrain], operator.add]] = Field(default_factory=list)
    artifact_spec: Optional[ArtifactSpec] = None  # Specification for the artifact to create
    artifact_files: Optional[List[ArtifactFile]] = None  # Files to create as part of the artifact

    class Config:
        arbitrary_types_allowed = True

async def create_plan(state: AgentState):
    """Create a step-by-step plan for app creation."""
    logger.info("Creating app plan")
    messages = state.messages
    
    # Create a planning-specific model
    planner_llm = load_model(model_name=state.model_name, tools=[], parser=None)
    structured_planner = planner_llm.with_structured_output(AppPlan)
    
    from .prompts.designer_prompt import system_prompt_designer
    # Add planning instructions to the messages with improved guidance
    planning_messages = [
            SystemMessage(content=system_prompt_designer)
            ] + messages
    
    # Get the plan
    plan = await structured_planner.ainvoke(planning_messages)
    
    # Convert plan to message and add to state
    plan_message = f"""
    # {plan.app_name} Development Plan
    
    {plan.description}
    
    ## Dependencies
    {', '.join(plan.dependencies)}
    
    ## Step-by-Step Plan
    """
    
    for step in plan.steps:
        plan_message += f"\n### Step {step.step_number}: {step.description}\n"
        
        if step.file_outputs:
            plan_message += "\nFiles to create/modify:\n"
            for file in step.file_outputs:
                plan_message += f"- {file}\n"
                
        if step.commands:
            plan_message += "\nCommands to run:\n"
            for cmd in step.commands:
                plan_message += f"- `{cmd}`\n"
                
    logger.info(f"Generated plan: {plan_message}")
    return {"messages": [HumanMessage(content=plan_message)],
            "app_plan": plan
            }


def create_agent_graph(
    tools: List = [], 
    system_prompt=None, 
    design_template=None,
):
    """Create an async LangGraph REACT agent with customizable prompts and testing capabilities.
    
    Args:
        tools: List of available tools
        system_prompt: Optional custom system prompt for formatting instructions
        design_template: Optional design template as a human message
        checkpointer: Optional checkpointer for state persistence
        
    Returns:
        Compiled async StateGraph for the agent
    """
    if tools is None:
        tools = []
        logger.info(f"Creating agent graph with {len(tools)} tools")

    @RunnableLambda
    async def call_brain(state: AgentState):
        """Call the LLM with the current conversation state."""
        logger.info(f"Calling Brain with {len(state.messages)} messages")

        
        llm = load_model(model_name=state.model_name, 
                            test=state.test_mode,
                            parser=AgentBrain,
        )
        from .prompts.brain_prompt import get_brain_prompt

        inputs = [
            SystemMessage(content=get_brain_prompt(
                current_step=state.step_count,
                max_steps=state.max_steps,
            )),
            ] + state.messages

        response = await llm.ainvoke(input=inputs)
        print(f"Response: {response}")
        # Return updated state with the response
        return {
            "agent_brain": [response],
            }

    @RunnableLambda
    async def spec_creator(state: AgentState):
        """Generate an application spec from a user request."""
        logger.info(f"Spec creator called with {len(state.messages)} messages")

        messages = [
            SystemMessage(content=system_prompt),
        ] + state.messages

        llm = load_model(model_name="gpt-4.1-nano")
        llm_with_struct = llm.with_structured_output(schema=ArtifactSpec, method="function_calling")

        # Generate the spec
        spec = await llm_with_struct.ainvoke(messages)
        
        # Debug logging to see what we got
        logger.info(f"Generated spec - dependencies: {spec.dependencies}")
        logger.info(f"Generated spec - devDependencies: {spec.devDependencies}")
        logger.info(f"Generated spec - scripts: {spec.scripts}")
        logger.info(f"Generated spec - files: {len(spec.files)} files")
        
        return {
            "artifact_spec": spec
        }

    @RunnableLambda
    async def call_create_agent(state: AgentState, config: RunnableConfig):
        """
        2nd stage: consume the ArtifactSpec and emit the final boltArtifact.
        """
        spec = state.artifact_spec
        print(f"Spec: {spec}")

        print(f"Invoking create agent with {len(state.messages)} messages")

        llm = load_model(
            model_name=state.model_name,
            tools=tools,
            test=state.test_mode,
        )

        length = len(state.messages)
        from .prompts.creator_prompt import get_unified_creator_prompt
        from .prompts.creator_prompt import get_creator_prompt

        #creator_prompt = get_creator_prompt(
        #    tools=tools,
        #    cwd=state.cwd,
        #    spec=spec,
        #    ui_components=state.ui_components if hasattr(state, 'ui_components') else [],
        #)
        combined_system_prompt = get_unified_creator_prompt(
            user_request=state.messages[-1].content if length > 0 else "Create an application",
            cwd=state.cwd,
            tools=tools,
            ui_components=state.ui_components if hasattr(state, 'ui_components') else [],
        )

        inputs = [
            SystemMessage(content=combined_system_prompt)
            ] + state.messages
        
        response = await llm.ainvoke(input=inputs)
        print(f"Creator response: {response}")

        # Return the generated artifact and increment step
        return {
            "messages": [response],
            "step_count": state.step_count + 1,
        }

    @RunnableLambda
    async def process_tool_execution(state: AgentState):
        """Execute tools and track intermediate steps."""
        # Get the last message with tool calls
        last_message = state.messages[-1]
        if not (isinstance(last_message, AIMessage) and last_message.tool_calls):
            return state

        tool_call = last_message.tool_calls[0]
        tool_name = tool_call["name"]
        tool_input = tool_call["args"]
        
        # Log the tool execution
        logger.info(f"Executing tool: {tool_name} with input: {str(tool_input)[:100]}...")

        # For all other tools (not ArtifactSpec), use normal ToolNode processing
        tool_node = ToolNode(
            tools=tools,
            handle_tool_errors=lambda exception: (
                f"Error executing tool {tool_name}: {str(exception)}"
            ),
        )
        
        result = await tool_node.ainvoke(state)
        
        # Create the agent action record
        agent_action = AgentAction(
            tool=tool_name,
            tool_input=tool_input,
            log=last_message.content
        )
        
        # Get the tool message content
        tool_message = result["messages"][-1]
        logger.info(f"Tool message: {tool_message}")
        
        # Add to intermediate steps
        new_steps = state.intermediate_steps + [(agent_action, str(tool_message.content))]
        
        logger.info(f"New intermediate steps: {len(new_steps)}")
        
        return {
            "messages": result["messages"],
            "intermediate_steps": new_steps,
            "step_count": state.step_count + 1,
        }
        
    
    # Update the workflow
    workflow = StateGraph(AgentState)
    logger.info("Initializing state graph")
    
    workflow.add_node("planner", call_brain)
    workflow.add_node("agent", call_create_agent)
    workflow.add_node("spec_creator", spec_creator)
    workflow.add_node("tools", process_tool_execution)

    def where_to_start(state: AgentState) -> str:
        """Determine where to start based on state."""
#        if len(state.messages) > 1:
#            logger.info("Starting with planner")
#            return "enhacer"
        if state.use_planner:
            logger.info("Using planner for initial step")
            return "planner"
        else:
            logger.info("Starting with agent")
            return "agent"
        
    #workflow.add_edge(START, "spec_creator")

    # 3. From START, route to planner *or* agent based on state.use_planner
    workflow.add_conditional_edges(
        START,
        where_to_start,
        {
            "planner": "planner",
            "agent": "agent"
        }
    )

    def decide_next(state: AgentState) -> str:
        """Determine if we should go to planner or agent."""
        # Add debug logging to understand what's happening
        logger.info(f"Decision checking: step_count={state.step_count}, max_steps={state.max_steps}")
#        logger.info(f"Brain next_goal={state.agent_brain[-1].next_goal}")
        
        # Force DONE if we've reached max steps, regardless of what the brain says
        if state.step_count >= state.max_steps:
            logger.info("Decision: Max steps reached, forcing workflow to end")
            # Optionally override the brain's next_goal
            # state.agent_brain[-1].next_goal = "DONE"
            return "end"
        
        # If brain explicitly said we're done
#        if state.agent_brain[-1].next_goal == "DONE":
#            logger.info("Decision: Brain indicated DONE, ending workflow")
#            return "end"
        
        else:
            logger.info("Decision: Continue to agent")
            return "agent"

    # 4. If we *did* go to planner, always hand off to agent next
    workflow.add_conditional_edges(
        "planner",
        decide_next,
        {
            "agent": "agent",
            "end": END
        }
    )
        
    # Define conditional edge routing
    def should_continue(state: AgentState) -> str:
        """Determine if we should continue with tools or end the conversation."""
        last_message = state.messages[-1]
        
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            logger.info("Decision: Agent requested tool execution")
            return "tools"
        elif state.use_planner:
            logger.info("Decision: Agent completed task, ending workflow")
            return "planner"
        else:
            logger.info("Decision: No tools requested, ending workflow")
            return "end"
    
    # Connect nodes
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "planner": "planner",
            "end": END
        }
    )
    workflow.add_edge("tools", "agent")
    
    logger.info("Graph structure defined and edges connected")
    

    logger.info("Compiling graph with checkpointer")
    return workflow.compile(checkpointer=MemorySaver())