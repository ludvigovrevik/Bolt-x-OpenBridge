

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
    
    # Generate the implementation plan
    plan_result = await llm.ainvoke({"prompt": planning_prompt})
    
    # Create a structured plan
    implementation_steps = plan_result.strip().split("\n")
    
    return {
        "implementation_plan": implementation_steps,
        "messages": [SystemMessage(content=f"Implementation plan created with {len(implementation_steps)} steps.")]
    }