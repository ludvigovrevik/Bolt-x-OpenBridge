# minimal example – replace with your own embedding/model keys
import sys, pathlib, faiss, json, pickle
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
docs_dir = pathlib.Path(sys.argv[1])
embeds, meta, texts = [], [], []
for p in list(docs_dir.rglob("*.md")) + list(docs_dir.rglob("*.ts")) + list(docs_dir.rglob("*.html")):
    txt = p.read_text()[:4000]
    embeds.append(model.encode(txt))
    meta.append({"path": str(p)})
    texts.append(txt)

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
