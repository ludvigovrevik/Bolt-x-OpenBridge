# graph.py
from typing import TypedDict, Annotated, Union, Sequence, Optional, Dict, List, Tuple, Any
from langgraph.graph import StateGraph, END, START
from .load_model import load_model
import operator
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field
from .load_model import load_model
from .prompt import get_prompt
from langgraph.prebuilt import create_react_agent
import os
from langchain_core.messages import BaseMessage, HumanMessage
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate


# Define the state as a Pydantic model for dot walking
class AgentState(BaseModel):
    input: Annotated[List[BaseMessage], operator.add]  # User's input
    #design_template: str  # User's design template
    app_plan: List[str] = []  # Detailed app development plan
    past_steps: Annotated[List[Tuple[str, str]], operator.add] = []  # Previously executed steps (step, result)
    files_created: Annotated[Dict[str, str], operator.or_] = {}  # Files created so far (filepath, content)
    response: Optional[str] = None  # Final response to user
    model_name: str = "gpt-4.1"
    cwd: str = Field(default=".", description="Current working directory")
    test: bool = False  # Test mode flag

# Define Pydantic models for structured outputs
class AppPlan(BaseModel):
    """Detailed app development plan"""
    steps: List[str] = Field(
        description="Different steps to follow in order to develop the app"
    )

class Response(BaseModel):
    """Response to user"""
    response: str

class Action(BaseModel):
    """Action to perform"""
    action: Union[Response, AppPlan] = Field(
        description="Action to perform. Use Response to respond to user or AppPlan to create/update plan."
    )

# Factory function to get the appropriate model
async def get_model(tools: list = [], prompt: Any =None, parser: BaseModel = None, 
                    model_name: str = None, 
                    test: bool = False) -> BaseChatModel:
    """
    Get the appropriate model based on test flag and model name
    """
    return load_model(
        model_name=model_name,
        tools=tools,
        prompt=prompt,
        parser=parser
        )


# Create the planning agent with structured output
from .prompt import openbridge_example

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
def get_design_template(openbridge_example):
    return """
        Project Structure:
        - src/
        - components/
            - Each component should have its own folder
            - Each folder should contain index.js and styles.css
        - utils/
        - pages/
        - App.js
        - index.js
        
        Styling:
        - Use CSS modules
        - Follow BEM naming convention
        - Use a color scheme of #f5f5f5, #4a90e2, #50e3c2
        
        Component Structure:
        - Functional components with hooks
        - Props should be destructured
        - Each component should have propTypes
        
        State Management:
        - Use React Context API for global state
        - Use useReducer for complex state logic

        Example of what we want:
        {openbridge_example}

        """.format(openbridge_example=openbridge_example)

