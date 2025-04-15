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