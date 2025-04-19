from pydantic import BaseModel, Field
from ..utils import make_structured_prompt
import json
from pathlib import Path
prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

# Compute path to the 'kb' directory at the project root
kb_path = Path(__file__).resolve().parents[2] / "kb"

# Load embeddings and vector store
embeddings = OpenAIEmbeddings()  # adjust to your embedding model
vectorstore = FAISS.load_local(
    kb_path,
    embeddings,
    allow_dangerous_deserialization=True
)
retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5})

# Load and summarize the manifest for context
manifest_path = kb_path / "manifest_min.json"
try:
    raw_manifest = json.loads(manifest_path.read_text())
except Exception:
    raw_manifest = {}
manifest_entries = []
for module in raw_manifest.get("modules", []):
    for exp in module.get("exports", []):
        if exp.get("kind") == "custom-element-definition":
            name = exp["declaration"].get("name", "")
            props = [d["name"] for d in module.get("declarations", [])]
            slots = [
                d["name"] for d in module.get("declarations", [])
                if d.get("kind") == "slot"
            ]
            manifest_entries.append(f"{name}: props={props}, slots={slots}")
manifest_doc = Document(
    page_content="Component Registry:\n" + "\n".join(manifest_entries),
    metadata={"source": "manifest"}
)

class Wireframe(BaseModel):
    """
    For each page: an ordered list of OpenBridge component tag names
    with optional layout hints.
    """
    pages: list[dict] = Field(
        description="List of pages mapped to component tag names and layout hints"
    )

# Load modular prompt components
with open(prompts_dir / 'system_constraints.md') as f:
    system_constraints = f.read()
with open(prompts_dir / 'openbridge_defaults.md') as f:
    component_defaults = f.read()
with open(prompts_dir / 'formatting_info.md') as f:
    formatting_rules = f.read()

system_prompt = f"""{system_constraints}

{component_defaults}

{formatting_rules}

Map each page description to OpenBridge web component tag names. 
Use ONLY tags in the manifest.
Output strictly valid JSON matching the Wireframe schema."""

designer_prompt, (designer_parser, _) = make_structured_prompt(
    Wireframe,
    system_prompt
)

def designer_context(messages, **_):
    """
    Retrieve relevant usage snippets and prepend the manifest registry.
    """
    query = messages[-1].content
    docs = retriever.get_relevant_documents(query)
    return [manifest_doc] + docs