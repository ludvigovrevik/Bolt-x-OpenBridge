from typing import TypedDict, Annotated, Union, Sequence, Optional, Dict, List, Tuple, Any
from langgraph.graph import StateGraph, END, START
from .agents.planner import Spec, parser as planner_parser, planner_prompt, chain as planner_chain
 
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

# Import agent schemas and parsers
from .agents.designer import Wireframe, designer_parser, designer_prompt, designer_context
from .agents.implementer import FilePatch, impl_parser
from .agents.tester import TestReport, tester_parser
from .agents.verifier import Verdict, ver_parser


# Define the unified state
class AgentState(BaseModel):
    """State for the multi-agent workflow."""
    input_message: Optional[BaseMessage] = None # Store the initial user request
    plan: Optional[Spec] = None
    design: Optional[Wireframe] = None
    implementation: Optional[FilePatch] = None
    test_report: Optional[TestReport] = None
    verification: Optional[Verdict] = None
    error: Optional[str] = None # To capture errors during steps
    # Add other necessary fields like cwd, model_name if needed globally
    model_name: str = "gpt-4.1" # Example default
    cwd: str = Field(default=".", description="Current working directory")
    # Potentially add fields for intermediate results if needed between steps

# --- Agent Step Functions ---

async def plan_step(state: AgentState) -> Dict[str, Any]:
    """Invokes the planner agent."""
    print("--- Running Planner Step ---")
    # Debugging: inspect inputs
    user_prompt = getattr(state.input_message, "content", "")
    print("__DEBUG__ planner_chain:", planner_chain, type(planner_chain))
    print("__DEBUG__ input_message:", state.input_message, type(state.input_message))
    print("__DEBUG__ user_prompt:", user_prompt, type(user_prompt))
    
    try:
        raw = await planner_chain.ainvoke({"user_prompt": user_prompt})
        print("RAW:", raw, type(raw))
        print("PARSER OBJ:", planner_parser, type(planner_parser))
        print("PARSER.METHOD:", planner_parser.parse, callable(planner_parser.parse))
        text = raw.content if hasattr(raw, "content") else str(raw)
        spec = planner_parser.parse_with_prompt(text)
        # Debugging: inspect parsed spec
        print("__DEBUG__ final parsed spec:", spec, type(spec))
        return {"plan": spec}
    except Exception as e:
        print(f"Planner Error: {e}")
        return {"error": f"Planner Error: {str(e)}"}

async def design_step(state: AgentState) -> Dict[str, Any]:
    """Invokes the designer agent."""
    print("--- Running Designer Step ---")
    if not state.plan:
         return {"error": "Designer Error: No plan found."}
    try:
        llm_chain = load_model(model_name=state.model_name, prompt=designer_prompt)
        # Prepare context for the designer
        # designer_prompt is defined in agents.designer
        # We need the plan and potentially context from the retriever
        # Example: Combine plan and retrieved docs
        plan_content = f"Plan: {state.plan.model_dump_json(indent=2)}"
        # Assuming input_message holds the original query for context retrieval
        context_docs = designer_context([state.input_message])
        context_str = "\n".join([doc.page_content for doc in context_docs])
        
        system_msgs = designer_prompt.format_messages()
        user_msg = HumanMessage(content=f"Plan:\n{plan_content}\n\nRelevant Context:\n{context_str}")
        messages = system_msgs + [user_msg]

        raw = await llm_chain.ainvoke(messages)
        text = raw.content if hasattr(raw, "content") else str(raw)
        try:
            wireframe = designer_parser.parse_with_prompt(text)
            return {"design": wireframe}
        except Exception as e:
            print(f"Designer Error parsing JSON: {repr(e)}")
            return {"error": f"Designer Error parsing JSON: {e}"}
    except Exception as e:
        print(f"Designer Error: {e}")
        return {"error": f"Designer Error: {str(e)}"}

