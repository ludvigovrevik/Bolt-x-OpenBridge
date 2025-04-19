import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA


# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize embeddings
embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

# Load existing vector store
vector_store = FAISS.load_local(
    folder_path="kb",
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
    search_kwargs={"k": 3}
)

# Simple test query
test_query = "What is RAG?"

# Build a QA chain using the new RetrievalQA facade
qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(temperature=0, openai_api_key=openai_api_key),
    chain_type="stuff",
    retriever=retriever,
)

# Execute the QA chain using invoke instead of the deprecated run()
response = qa_chain.invoke({"query": test_query})
answer = response["result"]

# Display output
print(f"Test query: {test_query}")
print(f"Answer: {answer}")
