import random
import asyncio
from typing import Dict, Any, AsyncGenerator, List, Optional
from langchain_core.messages import BaseMessage, AIMessageChunk, AIMessage

class MockStreamingLLM:
    """Mock LLM that simulates token-by-token streaming in the format observed from OpenAI."""
    
    def __init__(self):
        # Sample response content - you can replace this with any sample response
        self.sample_response = '''<boltArtifact id="react-todo-tailwind" title="React Todo App with Tailwind CSS">\n  
        <boltAction type="file" filePath="package.json">\n{\n  "name": "react-todo-tailwind",\n  "version": "1.0.0",\n  "scripts": {\n    "dev": "vite"\n  },\n  "dependencies": {\n    "react": "^18.0.0",\n    "react-dom": "^18.0.0"\n  },\n  "devDependencies": {\n    "vite": "^4.0.0"\n  }\n}\n  </boltAction>\n\n  
        <boltAction type="shell">\n    npm install --yes\n  </boltAction>\n\n  
        <boltAction type="file" filePath="index.html">\n<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n  <title>React Todo App</title>\n  <script type="module" src="/main.jsx"></script>\n</head>\n<body class="bg-[var(--container-background-color)] min-h-screen flex items-center justify-center p-4">\n</body>\n</html>\n  </boltAction>\n\n  
        <boltAction type="file" filePath="main.jsx">\nimport React, { useState } from \'react\';\n\nfunction App() {\n  const [todos, setTodos] = useState([]);\n  const [newTodo, setNewTodo] = useState(\'\');\n\n  const addTodo = () => {\n    if (newTodo.trim() !== \'\') {\n      setTodos([...todos, { text: newTodo, completed: false }]);\n      setNewTodo(\'\');\n    }\n  };\n\n  const toggleComplete = (index) => {\n    const updatedTodos = [...todos];\n    updatedTodos[index].completed = !updatedTodos[index].completed;\n    setTodos(updatedTodos);\n  };\n\n  const deleteTodo = (index) => {\n    const updatedTodos = [...todos];\n    updatedTodos.splice(index, 1);\n    setTodos(updatedTodos);\n  };\n\n  return (\n    <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">\n      <h1 className="text-2xl font-bold mb-4 text-center">Todo List</h1>\n      <div className="flex mb-4">\n        <input\n          type="text"\n          className="flex-1 border border-gray-300 rounded-l px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"\n          placeholder="Add a new task..."\n          value={newTodo}\n          onChange={(e) => setNewTodo(e.target.value)}\n          onKeyDown={(e) => e.key === \'Enter\' && addTodo()}\n        />\n        <button\n          className="bg-blue-500 text-white px-4 py-2 rounded-r hover:bg-blue-600"\n          onClick={addTodo}\n        >\n          Add\n        </button>\n      </div>\n      <ul className="space-y-2">\n        {todos.map((todo, index) => (\n          <li\n            key={index}\n            className={`flex items-center justify-between p-2 border border-gray-200 rounded ${\n              todo.completed ? \'bg-green-100 line-through text-gray-500\' : \'\'\n            }`}\n          >\n            <div className="flex items-center space-x-2">\n              <input\n                type="checkbox"\n                checked={todo.completed}\n                onChange={() => toggleComplete(index)}\n                className="form-checkbox h-4 w-4 text-blue-600"\n              />\n              <span>{todo.text}</span>\n            </div>\n            <button\n              className="text-red-500 hover:text-red-700"\n              onClick={() => deleteTodo(index)}\n            >\n              Delete\n            </button>\n          </li>\n        ))}\n      </ul>\n    </div>\n  );\n}\n\nexport default App;\n  </boltAction>\n\n  
        <boltAction type="file" filePath="vite.config.js">\nimport { defineConfig } from \'vite\';\nimport react from \'@vitejs/plugin-react\';\n\nexport default defineConfig({\n  plugins: [react()],\n});\n  </boltAction>\n\n  
        <boltAction type="shell">\n    npm install --save-dev @vitejs/plugin-react\n  </boltAction>\n\n  
        <boltAction type="shell">\n    npm run dev\n  </boltAction>\n</boltArtifact>'''

    async def ainvoke(
        self, input: List[BaseMessage], **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream events in the format expected by the agent."""
        # First, yield plan events (optional - simulates agent planning)

        # Just return the full artifact as a single message (not a stream)
        return AIMessage(content=self.sample_response)
    
    def _fragment_response(self):
        """Break the sample response into small fragments similar to real streaming."""
        # Current position in the response
        pos = 0
        response_len = len(self.sample_response)
        
        while pos < response_len:
            # Determine fragment size - bias toward very small fragments
            # This mimics the example where tokens are often just 1-3 chars
            if random.random() < 0.7:  # 70% chance for tiny fragment
                size = random.randint(1, 3)
            elif random.random() < 0.9:  # 20% chance for small fragment
                size = random.randint(4, 10)
            else:  # 10% chance for larger fragment
                size = random.randint(11, 20)
                
            # Extract fragment
            end = min(pos + size, response_len)
            fragment = self.sample_response[pos:end]
            
            # Special handling for tags - try to keep tags intact
            if '<' in fragment and '>' not in fragment:
                # Find the next closing bracket
                next_bracket = self.sample_response.find('>', pos)
                if next_bracket != -1:
                    fragment = self.sample_response[pos:next_bracket+1]
                    end = next_bracket + 1
            
            yield fragment
            pos = end

    def bind_values(self, **kwargs):
        """Mock bind_values method to match ChatOpenAI interface."""
        return self