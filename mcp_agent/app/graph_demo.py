# graph_demo.py
from typing import TypedDict, Annotated, Union, Sequence, Optional, Dict, List, Tuple, Any
from langgraph.graph import StateGraph, END, START
from .load_model import load_model
import operator
import json # Ensure json is imported
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field
from .load_model import load_model
from .prompt import get_prompt
from langgraph.prebuilt import create_react_agent
import os
from langchain_core.messages import BaseMessage, HumanMessage
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
# Removed incorrect import: from .prompts.designer_prompt import get_design_template


# Define the state as a Pydantic model for dot walking
class AgentState(BaseModel):
    input: Annotated[List[BaseMessage], operator.add]  # User's input
    design_specification: Optional[Dict] = None # Added field for design spec
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

# Define Pydantic model for structured Design Specification Output (Optional but good practice)
class DesignSpec(BaseModel):
    """Structured design specification"""
    project_goals: List[str] = Field(default=[])
    ui_components: List[str] = Field(default=[])
    layout: Dict = Field(default={})
    color_palette: Dict = Field(default={})
    interactions: List[str] = Field(default=[])
    constraints: List[str] = Field(default=[])
    # Add other fields as expected by your DESIGNER_PROMPT if needed

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
# Restoring the local function definition
def get_design_template(openbridge_example):
    # This template should reflect the MANDATORY structure defined in the designer/artifact prompts
    # It serves as a high-level guide but the detailed structure comes from the prompts.
    return """
        **Standard OpenBridge Vanilla JS Project Structure (High-Level):**

        *   **`package.json`**: Defines project metadata, scripts (`dev: vite`), and dependencies (`@oicl/openbridge-webcomponents`, `vite`).
        *   **`vite.config.js`**: Basic Vite configuration (server port, build output).
        *   **`index.html`**: Main entry point. Contains all HTML structure and the `<script type="module">` tag for all JavaScript logic. Includes link to `src/index.css`.
        *   **`src/index.css`**: Global CSS, including `@font-face` for Noto Sans and base styles.
        *   **`public/fonts/`**: Directory containing the downloaded `NotoSans-VariableFont_wdth,wght.ttf` file.

        **Key Principles:**
        *   All JavaScript MUST reside within the `<script type="module">` in `index.html`.
        *   No separate JS files in `src/`.
        *   Dependencies and setup commands are strictly defined in the main prompts.

        **Example Snippet (Illustrative - Full example in main prompts):**
        ```html
        <!-- index.html -->
        <html lang="en" data-obc-theme="day">
          <head>
            <link rel="stylesheet" href="/src/index.css">
          </head>
          <body class="obc-component-size-regular">
            <obc-top-bar ...></obc-top-bar>
            <main>...</main>
            <script type="module">
              import "@oicl/openbridge-webcomponents/src/palettes/variables.css";
              import "@oicl/openbridge-webcomponents/dist/components/top-bar/top-bar.js";
              // ... other imports and ALL JS logic ...
            </script>
          </body>
        </html>
        ```
        ```css
        /* src/index.css */
        @font-face {{ font-family: "Noto Sans"; src: url("/fonts/NotoSans-VariableFont_wdth,wght.ttf"); }}
        * {{ font-family: "Noto Sans", sans-serif; }}
        body {{ background-color: var(--container-background-color); }}
        ```

        """.format(openbridge_example=openbridge_example) # Keep format in case example is used elsewhere


