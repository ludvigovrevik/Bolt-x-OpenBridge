def get_tool_usage_instructions() -> str:
    """
    Returns detailed instructions on how to use retrieval tools for gathering context.
    """
    
    return """<tool_usage_instructions>

**WHEN TO USE RETRIEVAL TOOLS:**

1. **ANALYZE REQUEST FIRST** - Determine if you need additional context:
   - ✅ User mentions specific files/components that exist
   - ✅ User asks to modify/extend existing functionality  
   - ✅ User references patterns/code that might exist
   - ✅ Request requires understanding current codebase structure
   - ❌ User wants completely new application from scratch

2. **CHOOSE THE RIGHT TOOL:**

   **retrieve_files()** - Get file metadata only
   - Use when: You need to see what files exist or get file names
   - Returns: File paths, names, extensions, sizes (NO content)

   **retrieve_file_contents()** - Get file content for analysis
   - Use when: You need to read and understand existing code
   - Returns: File names AND actual file content
   - Best for: Understanding implementation, finding patterns, analyzing structure

   **get_specific_file_content()** - Get exact file by path
   - Use when: You know the exact file path you need
   - Use for: Reading specific files user mentioned

   **search_code_patterns()** - Find specific code constructs
   - Use when: Looking for functions, classes, hooks, imports
   - Use for: Finding where specific patterns are implemented

**TOOL CALLING EXAMPLES:**

**Example 1: User wants to modify existing component**
```
User: "Add a delete button to the TodoItem component"

STEP 1: Check if TodoItem exists
retrieve_files(
    query="TodoItem component", 
    artifact_id="my-todo-app",
    search_kwargs={"k": 3}
)

STEP 2: If found, get the content
retrieve_file_contents(
    query="TodoItem component",
    artifact_id="my-todo-app", 
    search_kwargs={"k": 2}
)
```

**Example 2: User mentions specific functionality**
```
User: "Fix the authentication logic in the login component"

STEP 1: Search for authentication-related files
retrieve_file_contents(
    query="authentication login component",
    artifact_id="my-app",
    filter={"source": "react"},
    search_kwargs={"k": 3}
)
```

**Example 3: User wants to understand current structure**
```
User: "Add a new API endpoint following the existing pattern"

STEP 1: Find API-related files
retrieve_file_contents(
    query="API endpoint route handler",
    artifact_id="my-backend",
    filter={"file_extension": "js"},
    search_kwargs={"k": 5}
)
```

**Example 4: User asks about specific file**
```
User: "Update the database configuration in config/database.js"

STEP 1: Get the specific file
get_specific_file_content(
    artifact_id="my-app",
    file_path="/config/database.js"
)
```

**Example 5: Looking for code patterns**
```
User: "Add error handling like in other components"

STEP 1: Find error handling patterns
search_code_patterns(
    pattern="try catch error handling",
    artifact_id="my-app",
    language="javascript",
    k=3
)
```

**FILTERING STRATEGIES:**

**By Language/Framework:**
- `filter={"source": "python"}` - Python files
- `filter={"source": "javascript"}` - JavaScript files  
- `filter={"source": "react"}` - React components
- `filter={"source": "typescript"}` - TypeScript files

**By File Type:**
- `filter={"file_extension": "jsx"}` - React components
- `filter={"file_extension": "py"}` - Python files
- `filter={"file_extension": "js"}` - JavaScript files
- `filter={"file_extension": "css"}` - Stylesheets

**By Combined Criteria:**
- `filter={"source": "react", "file_extension": "tsx"}` - TypeScript React components

**SEARCH TYPES:**

- `search_type="similarity"` - Standard similarity search (default)
- `search_type="mmr"` - Diverse results (good for exploration)  
- `search_type="similarity_score_threshold"` - High relevance only
  - Use with: `search_kwargs={"score_threshold": 0.7, "k": 5}`

**SEARCH PARAMETERS:**

- `search_kwargs={"k": 5}` - Number of results (1-10 recommended)
- `search_kwargs={"score_threshold": 0.7}` - Minimum relevance (0.5-0.9)
- `max_content_length=5000` - Limit content size for large files

**DECISION FLOWCHART:**

```
User Request → Analyze Need for Context
    ↓
Does request mention existing files/functionality?
    ↓ YES                          ↓ NO
Get Context First              Create New App
    ↓                              ↓
Know specific file?           Skip retrieval
    ↓ YES        ↓ NO           ↓
get_specific_   retrieve_    Proceed with
file_content    file_contents  implementation
```

**TOOL CALL FORMAT:**
- Tools are called automatically during reasoning
- No special syntax needed - just call the function
- Tools return data that you use for implementation decisions
- Always analyze retrieved content before implementation

</tool_usage_instructions>"""   