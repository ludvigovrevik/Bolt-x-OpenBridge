# minimal example – replace with your own embedding/model keys
import sys, pathlib, faiss, json, pickle
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
script_dir = pathlib.Path(__file__).parent.absolute()
docs_dir = script_dir / "kb"  # Use fixed relative path to knowledge base
manifest_path = script_dir / "kb/manifest_min.json"  # Use existing manifest

if not docs_dir.exists():
    print(f"Document directory {docs_dir} not found")
    sys.exit(1)

# Load file paths from manifest.json
with open(manifest_path, 'r') as f:
    manifest = json.load(f)

embeds, meta, texts = [], [], []
for module in manifest.get("modules", []):
    if "path" not in module:
        print(f"Skipping module without path: {module}")
        continue
        
    file_path = pathlib.Path(module["path"])
    if not file_path.is_absolute():
        file_path = docs_dir / file_path

    if not file_path.exists():
        print(f"File not found: {file_path}")
        continue

    try:
        txt = file_path.read_text(encoding="utf-8")[:4000]
        embeds.append(model.encode(txt))
        meta.append({"path": str(file_path), "module_type": module.get("kind", "unknown")})
        texts.append(txt)
        print(f"Processed: {file_path}")
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")

if not embeds:
    print("No files found to embed. Exiting.")
    sys.exit(1)

index = faiss.IndexFlatL2(len(embeds[0]))
index.add(np.array(embeds).astype("float32"))
faiss.write_index(index, str(docs_dir / "index.faiss"))
json.dump(meta, open(docs_dir / "index_meta.json", "w"))

# Save the required pickle file for LangChain FAISS loader
with open(docs_dir / "index.pkl", "wb") as f:
    pickle.dump((texts, meta), f)

print("vector store ready")
