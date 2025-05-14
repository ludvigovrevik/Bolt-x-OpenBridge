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
from .prompts.designer_prompt import get_designer_prompt


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agent_graph")

from enum import Enum
from typing import Literal, List, Optional, Union
from pydantic import BaseModel, Field


# 1. Enumerations for stronger typing and discoverability
class Framework(str, Enum):
    react = "react"
    vue = "vue"
    angular = "angular"
    svelte = "svelte"


class ActionType(str, Enum):
    shell = "shell"
    file = "file"
    message = "message"


# 2. Base action with a link back to the plan step for traceability
class BaseAction(BaseModel):
    type: ActionType
    step_number: int = Field(..., description="Corresponding PlanStep.step_number")


# 3. ShellAction: break out arguments for easier validation or introspection
class ShellAction(BaseAction):
    type: Literal[ActionType.shell]
    command: str = Field(..., description="The full shell command to execute")
    args: Optional[List[str]] = Field(
        ..., description="Optional list of command-line arguments"
    )


# 4. FileAction: add an operation flag and support for file mode or encoding
class FileOperation(str, Enum):
    create = "create"
    update = "update"


class FileAction(BaseAction):
    type: Literal[ActionType.file]
    file_path: str = Field(..., description="Relative path to the file")
    operation: FileOperation = Field(
        ..., description="Whether this is a create or update operation"
    )
    content: str = Field(..., description="Full file contents")


class MessageAction(BaseAction):
    type: Literal[ActionType.message]
    content: str = Field(..., description="The message content")


# 6. BoltArtifact: track environment, version, and optional metadata
class BoltArtifact(BaseModel):
    type: Literal["artifact"]
    id: str = Field(..., description="Unique identifier in kebab-case")
    title: str = Field(..., description="Human-readable title")
    project_dir: str = Field(..., description="Root folder created in first ShellAction")
    framework: Framework = Field(..., description="Chosen application framework")
    actions: List[Union[ShellAction, FileAction, MessageAction]]

class BoltAction(BaseModel):
    type: Literal["boltAction"]
    step_number: int = Field(..., description="Corresponding PlanStep.step_number")
    action: Union[ShellAction, FileAction, MessageAction] = Field(
        ..., description="The action to be performed"
    )

#    environment: str = Field(
#        "webcontainer",
#        description="Target environment (e.g. webcontainer, node, etc.)"
#    )
#    version: Optional[str] = Field(
#        ..., description="Optional version tag for this artifact"
#    )
#    metadata: Optional[dict] = Field(
#        ..., description="Arbitrary additional metadata"
#    )


# 7. PlanStep: make file_outputs and commands required when present,
#    and include an optional “rollback” command list for error handling
class PlanStep(BaseModel):
    step_number: int
    description: str
    file_outputs: List[str] = Field(
        default_factory=list,
        description="List of file paths created or modified in this step; must start with project_dir/"
    )
    commands: List[str] = Field(
        default_factory=list,
        description="Shell commands required for this step; must operate in project_dir"
    )
    rollback_commands: Optional[List[str]] = None
    working_dir: Optional[str] = Field(
        None, description="If set, commands are meant to run in this directory"
    )

class AppPlan(BaseModel):
    app_name: str
    framework: Framework
    project_dir: str = Field(..., description="The folder name created in step 1")
    description: str
    dependencies: List[str]
    steps: List[PlanStep]

class AgentState(BaseModel):
    """State of the agent."""
    cwd: str = Field(default=".", description="Current working directory")
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: Union[AgentAction, AgentFinish, None] = None
    return_direct: bool = False
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add] = Field(default_factory=list)
    model_name: str = "gpt-4.1-nano"  # Default model name
    test_mode: bool = False  # Flag to indicate if we're in test mode
    test_responses: Optional[List[Dict[str, Any]]] = None  # Predefined responses for testing
    app_plan: Optional[AppPlan] = None  # App plan for the agent
    use_planner: bool = False  # Flag to indicate if we should use the planner
    bolt_artifact: Optional[BoltArtifact] = None  # Bolt artifact to be created

    class Config:
        arbitrary_types_allowed = True

