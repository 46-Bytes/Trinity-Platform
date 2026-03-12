"""
File loading utilities for prompts and data files
"""
import json
from pathlib import Path
from typing import Dict, Any
from functools import lru_cache


class FileLoader:
    """Utility class for loading prompts and data files"""
    
    BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend directory
    FILES_DIR = BASE_DIR / "files"
    PROMPTS_DIR = FILES_DIR / "prompts"
    
    @classmethod
    @lru_cache(maxsize=32)
    def load_json(cls, filename: str) -> Dict[str, Any]:
        """
        Load a JSON file from the files directory.
        
        Args:
            filename: Name of the JSON file (with or without .json extension)
            
        Returns:
            Dictionary containing the parsed JSON data
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file is not valid JSON
        """
        if not filename.endswith('.json'):
            filename = f"{filename}.json"
        
        file_path = cls.FILES_DIR / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"JSON file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    @lru_cache(maxsize=32)
    def load_prompt(cls, prompt_name: str) -> str:
        """
        Load a prompt file from the prompts directory.
        
        Args:
            prompt_name: Name of the prompt file (with or without .md extension)
            
        Returns:
            String containing the prompt text
            
        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        if not prompt_name.endswith('.md'):
            prompt_name = f"{prompt_name}.md"
        
        file_path = cls.PROMPTS_DIR / prompt_name
        
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @classmethod
    def load_diagnostic_questions(cls) -> Dict[str, Any]:
        """Load the diagnostic survey questions"""
        return cls.load_json("diagnostic-surveyjs.json")
    
    @classmethod
    def load_scoring_map(cls) -> Dict[str, Any]:
        """Load the scoring map"""
        return cls.load_json("scoring_map.json")

    @classmethod
    @lru_cache(maxsize=8)
    def load_scoring_map_for_type(cls, engagement_type: str) -> Dict[str, Any]:
        """Load the scoring map based on engagement type.

        Args:
            engagement_type: 'sale_ready' or 'value_builder'

        Returns:
            Dictionary containing the scoring map data
        """
        scoring_map_paths = {
            'sale_ready': cls.PROMPTS_DIR / "sale-ready" / "SCORING_MAP_COMPLETE.json",
            'value_builder': cls.PROMPTS_DIR / "value-builder" / "SCORING_MAP_VALUE_BUILDER.json",
        }

        file_path = scoring_map_paths.get(engagement_type, scoring_map_paths['value_builder'])

        if not file_path.exists():
            raise FileNotFoundError(f"Scoring map not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    @lru_cache(maxsize=32)
    def load_prompt_for_type(cls, prompt_name: str, engagement_type: str) -> str:
        """Load a prompt file specific to an engagement type.

        Checks prompts/{sale-ready|value-builder}/{prompt_name}.md first,
        falls back to prompts/{prompt_name}.md if type-specific file doesn't exist.

        Args:
            prompt_name: Name of the prompt file (with or without .md extension)
            engagement_type: 'sale_ready' or 'value_builder'

        Returns:
            String containing the prompt text
        """
        if not prompt_name.endswith('.md'):
            prompt_name = f"{prompt_name}.md"

        type_dirs = {
            'sale_ready': 'sale-ready',
            'value_builder': 'value-builder',
        }
        type_dir = type_dirs.get(engagement_type)

        if type_dir:
            type_path = cls.PROMPTS_DIR / type_dir / prompt_name
            if type_path.exists():
                with open(type_path, 'r', encoding='utf-8') as f:
                    return f.read()

        # Fall back to generic prompt
        file_path = cls.PROMPTS_DIR / prompt_name
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    @classmethod
    def load_task_library(cls) -> Dict[str, Any]:
        """Load the task library"""
        return cls.load_json("task_library.json")

    @classmethod
    def clear_cache(cls):
        """Clear the LRU cache for file loading (useful in tests)"""
        cls.load_json.cache_clear()
        cls.load_prompt.cache_clear()
        cls.load_prompt_for_type.cache_clear()
        cls.load_scoring_map_for_type.cache_clear()


# Convenience functions for direct access
def load_diagnostic_questions() -> Dict[str, Any]:
    """Load diagnostic questions"""
    return FileLoader.load_diagnostic_questions()


def load_scoring_map() -> Dict[str, Any]:
    """Load scoring map"""
    return FileLoader.load_scoring_map()


def load_scoring_map_for_type(engagement_type: str) -> Dict[str, Any]:
    """Load scoring map for a specific engagement type"""
    return FileLoader.load_scoring_map_for_type(engagement_type)


def load_task_library() -> Dict[str, Any]:
    """Load task library"""
    return FileLoader.load_task_library()


def load_prompt(prompt_name: str) -> str:
    """Load a prompt file"""
    return FileLoader.load_prompt(prompt_name)


def load_prompt_for_type(prompt_name: str, engagement_type: str) -> str:
    """Load a prompt file for a specific engagement type"""
    return FileLoader.load_prompt_for_type(prompt_name, engagement_type)