async def implement_step(state: AgentState) -> Dict[str, Any]:
    """Invokes the implementer agent."""
    print("--- Running Implementer Step ---")
    if not state.design:
         return {"error": "Implementer Error: No design found."}
    try:
        model = load_model(model_name=state.model_name, parser=FilePatch)
        # Prepare context for the implementer
        # implementer_prompt is defined in agents.implementer
        design_content = f"Design: {state.design.model_dump_json(indent=2)}"
        messages = [HumanMessage(content=design_content)]

        response = await model.ainvoke(messages)
        # Here you would typically use a tool to write the file
        # For now, just store the intended patch
        print(f"Implementer generated patch for: {response.filename}")
        return {"implementation": response}
    except Exception as e:
        print(f"Implementer Error: {e}")
        return {"error": f"Implementer Error: {str(e)}"}

async def test_step(state: AgentState) -> Dict[str, Any]:
    """Invokes the tester agent."""
    print("--- Running Tester Step ---")
    if not state.implementation:
         return {"error": "Tester Error: No implementation found."}
    try:
        model = load_model(model_name=state.model_name, parser=TestReport)
        # Prepare context for the tester
        # tester_prompt is defined in agents.tester
        # This agent would likely need access to the implemented code/files
        # and potentially tools to run tests (e.g., Playwright via MCP)
        impl_content = f"Implementation: {state.implementation.model_dump_json(indent=2)}"
        messages = [HumanMessage(content=impl_content)]

        # In a real scenario, this step would involve:
        # 1. Writing the code from state.implementation to a file (using a tool).
        # 2. Running tests against that code (using a tool).
        # 3. Passing test results to the LLM to generate the TestReport.
        # For this demo, we simulate the LLM generating a report based on the implementation description.
        response = await model.ainvoke(messages)
        print(f"Tester generated report: Status - {response.status}")
        return {"test_report": response}
    except Exception as e:
        print(f"Tester Error: {e}")
        return {"error": f"Tester Error: {str(e)}"}

async def verify_step(state: AgentState) -> Dict[str, Any]:
    """Invokes the verifier agent."""
    print("--- Running Verifier Step ---")
    if not state.test_report:
         return {"error": "Verifier Error: No test report found."}
    try:
        model = load_model(model_name=state.model_name, parser=Verdict)
        # Prepare context for the verifier
        # verifier_prompt is defined in agents.verifier
        test_content = f"Test Report: {state.test_report.model_dump_json(indent=2)}"
        # Could also include plan, design, implementation for context
        messages = [HumanMessage(content=test_content)]

        response = await model.ainvoke(messages)
        print(f"Verifier result: Action - {response.action}")
        return {"verification": response}
    except Exception as e:
        print(f"Verifier Error: {e}")
        return {"error": f"Verifier Error: {str(e)}"}

# --- Conditional Edge Logic ---

def should_loop(state: AgentState) -> str:
    """Determines whether to loop back to the designer or end."""
    print("--- Checking Verification ---")
    if state.error:
        print(f"Error occurred: {state.error}")
        return END # End on error
    if state.verification:
        if state.verification.action == "revise":
            print("Verification result: revise. Looping back to Designer.")
            # Reset downstream states for the loop
            state.design = None
            state.implementation = None
            state.test_report = None
            state.verification = None
            return "designer"
        else:
            print("Verification result: accept. Ending workflow.")
            return END
    print("Verification state not found. Ending.")
    return END

# --- Graph Creation ---

async def create_agent_graph(tools: list = [], checkpointer: Optional[BaseCheckpointSaver] = None):
    """Creates the multi-agent LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("planner", plan_step)
    workflow.add_node("designer", design_step)
    workflow.add_node("implementer", implement_step)

    # Add edges
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "designer")
    workflow.add_edge("designer", "implementer")
    workflow.add_edge("implementer", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app

# Note: Removed the old example usage (__main__ block, develop_app, stream_app_development)
# as main.py handles the invocation.
