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

    class Config:
        min_anystr_length = 1  # Ensure all strings have a minimum length
        anystr_strip_whitespace = True  # Strip unnecessary whitespace from string inputs


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

    class Config:
        arbitrary_types_allowed = True

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


    @RunnableLambda
    async def call_create_agent(state: AgentState, config: RunnableConfig):
        """Call the LLM with the current conversation state."""
        logger.info(f"Calling model {state.model_name} with {len(state.messages)} messages")
        plan_content = [state.messages[-1]]
    
        llm = load_model(model_name=state.model_name, 
                         tools=tools,
                         test=state.test_mode,
        )
        from .prompt import get_prompt
        from .prompts.creator_prompt import get_creator_prompt
        from .prompt import get_test_prompt
        test_prompt = get_test_prompt(
            cwd=state.cwd,
            tools=tools,
        )
        
        
        inputs = [
            SystemMessage(content=get_creator_prompt())
            ] + plan_content

        response = await llm.ainvoke(input=inputs)
        print(f"Response: {response}")
        # Return updated state with the response
        return {
            "messages": [response],
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
        logger.info(f"Executing tool: {tool_name} with input: {json.dumps(tool_input)[:100]}...")
        
        # Create tool node for this execution
        tool_node = ToolNode(
            tools=tools,
            handle_tool_errors=lambda exception, tool_call: (
                f"Error executing tool {tool_call.get('name')}: {str(exception)}"
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
        
        # Add to intermediate steps
        new_steps = state.intermediate_steps + [(agent_action, tool_message.content)]
        
        logger.info(f"New intermediate steps: {len(new_steps)}")
        
        # Return updated state
        return {
            "messages": result["messages"],
            "intermediate_steps": new_steps
        }
        
    
    # Update the workflow
    workflow = StateGraph(AgentState)
    logger.info("Initializing state graph")
    
    workflow.add_node("planner", create_plan)
    workflow.add_node("agent", call_create_agent)
    workflow.add_node("tools", process_tool_execution)

    # 3. From START, route to planner *or* agent based on state.use_planner
    workflow.add_conditional_edges(
        START,
        lambda state: "planner" if state.use_planner else "agent",
        {
            "planner": "planner",
            "agent": "agent"
        }
    )

    # 4. If we *did* go to planner, always hand off to agent next
    workflow.add_edge("planner", "agent")
        
    # Define conditional edge routing
    def should_continue(state: AgentState) -> str:
        """Determine if we should continue with tools or end the conversation."""
        last_message = state.messages[-1]
        
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            logger.info("Decision: Agent requested tool execution")
            return "tools"
        else:
            logger.info("Decision: Agent completed task, ending workflow")
            return "end"
    
    # Connect nodes
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    workflow.add_edge("tools", "agent")
    
    logger.info("Graph structure defined and edges connected")
    

    logger.info("Compiling graph with checkpointer")
    return workflow.compile(checkpointer=MemorySaver())