# build_vectorstore.py
import os
import sys
import json
import pathlib
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

# Load environment
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("Error: OPENAI_API_KEY not set in environment.")
    sys.exit(1)

# Paths
script_dir = pathlib.Path(__file__).parent.resolve()
manifest_path = script_dir / "manifest.json"

if not manifest_path.exists():
    print(f"Manifest file not found at {manifest_path}")
    sys.exit(1)

# Load manifest
with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Collect raw documents
raw_docs = []
for module in manifest.get("modules", []):
    path = module.get("path")
    if not path:
        continue
    file_path = script_dir / path
    if not file_path.exists():
        # 1) Try resolving from project root 'src' folder
        repo_root = script_dir.parents[2]
        alt_path = repo_root / path
        if alt_path.exists():
            file_path = alt_path
        else:
            # 2) Fallback to node_modules/@oicl/openbridge-webcomponents
            alt_pkg = repo_root / "node_modules" / "@oicl" / "openbridge-webcomponents" / path
            if alt_pkg.exists():
                file_path = alt_pkg
            else:
                print(f"Skipping missing file: {file_path}")
                continue
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        continue
    raw_docs.append(Document(page_content=content, metadata={
        "path": str(file_path),
        "kind": module.get("kind", "")
    }))
print(f"Loaded {len(raw_docs)} documents from manifest.")

if not raw_docs:
    print("No documents to process. Exiting.")
    sys.exit(1)

# Split into chunks
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
docs = splitter.split_documents(raw_docs)
print(f"Split into {len(docs)} chunks.")

# Embed and build FAISS
embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
vector_store = FAISS.from_documents(docs, embeddings)

# Persist the index
output_dir = script_dir / "kb"
output_dir.mkdir(exist_ok=True)
vector_store.save_local(folder_path=str(output_dir), index_name="index")
print("✅ Rebuilt FAISS index with dimension:", vector_store.index.d)
