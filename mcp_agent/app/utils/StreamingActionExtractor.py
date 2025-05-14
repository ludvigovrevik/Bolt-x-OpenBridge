import json
from typing import List, Dict, Optional, Set, Tuple, Any

class StreamingJsonParser:
    """Base class for parsing JSON objects from streaming content."""
    
    def __init__(self):
        self.buffer = ""
        self.in_string = False
        self.escape = False
        self.starts: List[int] = []
        
    def feed(self, chunk: str) -> List[Dict]:
        """Feed a fragment and return any newly complete JSON objects."""
        self.buffer += chunk
        found = []

        for i, c in enumerate(self.buffer):
            if self.escape:
                self.escape = False
            elif c == "\\" and self.in_string:
                self.escape = True
            elif c == '"':
                self.in_string = not self.in_string
            elif not self.in_string:
                if c == "{":
                    self.starts.append(i)
                elif c == "}" and self.starts:
                    start = self.starts.pop()
                    candidate = self.buffer[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        found.append(obj)
                    except json.JSONDecodeError:
                        continue

        # trim buffer to the earliest unmatched '{'
        if self.starts:
            min_start = min(self.starts)
            self.buffer = self.buffer[min_start:]
            self.starts = [s - min_start for s in self.starts]
        else:
            self.buffer = ""

        return found


class StreamingActionExtractor:
    """Extracts specific action objects from a JSON stream."""
    
    def __init__(self):
        self.parser = StreamingJsonParser()
        self.seen: Set[Tuple] = set()
        self.artifact_info: Optional[Dict] = None
        
    def feed(self, chunk: str) -> List[Dict]:
        """Feed a fragment and return any newly complete action objects."""
        all_objects = self.parser.feed(chunk)
        found = []
        
        for obj in all_objects:
            # capture the first artifact metadata
            if obj.get("type") == "artifact" and self.artifact_info is None:
                self.artifact_info = {
                    "id": obj.get("id"),
                    "title": obj.get("title")
                }

            # collect only action objects
            if obj.get("type") in ("shell", "file", "message"):
                key = (
                    obj["type"],
                    obj.get("step_number"),
                    obj.get("command") or obj.get("file_path") or obj.get("content", "")[:30]
                )
                if key not in self.seen:
                    self.seen.add(key)
                    found.append(obj)
                    
        return found