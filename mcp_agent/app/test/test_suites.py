# test_suites.py
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from .test_framework import create_test_case

# Define some sample test suites
BASE_SYSTEM_PROMPT = """You are an AI assistant that helps users with tasks.
Follow these formatting constraints:
1. Use markdown formatting for all responses
2. Start each response with a greeting
3. End each response with a question to engage the user
"""

UI_DESIGN_TEMPLATE = """I want you to act as a UI/UX designer. Please structure your responses as follows:
1. Summary of the design approach
2. Key design elements
3. Visual description
4. Interaction patterns"""

CODE_DESIGN_TEMPLATE = """I want you to act as a senior software engineer. Please structure your responses as follows:
1. Analysis of the problem
2. Solution architecture overview
3. Code implementation with comments
4. Testing considerations"""

# Test suite for basic agent functionality
BASIC_TEST_SUITE = [
    create_test_case(
        name="Basic greeting test",
        input_message="Hello there",
        model_responses=[
            {"content": "# Hi there!\n\nIt's nice to meet you. How can I assist you today?"}
        ],
        system_prompt=BASE_SYSTEM_PROMPT,
        validation={
            "expected_messages": 2,
            "contains_content": "# Hi there"
        }
    ),
    create_test_case(
        name="Tool usage test",
        input_message="What files are in my directory?",
        model_responses=[
            {
                "content": "I'll check your files",
                "tool_calls": [
                    {
                        "name": "list_directory",
                        "args": {"path": "."}
                    }
                ]
            },
            {"content": "# Here are your files\n\nI found these files in your directory:\n- test.py\n- graph.py\n\nDo you want to examine any of these files?"}
        ],
        system_prompt=BASE_SYSTEM_PROMPT,
        validation={
            "expected_tool_calls": ["list_directory"],
            "contains_content": "Here are your files"
        }
    )
]

# Test suite for UI design template
UI_DESIGNER_TEST_SUITE = [
    create_test_case(
        name="UI design request",
        input_message="Design a mobile app home screen for a fitness tracking app",
        model_responses=[
            {"content": """# Fitness App Home Screen Design

1. **Summary of the design approach**
   - Creating a user-centered fitness tracking interface that prioritizes daily goals and activity metrics
   - Using a clean, motivational design with high contrast for glanceability 

2. **Key design elements**
   - Progress ring showing daily goal completion
   - Activity card carousel for quick metric viewing
   - Bottom navigation with 4 core sections
   - Personalized greeting with motivational message

3. **Visual description**
   - Color scheme: Primary blue (#3B82F6) with energetic accent colors
   - Typography: Sans-serif for readability, bold headers for emphasis
   - Iconography: Rounded, simple icons with consistent padding
   - Layout: Card-based design with clear visual hierarchy

4. **Interaction patterns**
   - Swipeable cards for different activity metrics
   - Pull-to-refresh for latest sync
   - Tap actions for expanding data cards
   - Long-press for quick actions

Would you like me to elaborate on any specific aspect of this design?"""}
        ],
        system_prompt=BASE_SYSTEM_PROMPT,
        design_template=UI_DESIGN_TEMPLATE,
        validation={
            "expected_messages": 2,
            "contains_content": "Summary of the design approach"
        }
    )
]

# Test suite for code implementation template
CODE_ENGINEER_TEST_SUITE = [
    create_test_case(
        name="Code implementation request",
        input_message="Write a function to find the longest palindrome in a string",
        model_responses=[
            {"content": """# Palindrome Function Implementation

1. **Analysis of the problem**
   - Need to find the longest palindrome substring in a given string
   - Naive approach would check all substrings (O(n³) complexity)
   - We'll use Manacher's algorithm for O(n) complexity
   - Edge cases: empty strings, single characters, all unique characters

2. **Solution architecture overview**
   - Preprocess string to handle even-length palindromes
   - Use dynamic programming to expand around centers
   - Track longest palindrome found
   - Return the longest palindrome substring

3. **Code implementation with comments**

```python
def longest_palindrome(s: str) -> str:
    '''
    Find the longest palindromic substring in a given string using Manacher's algorithm.
    
    Args:
        s: Input string
        
    Returns:
        Longest palindromic substring
    '''
    if not s or len(s) < 2:
        return s
        
    # Preprocess the string to handle even length palindromes
    # Insert '#' between each character and at boundaries
    processed = '#' + '#'.join(s) + '#'
    n = len(processed)
    
    # p[i] stores the length of palindrome centered at i
    p = [0] * n
    
    # Variables to track center and right boundary of current palindrome
    center = 0
    right = 0
    
    # Variables to track the longest palindrome
    max_len = 0
    max_center = 0
    
    for i in range(n):
        # Mirror of current position
        mirror = 2 * center - i
        
        # If within right boundary, take advantage of mirror property
        if i < right:
            p[i] = min(right - i, p[mirror])
        
        # Expand around center i
        while (i + 1 + p[i] < n and 
               i - 1 - p[i] >= 0 and 
               processed[i + 1 + p[i]] == processed[i - 1 - p[i]]):
            p[i] += 1
        
        # Update center and right boundary if needed
        if i + p[i] > right:
            center = i
            right = i + p[i]
        
        # Update longest palindrome if needed
        if p[i] > max_len:
            max_len = p[i]
            max_center = i
    
    # Calculate start index in original string
    start = (max_center - max_len) // 2
    
    # Return the longest palindrome
    return s[start:start + max_len]
```

4. **Testing considerations**
   - Test with empty strings: should return empty string
   - Test with single character: should return that character
   - Test with all same characters: should return the entire string
   - Test with even-length palindromes: "abba"
   - Test with odd-length palindromes: "racecar"
   - Test with multiple palindromes: pick the longest one
   - Test with very long strings for performance
   - Test with Unicode characters to ensure proper handling

Would you like me to provide test cases for this function?"""}
        ],
        system_prompt=BASE_SYSTEM_PROMPT,
        design_template=CODE_DESIGN_TEMPLATE,
        validation={
            "expected_messages": 2,
            "contains_content": "Analysis of the problem"
        }
    )
]

# Export all test suites
TEST_SUITES = {
    "basic": BASIC_TEST_SUITE,
    "ui_designer": UI_DESIGNER_TEST_SUITE,
    "code_engineer": CODE_ENGINEER_TEST_SUITE
}