def create_agent_graph(
    tools, 
    system_prompt=None, 
    design_template=None,
    checkpointer=None
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
    logger.info(f"Creating agent graph with {len(tools)} tools")

    async def create_plan(state: AgentState):
        """Create a step-by-step plan for app creation."""
        logger.info("Creating app plan")
        messages = state.messages
        
        # Create a planning-specific model
        planner_llm = load_model(model_name=state.model_name, tools=[], parser=None)
        structured_planner = planner_llm.with_structured_output(AppPlan)
        
        system_prompt_designer = """
You are the design agent. Produce a complete AppPlan for a browser‑based web app in a WebContainer.

For each atomic step:
1. Describe exactly what you will do.
2. List `file_outputs`: an array of file paths created or modified (no shell file commands).
3. List `commands`: only web‑compatible npm/Vite commands.

Hard requirements:
- **No shell‑based file operations.** Do not propose `echo >`, `sed`, `touch`, `cat`, etc. File creation/editing belongs exclusively in `file_outputs`.
- **Environment:** Browser WebContainer, no native binaries.
- **Init:** `npm create vite@latest <app-name> -- --template react`.
- **Dependencies:** Explicit `npm install` or `npm install -D tailwindcss postcss autoprefixer`.
- **Styling:** Include Tailwind: add `tailwind.config.js`, `postcss.config.js`, and `src/index.css` (via `file_outputs`).
- **Dev server:** Include final `npm run dev` command.
- **Atomicity:** One step = one set of files + one set of commands. No mixing.
- **Minimal files:** File contents are not written here; the creator agent will handle full content via FileActions.
- **OpenBridge:** Note any OpenBridge component files in `file_outputs` if used.

Output **only** the AppPlan JSON (matching the AppPlan Pydantic model) — do not emit any code, shell commands, or explanations outside of the plan’s `steps`, `dependencies`, etc.
        """

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
        )#parser=config["configurable"]["parser"])
        system_prompt_1 = """
You are the creator agent. Your job is to translate the AppPlan into a structured BoltArtifact, using one BoltAction per step.

Strict Rules:
- One-to-One Mapping: Each PlanStep → exactly one BoltAction. Never merge or skip steps.
- Action Types:
  - ShellAction for npm/Vite commands (e.g., `npm install`, `npm run dev`, `npx tailwindcss init -p`).
  - FileAction for every path listed in PlanStep.file_outputs:
      • filePath="{{project_dir}}/relative/path/to/file"
      • content = the full, minimal, valid file contents (e.g., package.json skeleton, Tailwind config, React entry/App component).
  - MessageAction only for final user‑facing summaries.
- **No shell commands** like `touch`, `echo`, `sed`, or `cat` for file creation or edits. All file work must be via FileAction.

File Output Rules:
- Every file listed in file_outputs **must** become a FileAction with actual code/text.
- File contents must be minimal, functional, and free of comments or placeholders.

Command Ordering:
1. Initialization (e.g. `npm create vite@latest …`)
2. Dependency installation (`npm install`, `npm install -D …`)
3. File creation/configuration via FileAction
4. Dev server start (`npm run dev`)

Batching:
- You may batch purely directory navigation or purely install flags (e.g., `cd dir && npm install`) only if they belong to the same atomic step.

Output Format:
- Wrap all actions in a single `<boltArtifact id="..." title="...">`
- Emit actions in the exact sequence of the AppPlan steps.

Final notes:
- Avoid placeholders or partial steps.
- Generated actions will run in a browser‑based WebContainer; shell commands must be compatible.

        """
        from .prompt import get_prompt, get_new_prompt
        inputs = [
            SystemMessage(content=get_prompt())
            ] + state.messages

        response = await llm.ainvoke(input=inputs)
        print(f"Response: {response}")
        # Return updated state with the response
        return {
            "bolt_artifact": response,
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