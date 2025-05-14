from typing import Optional, List, Dict, Any, Generator
import re

class StreamingXmlProcessor:
    """
    Process streaming XML-like content with boltArtifact and boltAction tags.
    
    This processor handles content in the format:
    <boltArtifact id="..." title="...">
        <boltAction type="..." ...>...</boltAction>
        ...
    </boltArtifact>
    """
    
    def __init__(self):
        self.buffer = ""
        self.artifact_stack = []  # Track nested artifacts
        self.current_artifact_id = None
        self.current_artifact_title = None
    
    def feed(self, chunk: str) -> Generator[str, None, None]:
        """
        Process a chunk of XML-like content and yield formatted output.
        
        Args:
            chunk: A string chunk from the stream
            
        Yields:
            Properly formatted XML segments
        """
        # Add the new chunk to our buffer
        self.buffer += chunk
        
        # Process the buffer until we can't make further progress
        while True:
            if self.artifact_stack:
                # Inside an artifact - look for closing tag
                close_pos = self.buffer.find("</boltArtifact>")
                if close_pos != -1:
                    # Found closing tag - yield content up to close tag
                    artifact_content = self.buffer[:close_pos]
                    if artifact_content:
                        yield artifact_content

                    # Emit closing tag
                    yield '</boltArtifact>'

                    # Update state
                    self.artifact_stack.pop()
                    self.buffer = self.buffer[close_pos + len("</boltArtifact>"):]
                    
                    # Reset artifact info if we've exited all artifacts
                    if not self.artifact_stack:
                        self.current_artifact_id = None
                        self.current_artifact_title = None
                else:
                    # No closing tag yet - wait for more data
                    break
            else:
                # Outside artifact - look for opening tag
                open_pos = self.buffer.find("<boltArtifact")
                if open_pos == -1:
                    # No artifact tag found - yield text if needed
                    if self.buffer:
                        yield self.buffer
                        self.buffer = ""
                    break
                
                # Found opening tag - yield text before it
                if open_pos > 0:
                    yield self.buffer[:open_pos]
                
                # Find end of opening tag
                tag_end_pos = self.buffer.find(">", open_pos)
                if tag_end_pos == -1:
                    # Incomplete tag - wait for more data
                    if open_pos > 0:
                        self.buffer = self.buffer[open_pos:]
                    break
                
                # Extract artifact ID and title
                tag_content = self.buffer[open_pos:tag_end_pos+1]
                self.extract_artifact_info(tag_content)
                
                # Yield the complete opening tag
                yield tag_content
                
                # Update state
                self.artifact_stack.append(True)
                self.buffer = self.buffer[tag_end_pos+1:]

    def extract_artifact_info(self, tag_content: str) -> None:
        """Extract ID and title from a boltArtifact tag."""
        # Extract id
        id_match = re.search(r'id=["\'](.*?)["\']', tag_content)
        if id_match:
            self.current_artifact_id = id_match.group(1)
        
        # Extract title
        title_match = re.search(r'title=["\'](.*?)["\']', tag_content)
        if title_match:
            self.current_artifact_title = title_match.group(1)
            
    @property
    def artifact_info(self) -> Optional[Dict[str, str]]:
        """Get the current artifact information."""
        if self.current_artifact_id or self.current_artifact_title:
            return {
                "id": self.current_artifact_id,
                "title": self.current_artifact_title
            }
        return None