# Design step function
async def get_design_step():
    async def design_step(state: AgentState) -> dict:
        print("--- Entering Design Step ---")
        # Prepare context for the designer prompt
        # For now, file_list and prev_spec are placeholders
        # In a more advanced setup, these would be dynamically populated
        design_context = {
            "cwd": state.cwd,
            "file_list": "N/A (File listing not implemented)",
            "prev_spec": "N/A (Previous specification tracking not implemented)",
            "input": state.input[-1].content if state.input else "No input provided"
        }

        # Use the DESIGNER_PROMPT defined globally within this file
        formatted_designer_prompt = DESIGNER_PROMPT.format(**design_context)

        designer_model = await get_model(
            model_name=state.model_name,
            test=state.test,
            # Attempt to parse as JSON, though the model might not strictly adhere
            # Consider adding a specific JSON parser if needed
            # parser=DesignSpec # Optional: Use Pydantic parser if model reliably outputs JSON
        )

        print("Invoking Designer Model...")
        design_result_raw = await designer_model.ainvoke(formatted_designer_prompt)
        design_content = design_result_raw.content if hasattr(design_result_raw, 'content') else str(design_result_raw)

        # Attempt to parse the result as JSON
        parsed_spec = None
        try:
            # Basic cleanup attempt before parsing
            json_string = design_content.strip()
            if json_string.startswith("```json"):
                json_string = json_string[7:]
            if json_string.endswith("```"):
                json_string = json_string[:-3]
            json_string = json_string.strip()

            parsed_spec = json.loads(json_string)
            print("Design Specification Parsed Successfully.")
        except Exception as e:
            print(f"Warning: Could not parse design specification as JSON. Using raw string. Error: {e}")
            # Fallback to using the raw string content if JSON parsing fails
            parsed_spec = {"raw_design_output": design_content}

        return {"design_specification": parsed_spec}
    return design_step


