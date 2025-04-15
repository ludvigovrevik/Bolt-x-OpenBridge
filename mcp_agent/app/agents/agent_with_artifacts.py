

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
        cwd=config.get("cwd", "."),
        tools=config.get("tools", [])
    )
    
    # Combine all context into a single message
    full_context = [
        SystemMessage(content=f"{artifact_prompt}\n\n{design_context}"),
        *state.messages
    ]
    
    # Call the model with the artifact-focused prompt
    artifact_result = await llm.ainvoke(full_context)
    
    # Return the result which should contain the boltArtifact structures
    return {"agent_outcome": artifact_result}