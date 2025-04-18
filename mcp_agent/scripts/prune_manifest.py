import json, sys, pathlib
src = pathlib.Path(sys.argv[1])  # big manifest path
dst = pathlib.Path("kb/manifest_min.json")
data = json.loads(src.read_text())
data["modules"] = [
    m for m in data["modules"]
    if any(e["kind"] == "custom-element-definition" for e in m.get("exports", []))
    and not m["path"].startswith("src/icons/")
]
dst.write_text(json.dumps(data, indent=2))
print(f"wrote {dst}")