# Plan step function (Updated to use design_specification)
async def get_plan_step():
    async def plan_step(state: AgentState) -> dict:
        print("--- Entering Plan Step ---")
        input_content = state.input[-1].content if state.input else ""
        # Convert design spec dict to string for the prompt
        design_spec_str = json.dumps(state.design_specification, indent=2) if state.design_specification else "No design specification provided."

        planner_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert app planner.
    Based on the user's objective and the provided design specification, create a detailed step-by-step plan (max 5 steps) for implementation.
    Focus on the sequence of file creation/modification and necessary commands.
    Reference the design specification for components, layout, and constraints."""),
            ("user", "Objective: {input}\n\nDesign Specification:\n{design_specification}\n\nHigh-Level Template:\n{design_template}"), # Added design_specification
        ])

        planner_message = planner_prompt.format_messages(
            design_template=get_design_template(openbridge_example), # Keep high-level template for context
            input=input_content,
            design_specification=design_spec_str # Pass the generated spec string
        )

        planner = await get_model(
            model_name=state.model_name,
            test=state.test,
            parser=AppPlan
            )

        plan_result = await planner.ainvoke(planner_message)
        return {"app_plan": plan_result.steps}
    return plan_step



# Execute step function (Updated to use design_specification)
async def get_execution_agent(tools: List[Any]):
    async def execute_step(state: AgentState) -> dict:
        print("--- Entering Execute Step ---")
        app_plan = state.app_plan
        # design_template = get_design_template(openbridge_example) # Design template less relevant here now
        design_spec_str = json.dumps(state.design_specification, indent=2) if state.design_specification else "No design specification provided."
        cwd = state.cwd
        model_name = state.model_name
        test_mode = state.test

        if not app_plan:
            print("EXECUTE: No steps in plan to execute")
            return {"past_steps": [("Error", "No steps in plan to execute")]}

        current_step = app_plan[0]
        remaining_steps = app_plan[1:] if len(app_plan) > 1 else []

        # Pass design spec and file details (if available) to the main execution prompt
        # Assuming get_prompt can handle these new arguments
        execution_prompt_obj = get_prompt(
             cwd=cwd,
             tools=tools, # Pass tools to get_prompt if needed by artifact_prompt
             design_specification=state.design_specification # Pass the parsed spec
             # file_details=... # Pass current file details if modifying a specific file
        )
        # execution_prompt = execution_prompt_obj # Assuming get_prompt returns the string/template needed

        model = await get_model(
            model_name=model_name,
            test=test_mode,
            parser=None # Executor agent uses React agent, no specific parser needed here
        )

        # Use the prompt object returned by get_prompt
        executor_agent = create_react_agent(model, tools, prompt=execution_prompt_obj) # Pass the prompt object

        # Prepare context for the agent, now including the design spec
        task_formatted = f"""Execute the following step based on the overall plan and design specification:

        Current Step: {current_step}

        Full Plan (for context): {state.app_plan}
        Design Specification:
        {design_spec_str}

        Current Directory: {cwd}
        """

        print(f"Executing Step: {current_step}")
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



# Replan step function (Updated to use design_specification)
async def get_replan_step():
    async def replan_step(state: AgentState) -> dict:
        print("--- Entering Replan Step ---")
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

        # Create replanner prompt, now including design spec
        replanner_prompt = ChatPromptTemplate.from_template(
        """You are an expert app developer and architect reviewing progress.
        Your objective was: {input}
        The design specification was:
        {design_specification}

        Your original plan was: {app_plan}
        You have completed these steps:
        {past_steps}

        Based on the progress and the design specification, update the plan. Only include steps that still NEED to be done.
        If all steps derived from the design specification and original plan are complete, provide a final response summarizing what was accomplished."""
            )

        input_content = state.input[-1].content if state.input else ""
        design_spec_str = json.dumps(state.design_specification, indent=2) if state.design_specification else "No design specification provided."
        # Track original plan for context
        original_plan = state.app_plan + [step for step, _ in state.past_steps] # This might need adjustment if plan changes significantly

        replanner_message = replanner_prompt.format_messages(
            input=input_content,
            design_specification=design_spec_str, # Pass the design spec
            app_plan=original_plan, # Pass the original plan for context
            past_steps=past_steps_formatted
        )

        # print(f"REPLAN: Evaluating progress with {len(state.past_steps)} steps completed and {len(state.app_plan)} steps remaining") # Removed verbose log

        replanner = await get_model(
            model_name=state.model_name,
            test=state.test,
            parser=Action
        )

        output = await replanner.ainvoke(replanner_message)
        # print(f"REPLAN OUTPUT TYPE: {type(output.action)}") # Removed verbose log

        if isinstance(output.action, Response):
            # print("REPLAN: Task complete - returning final response") # Removed verbose log
            return {"response": output.action.response, "app_plan": []}
        else:  # AppPlan
            if not output.action.steps:
                # print("REPLAN: Empty plan received - treating as completion") # Removed verbose log
                # Provide a default completion message if none was generated
                final_response = "Task completed."
                # Attempt to get a summary from past steps if no explicit response
                if state.past_steps:
                    summary = "\n".join([f"- {step}" for step, _ in state.past_steps])
                    final_response = f"Task completed. Steps taken:\n{summary}"

                return {"response": final_response, "app_plan": []}

            # print(f"REPLAN: Continuing with {len(output.action.steps)} new/updated steps") # Removed verbose log
            return {"app_plan": output.action.steps}

    return replan_step



# Create the graph with dependency injection for tools and checkpointer (Updated for design step)
async def create_agent_graph(tools: list = [], checkpointer=None):
    """
    Create the app development agent graph with optional tools and checkpointer, including a design step.

    Args:
        tools: Optional list of tools to use for the agent
        checkpointer: Optional checkpointer for persistence

    Returns:
        Compiled graph for app development
    """
    design_step = await get_design_step() # Get the design step function
    plan_step = await get_plan_step()
    execute_step = await get_execution_agent(
        tools=tools,
    )
    replan_step = await get_replan_step()

    # Decision function (remains the same)
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

    # Add nodes (including the new design node)
    workflow.add_node("planner", plan_step)
    workflow.add_node("designer", design_step)
    workflow.add_node("execute", execute_step)
    workflow.add_node("replan", replan_step)

    # Add edges (updated flow)
    workflow.add_edge(START, "planner") # Start with the designer
    workflow.add_edge("planner", "designer") # Designer output goes to planner
    workflow.add_edge("designer", "execute") # Planner output goes to executor
    workflow.add_edge("execute", "replan") # Executor output goes to replanner
    workflow.add_conditional_edges(
        "replan", # Replanner decides next step
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

# Example usage - but now async (Updated for design step integration)
async def develop_app(user_request: List[BaseMessage], cwd=".", model_name="gpt-4o", test=False): # Removed design_template param
    app_dev_agent = await create_agent_graph()

    # Initialize state using Pydantic model
    initial_state = AgentState(
        input=user_request, # Pass the list of messages directly
        # design_template is no longer needed here, it's handled internally
        cwd=cwd,
        model_name=model_name,
        test=test
    )

    result = await app_dev_agent.ainvoke(initial_state)

    print("\n=== APP DEVELOPMENT COMPLETE ===")
    print(f"User Request: {user_request}") # Note: user_request here is the list of messages
    print(f"Test Mode: {test}")
    print("\n=== Files Created ===")
    if hasattr(result, 'files_created'):
        for filepath, content in result.files_created.items():
            print(f"\n--- {filepath} ---")
            print(content[:200] + "..." if len(content) > 200 else content)

    print("\n=== Final Response ===")
    if hasattr(result, 'response'):
        print(result.response)
    else:
        print("No final response generated.")

    return result

# Stream results during app development (Updated for design step integration)
async def stream_app_development(user_request: List[BaseMessage], cwd=".", model_name="gpt-4o", test=False): # Removed design_template param
    # Pass empty list for tools if none are specifically needed for the graph creation itself
    app_dev_agent = await create_agent_graph(tools=[])

    # Initialize state using Pydantic model
    initial_state = AgentState(
        input=user_request, # Pass the list of messages directly
        # design_template is no longer needed here
        cwd=cwd,
        model_name=model_name,
        test=test
    )

    print("Starting app development process...")
    print(f"Test Mode: {test}")

    async for event in app_dev_agent.astream(initial_state):
        # Add handling for the new 'designer' step
        if "designer" in event:
             design_data = event['designer']
             if design_data and design_data.get('design_specification'):
                  print("\n=== Designing ===")
                  # Avoid printing the full potentially large spec, just acknowledge
                  print("Generated design specification.")
                  # Optionally print a small part or specific keys if needed for debugging
                  # spec = design_data['design_specification']
                  # print(f"  Goals: {spec.get('project_goals', 'N/A')}")
        elif "planner" in event:
            plan_data = event['planner']
            if plan_data and plan_data.get('app_plan'):
                 print("\n=== Planning ===")
                 for i, step in enumerate(plan_data['app_plan']):
                     print(f"{i+1}. {step}")
        elif "execute" in event:
            print("\n=== Executing ===")
            execute_data = event['execute']
            past_steps_update = execute_data.get('past_steps')
            if past_steps_update:
                current_step, response_content = past_steps_update[-1] # Get the latest step result
                print(f"Action: {current_step}")
                # Basic parsing to show actions without full XML/content
                actions_summary = []
                import re
                # Find file actions
                file_actions = re.findall(r'<boltAction type="file" filePath="([^"]+)">', response_content)
                for filePath in file_actions:
                    actions_summary.append(f"  - Update/Create file: {filePath}")
                # Find shell actions
                shell_actions = re.findall(r'<boltAction type="shell">(.*?)</boltAction>', response_content, re.DOTALL)
                for command in shell_actions:
                    command_text = command.strip() # Get command text
                    display_command = (command_text[:70] + '...') if len(command_text) > 70 else command_text
                    actions_summary.append(f"  - Run command: `{display_command}`")

                if actions_summary:
                    print("\n".join(actions_summary))
                # Optionally print a snippet of text response if no actions found
                elif isinstance(response_content, str) and not file_actions and not shell_actions:
                     print(f"  - Response: {response_content[:100] + '...' if len(response_content) > 100 else response_content}")

        elif "replan" in event:
            print("\n=== Checking Progress ===")
            replan_data = event['replan']
            if replan_data.get('response'):
                 # Final response is handled after the loop
                 pass
            elif replan_data.get('app_plan'):
                 print("Updating plan...")
                 # Updated plan will be shown in the next 'planner' or 'execute' step if applicable
            else:
                 print("Continuing...") # Generic message if no specific update
        elif END in event: # Check for the END event explicitly
             final_result = event.get(END)
             if final_result and final_result.get('response'):
                  print("\n=== Final Result ===")
                  print(final_result['response'])

    # Final result processing might not be needed if handled within the loop by checking END
    # final_result = event.get(END) # LangGraph typically puts final state here
    # if final_result and final_result.get('response'):
    #      print("\n=== Final Result ===")
    #      print(final_result['response'])
    # else:
    #      print("\n=== App Development Complete (No final response message) ===")


# Example execution
if __name__ == "__main__":
    import asyncio

    # Initialize design_template using the *local* function and example
    # design_template is no longer needed

    user_request_content = "Create a simple Todo app with React"
    user_request_message = [HumanMessage(content=user_request_content)]

    # Test the pipeline with test mode
    # asyncio.run(stream_app_development(user_request_message, test=True))

    # Run with actual models
    asyncio.run(stream_app_development(user_request_message, test=False))
