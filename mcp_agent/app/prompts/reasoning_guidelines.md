# Reasoning & Planning Process

## Implementation Workflow
```mermaid
graph TD
    A[Analyze Inputs] --> B[Synthesize Requirements]
    B --> C[Identify OpenBridge Components]
    C --> D[Plan Structure]
    D --> E[Pre-Computations]
    E --> F[Output Plan]
    F --> G[Emit Files/Actions]
    
    style A fill:#e1f5fe,stroke:#039be5
    style B fill:#f0f4c3,stroke:#afb42b
    style C fill:#ffcdd2,stroke:#e53935
    style F fill:#c8e6c9,stroke:#43a047
```

## Required Planning Steps
1. **Visual Analysis** - Examine all visual references first
2. **Component Mapping** - Match UI elements to OpenBridge web components
3. **Dependency Graph** - Create import hierarchy for required modules
4. **Theme Strategy** - Plan palette handling and CSS variable usage
5. **Error Boundaries** - Identify potential compatibility issues
6. **Output Validation** - Verify against WebContainer constraints