# Need to work on this prompt to make it more specific to the task
# Plan step function
async def get_plan_step():
    async def plan_step(state: AgentState) -> dict:
        input = state.input[-1].content
        planner_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert app designer and architect. 
    For the given objective and design template, create a detailed step-by-step plan with NO MORE THAN 3 STEPS for developing the app..
    Break down the app development into logical components and files to be created.
    Each step should be specific and actionable, focusing on one file or component at a time.
    The plan should be comprehensive and cover all aspects of the app.
    Consider project structure, dependencies, components, styling, and functionality."""),
            ("user", "Design Template: {design_template}\n\nObjective: {input}"),
        ])

        planner_message = planner_prompt.format_messages(
            design_template=get_design_template(openbridge_example),
            input=input
        )

        planner = await get_model(
            model_name=state.model_name, 
            test=state.test,
            parser=AppPlan
            )
            
        
        plan_result = await planner.ainvoke(planner_message)
        return {"app_plan": plan_result.steps}
    return plan_step



# Execute step function
async def get_execution_agent(tools: List[Any]):
    async def execute_step(state: AgentState) -> dict:
        app_plan = state.app_plan
        design_template = get_design_template(openbridge_example)
        cwd = state.cwd
        model_name = state.model_name
        test_mode = state.test
        
        if not app_plan:
            print("EXECUTE: No steps in plan to execute")
            return {"past_steps": [("Error", "No steps in plan to execute")]}
        
        current_step = app_plan[0]
        remaining_steps = app_plan[1:] if len(app_plan) > 1 else []
        
        print(f"EXECUTE: Processing step: {current_step}")
        print(f"EXECUTE: Remaining steps: {len(remaining_steps)}")
        
        execution_prompt = get_prompt(cwd)
        print("EXECUTE: Invoking prompt for llm agent")
    
        model = await get_model(
            model_name=model_name,
            test=test_mode,
            parser=None
        )
        
        executor_agent = create_react_agent(model, tools, prompt=execution_prompt)
        
        # Prepare context for the agent
        task_formatted = f"""For the following app plan:
        {app_plan}\n\n
        You are tasked with executing step: {current_step}

        Work in the current directory: {cwd}

        Follow the design template: {design_template}
        """
            
        agent_response = await executor_agent.ainvoke({"messages": [("user", task_formatted)]})
        response_content = agent_response["messages"][-1].content
        
        step_name = current_step.lower().replace(" ", "_")
        filename = f"{step_name}"
        
        print(f"EXECUTE: Completed step: {current_step}")
        
        return {
            "past_steps": [(current_step, response_content)],
            "files_created": {filename: response_content},
            "app_plan": remaining_steps
        }
    
    return execute_step



# Replan step function
async def get_replan_step():
    async def replan_step(state: AgentState) -> dict:
        # Safety mechanism to prevent infinite loops
        if len(state.past_steps) > 20:  # Adjust threshold as needed
            print("SAFETY: Maximum iterations reached, forcing termination")
            return {
                "response": "Task execution reached maximum number of steps. Here's what was accomplished:\n" + 
                           "\n".join([f"- {step}" for step, _ in state.past_steps[:10]]) + 
                           ("\n... and more" if len(state.past_steps) > 10 else ""),
                "app_plan": []
            }
        
        # Format past steps
        past_steps_formatted = "\n".join([f"Step: {step}\nResult: {result[:200]}..." if len(result) > 200 else f"Step: {step}\nResult: {result}" for step, result in state.past_steps])
        
        # Create replanner prompt with explicit completion instruction
        replanner_prompt = ChatPromptTemplate.from_template(
        """You are an expert app developer and architect.
        Your objective was: {input}
        Your design template is: {design_template}
        Your original plan was: {app_plan}
        You have completed these steps: {past_steps}

        Update your plan accordingly. Only include steps that still NEED to be done.
        If all steps are complete, provide a final response summarizing what was accomplished."""
            )
        
        input_content = state.input[-1].content if state.input else ""
        # Track original plan for context
        original_plan = state.app_plan + [step for step, _ in state.past_steps]
        
        replanner_message = replanner_prompt.format_messages(
            input=input_content,
            design_template=get_design_template(openbridge_example),
            original_plan=original_plan,
            past_steps=past_steps_formatted
        )
        
        print(f"REPLAN: Evaluating progress with {len(state.past_steps)} steps completed and {len(state.app_plan)} steps remaining")
        
        replanner = await get_model(
            model_name=state.model_name, 
            test=state.test,
            parser=Action
        )
        
        output = await replanner.ainvoke(replanner_message)
        
        print(f"REPLAN OUTPUT TYPE: {type(output.action)}")
        
        if isinstance(output.action, Response):
            print("REPLAN: Task complete - returning final response")
            return {"response": output.action.response, "app_plan": []}
        else:  # AppPlan
            if not output.action.steps:
                print("REPLAN: Empty plan received - treating as completion")
                return {"response": "Task completed successfully!", "app_plan": []}
                
            print(f"REPLAN: Continuing with {len(output.action.steps)} new/updated steps")
            return {"app_plan": output.action.steps}
    
    return replan_step



# Create the graph with dependency injection for tools and checkpointer
async def create_agent_graph(tools: list = [], checkpointer=None):
    """
    Create the app development agent graph with optional tools and checkpointer
    
    Args:
        tools: Optional list of tools to use for the agent
        checkpointer: Optional checkpointer for persistence
    
    Returns:
        Compiled graph for app development
    """
    execute_step = await get_execution_agent(
        tools=tools,
    )
    plan_step = await get_plan_step()
    replan_step = await get_replan_step()

    # Decision function
    def should_continue(state: AgentState) -> str:
        if state.response:
            print(f"DECISION: Ending flow - response provided: {state.response[:30]}...")
            return END
        elif state.app_plan and len(state.app_plan) > 0:
            print(f"DECISION: Continuing execution with {len(state.app_plan)} steps")
            return "execute"
        else:
            print("DECISION: No steps left, going to replan")
            return "replan"


    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planner", plan_step)
    workflow.add_node("execute", execute_step)
    workflow.add_node("replan", replan_step)
    
    # Add edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "execute")
    workflow.add_edge("execute", "replan")
    workflow.add_conditional_edges(
        "replan",
        should_continue,
        {
            "execute": "execute",
            END: END
        }
    )
    
    
    # Add checkpointer if provided
    if checkpointer is not None:
        workflow.compile(checkpointer=checkpointer)
    
    # Compile the graph
    return workflow.compile()

# Example usage - but now async
async def develop_app(user_request, design_template, cwd=".", model_name="gpt-4o", test=False):
    app_dev_agent = await create_agent_graph()
    
    # Initialize state using Pydantic model
    initial_state = AgentState(
        input=user_request,
        design_template=design_template,
        cwd=cwd,
        model_name=model_name,
        test=test
    )
    
    result = await app_dev_agent.ainvoke(initial_state)
    
    print("\n=== APP DEVELOPMENT COMPLETE ===")
    print(f"User Request: {user_request}")
    print(f"Test Mode: {test}")
    print("\n=== Files Created ===")
    for filepath, content in result.files_created.items():
        print(f"\n--- {filepath} ---")
        print(content[:200] + "..." if len(content) > 200 else content)
    
    print("\n=== Final Response ===")
    print(result.response)
    
    return result

# Stream results during app development
async def stream_app_development(user_request, design_template, cwd=".", model_name="gpt-4o", test=False):
    app_dev_agent = await create_agent_graph()
    
    # Initialize state using Pydantic model
    initial_state = AgentState(
        input=user_request,
        design_template=design_template,
        cwd=cwd,
        model_name=model_name,
        test=test
    )
    
    print("Starting app development process...")
    print(f"Test Mode: {test}")
    
    async for event in app_dev_agent.astream(initial_state):
        if "planner" in event:
            print(f"Planning step: {event['planner']}")
        elif "execute" in event:
            print(f"Executing step: {event['execute']}")
        elif "replan" in event:
            print(f"Replanning step: {event['replan']}")
    print("\n=== App Development Complete ===")

# Example execution
if __name__ == "__main__":
    import asyncio
    
    user_request = "Create a simple Todo app with React"
    
    # Test the pipeline with test mode
    #asyncio.run(stream_app_development(user_request, design_template, test=True))
    
    # Run with actual models
    asyncio.run(stream_app_development([HumanMessage(content=user_request)], design_template, test=False))