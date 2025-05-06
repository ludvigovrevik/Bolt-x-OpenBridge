import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain import hub
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize embeddings
embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

# Load existing vector store
vector_store = FAISS.load_local(
    folder_path=str(BASE_DIR / "kb"),
    embeddings=embeddings,
    index_name="index",
    allow_dangerous_deserialization=True
)
# Debug: verify embedding vs index dimensions
print(f"FAISS index dimension: {vector_store.index.d}")
test_emb = embeddings.embed_query("test query")
print(f"Embedding dimension: {len(test_emb)}")
if vector_store.index.d != len(test_emb):
    raise ValueError(
        f"Dimension mismatch: FAISS index dimension {vector_store.index.d} != embedding dimension {len(test_emb)}. "
        "Please rebuild your index with the same embedding model."
    )

# Create retriever with basic configuration
retriever = vector_store.as_retriever(
    search_kwargs={"k": 5}
)

# Simple test query
test_query = """
 You are a coding assistant. Produce a JSON object describing the “azimuth thuster” component with exactly these keys:
1. name: the class or tag name
2. description: one‑sentence summary
3. properties: an array of { name, type, default }
4. example: a minimal code snippet showing basic usage


Respond with valid JSON only—no extra text.
"""

# Build a retrieval-augmented generation (RAG) chain
retrieval_qa_chat_prompt = hub.pull("langchain-ai/retrieval-qa-chat")
stuff_chain = create_stuff_documents_chain(
    ChatOpenAI(temperature=0, openai_api_key=openai_api_key),
    retrieval_qa_chat_prompt
)
rag_chain = create_retrieval_chain(
    retriever=retriever,
    combine_docs_chain=stuff_chain
)
from langchain.tools import Tool

def retrieve_component_info(component_name: str) -> str:
    """
    Retrieve JSON description for the given web component.
    """
    # build a dynamic query using the provided component name
    query = f"""
    You are a coding assistant. Produce a JSON object describing the “{component_name}” component with exactly these keys:
    1. name: the class or tag name
    2. description: one‑sentence summary
    3. properties: an array of {{ name, type, default }}
    4. example: a minimal code snippet showing basic usage
    
    Respond with valid JSON only—no extra text.
    """
    response = rag_chain.invoke({"input": query})
    return response["answer"]

component_info_tool = Tool(
    name="retrieve_component_info",
    func=retrieve_component_info,
    description="Retrieves a JSON description of a specified web component"
)

# Execute the RAG chain
response = rag_chain.invoke({"input": test_query})
answer = response["answer"]

# Display output
print(f"Test query: {test_query}")
print(f"Answer: {answer}")

if __name__ == "__main__":
   # smoke‑test your new tool
    comp = "azimuth thuster"
    print(">>> retrieve_component_info output:")
    print(retrieve_component_info(comp))