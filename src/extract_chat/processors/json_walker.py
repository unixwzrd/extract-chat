"""
JSON Walker for examining conversation structure.

This module walks through the actual JSON structure without making assumptions
about what fields exist or what constitutes turn content.
"""

import logging
from typing import Any, Dict


class JSONWalker:
    """Walks through JSON structure to understand actual content."""
    
    def __init__(self):
        """Initialize the JSON walker."""
        self.visited_paths = set()
        self.field_types = {}
        self.field_values = {}
    
    def walk_conversation(self, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Walk through the entire conversation structure.
        
        Args:
            conversation_data: The raw conversation JSON data
            
        Returns:
            Analysis of the conversation structure
        """
        logging.getLogger(__name__).debug("Starting JSON walk of conversation structure")
        
        # Reset state
        self.visited_paths = set()
        self.field_types = {}
        self.field_values = {}
        
        # Walk the root level
        root_analysis = self._walk_object(conversation_data, "root")
        
        # Walk the mapping structure specifically
        if "mapping" in conversation_data:
            logging.getLogger(__name__).debug("Found mapping structure, walking turns...")
            mapping_analysis = self._walk_mapping(conversation_data["mapping"])
        else:
            mapping_analysis = {"error": "No mapping found"}
        
        return {
            "root_structure": root_analysis,
            "mapping_structure": mapping_analysis,
            "field_types": self.field_types,
            "field_values": self.field_values
        }
    
    def _walk_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """
        Walk through the mapping structure to understand turn content.
        
        Args:
            mapping: The mapping dictionary
            
        Returns:
            Analysis of the mapping structure
        """
        turn_analyses = {}
        
        for turn_id, turn_data in mapping.items():
            logging.getLogger(__name__).debug("Walking turn %s", turn_id)
            turn_analysis = self._walk_turn(turn_id, turn_data)
            turn_analyses[turn_id] = turn_analysis
        
        return {
            "total_turns": len(mapping),
            "turn_analyses": turn_analyses
        }
    
    def _walk_turn(self, turn_id: str, turn_data: Any) -> Dict[str, Any]:
        """
        Walk through a single turn to understand its complete structure.
        
        Args:
            turn_id: The turn ID
            turn_data: The turn data
            
        Returns:
            Analysis of the turn structure
        """
        logging.getLogger(__name__).debug("Analyzing turn %s structure", turn_id)
        
        turn_analysis = {
            "turn_id": turn_id,
            "fields": {},
            "message_analysis": None,
            "relationships": {},
            "metadata": {}
        }
        
        # Walk all fields in the turn
        if isinstance(turn_data, dict):
            for field_name, field_value in turn_data.items():
                field_path = f"turn.{turn_id}.{field_name}"
                field_analysis = self._walk_field(field_path, field_value)
                turn_analysis["fields"][field_name] = field_analysis
                
                # Special handling for different field types
                if field_name == "message":
                    turn_analysis["message_analysis"] = self._walk_message(field_path, field_value)
                elif field_name in ["parent", "children"]:
                    turn_analysis["relationships"][field_name] = field_analysis
                else:
                    turn_analysis["metadata"][field_name] = field_analysis
        else:
            # Handle non-dict turn data
            turn_analysis["fields"]["data"] = self._walk_field(f"turn.{turn_id}.data", turn_data)
        
        return turn_analysis
    
    def _walk_message(self, message_path: str, message_data: Any) -> Dict[str, Any]:
        """
        Walk through a message to understand its complete structure.
        
        Args:
            message_path: The path to this message
            message_data: The message data
            
        Returns:
            Analysis of the message structure
        """
        if not message_data:
            return {"type": "null", "content": None}
        
        message_analysis = {
            "message_path": message_path,
            "fields": {},
            "author_analysis": None,
            "content_analysis": None,
            "metadata_analysis": None
        }
        
        if isinstance(message_data, dict):
            for field_name, field_value in message_data.items():
                field_path = f"{message_path}.{field_name}"
                field_analysis = self._walk_field(field_path, field_value)
                message_analysis["fields"][field_name] = field_analysis
                
                # Special handling for different field types
                if field_name == "author":
                    message_analysis["author_analysis"] = self._walk_author(field_path, field_value)
                elif field_name == "content":
                    message_analysis["content_analysis"] = self._walk_content(field_path, field_value)
                elif field_name == "metadata":
                    message_analysis["metadata_analysis"] = self._walk_metadata(field_path, field_value)
        
        return message_analysis
    
    def _walk_author(self, author_path: str, author_data: Any) -> Dict[str, Any]:
        """
        Walk through author information.
        
        Args:
            author_path: The path to this author
            author_data: The author data
            
        Returns:
            Analysis of the author structure
        """
        if not author_data:
            return {"type": "null", "content": None}
        
        author_analysis = {
            "author_path": author_path,
            "fields": {},
            "metadata_analysis": None
        }
        
        if isinstance(author_data, dict):
            for field_name, field_value in author_data.items():
                field_path = f"{author_path}.{field_name}"
                field_analysis = self._walk_field(field_path, field_value)
                author_analysis["fields"][field_name] = field_analysis
                
                if field_name == "metadata":
                    author_analysis["metadata_analysis"] = self._walk_metadata(field_path, field_value)
        
        return author_analysis
    
    def _walk_content(self, content_path: str, content_data: Any) -> Dict[str, Any]:
        """
        Walk through content information.
        
        Args:
            content_path: The path to this content
            content_data: The content data
            
        Returns:
            Analysis of the content structure
        """
        if not content_data:
            return {"type": "null", "content": None}
        
        content_analysis = {
            "content_path": content_path,
            "fields": {},
            "all_content_fields": []
        }
        
        if isinstance(content_data, dict):
            for field_name, field_value in content_data.items():
                field_path = f"{content_path}.{field_name}"
                field_analysis = self._walk_field(field_path, field_value)
                content_analysis["fields"][field_name] = field_analysis
                content_analysis["all_content_fields"].append(field_name)
        
        return content_analysis
    
    def _walk_metadata(self, metadata_path: str, metadata_data: Any) -> Dict[str, Any]:
        """
        Walk through metadata information.
        
        Args:
            metadata_path: The path to this metadata
            metadata_data: The metadata data
            
        Returns:
            Analysis of the metadata structure
        """
        if not metadata_data:
            return {"type": "null", "content": None}
        
        metadata_analysis = {
            "metadata_path": metadata_path,
            "fields": {},
            "all_metadata_fields": []
        }
        
        if isinstance(metadata_data, dict):
            for field_name, field_value in metadata_data.items():
                field_path = f"{metadata_path}.{field_name}"
                field_analysis = self._walk_field(field_path, field_value)
                metadata_analysis["fields"][field_name] = field_analysis
                metadata_analysis["all_metadata_fields"].append(field_name)
        
        return metadata_analysis
    
    def _walk_field(self, field_path: str, field_value: Any) -> Dict[str, Any]:
        """
        Walk through a single field to understand its type and content.
        
        Args:
            field_path: The path to this field
            field_value: The field value
            
        Returns:
            Analysis of the field
        """
        if field_path in self.visited_paths:
            return {"type": "visited", "path": field_path}
        
        self.visited_paths.add(field_path)
        
        field_type = type(field_value).__name__
        self.field_types[field_path] = field_type
        
        field_analysis = {
            "path": field_path,
            "type": field_type,
            "value": field_value
        }
        
        # Store sample values for analysis
        if field_path not in self.field_values:
            self.field_values[field_path] = []
        
        if len(self.field_values[field_path]) < 5:  # Keep up to 5 samples
            self.field_values[field_path].append(str(field_value)[:100])  # Truncate long values
        
        # Recursively walk complex types
        if isinstance(field_value, dict):
            field_analysis["subfields"] = {}
            for subfield_name, subfield_value in field_value.items():
                subfield_path = f"{field_path}.{subfield_name}"
                field_analysis["subfields"][subfield_name] = self._walk_field(subfield_path, subfield_value)
        elif isinstance(field_value, list):
            field_analysis["list_items"] = []
            for i, item in enumerate(field_value[:3]):  # Only examine first 3 items
                item_path = f"{field_path}[{i}]"
                field_analysis["list_items"].append(self._walk_field(item_path, item))
        
        return field_analysis
    
    def _walk_object(self, obj: Any, path: str) -> Dict[str, Any]:
        """
        Walk through any object structure.
        
        Args:
            obj: The object to walk
            path: The path to this object
            
        Returns:
            Analysis of the object
        """
        if isinstance(obj, dict):
            analysis = {"type": "dict", "fields": {}}
            for key, value in obj.items():
                field_path = f"{path}.{key}"
                analysis["fields"][key] = self._walk_field(field_path, value)
            return analysis
        elif isinstance(obj, list):
            analysis = {"type": "list", "items": []}
            for i, item in enumerate(obj[:3]):  # Only examine first 3 items
                item_path = f"{path}[{i}]"
                analysis["items"].append(self._walk_field(item_path, item))
            return analysis
        else:
            return self._walk_field(path, obj) 
