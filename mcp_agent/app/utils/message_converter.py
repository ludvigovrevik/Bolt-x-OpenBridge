from typing import List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from ..models.artifact_models import ChatMessage
import logging

logger = logging.getLogger(__name__)

def convert_chat_messages_to_langchain(
    messages: List[ChatMessage], 
    include_images: bool = True,
    image_only_on_last: bool = True
) -> List[BaseMessage]:
    """
    Convert chat messages to LangChain BaseMessage format.
    
    Args:
        messages: List of ChatMessage objects
        include_images: Whether to include image data
        image_only_on_last: Only include images on the last message
    
    Returns:
        List of LangChain BaseMessage objects
    """
    langchain_messages: List[BaseMessage] = []
    num_messages = len(messages)
    
    for i, msg in enumerate(messages):
        is_last_message = (i == num_messages - 1)
        
        if msg.role == 'user':
            # Check if we should include image data
            should_include_image = (
                include_images and 
                msg.data and 
                msg.data.imageData and 
                (not image_only_on_last or is_last_message)
            )
            
            if should_include_image:
                message_content = [
                    {"type": "text", "text": msg.content},
                    {"type": "image_url", "image_url": {"url": msg.data.imageData}}
                ]
                langchain_messages.append(HumanMessage(content=message_content))
                logger.debug(f"Processed multimodal user message: {msg.content[:50]}... + Image")
            else:
                langchain_messages.append(HumanMessage(content=msg.content))
                
        elif msg.role == 'assistant':
            langchain_messages.append(AIMessage(content=msg.content))
    
    logger.info(f"Converted {len(messages)} messages to {len(langchain_messages)} LangChain messages")
    return langchain_messages

def convert_log_entries_to_messages(log_entries: List) -> List[BaseMessage]:
    """
    Convert log entries to LangChain HumanMessage format.
    
    Args:
        log_entries: List of LogEntry objects
    
    Returns:
        List of HumanMessage objects
    """
    messages = []
    
    for log in log_entries:
        formatted_error = f"""
        {log.command} | Success: {log.success} | Exit Code: {log.exitCode} |
        Stdout: {log.stdout} | Stderr: {log.stderr}
        """
        messages.append(HumanMessage(formatted_error))
    
    logger.info(f"Converted {len(log_entries)} log entries to messages")
    return messages

def combine_messages(*message_groups: List[BaseMessage]) -> List[BaseMessage]:
    """
    Combine multiple lists of messages into one.
    
    Args:
        *message_groups: Variable number of message lists
    
    Returns:
        Combined list of messages
    """
    combined = []
    for group in message_groups:
        if group:  # Only add non-empty groups
            combined.extend(group)
    
    logger.info(f"Combined {len(message_groups)} message groups into {len(combined)} total messages")
    return combined