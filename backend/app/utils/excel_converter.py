"""
Utility for converting Excel files to TXT format for OpenAI compatibility.
OpenAI Responses API doesn't support .xlsx or .csv files as input_file attachments,
so we convert them to .txt (using tab-separated values to preserve table structure)
and route them through Code Interpreter instead.
"""
import os
import tempfile
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Supported Excel extensions
EXCEL_EXTENSIONS = {'.xlsx', '.xls', '.xlsm', '.xlsb'}


def convert_excel_to_txt(
    excel_path: str,
    output_path: Optional[str] = None
) -> Optional[str]:
    """
    Convert an Excel file to TXT format (tab-separated or formatted table).
    OpenAI Responses API supports .txt but not .csv or .xlsx as input_file.
    These must go through Code Interpreter instead.
    
    Args:
        excel_path: Path to the Excel file
        output_path: Optional output path. If None, creates a temp file.
        
    Returns:
        Path to the converted TXT file, or None if conversion failed.
    """
    try:
        import pandas as pd
    except ImportError:
        logger.warning("pandas not installed. Attempting to install...")
        try:
            import subprocess
            subprocess.check_call(['pip', 'install', 'pandas', 'openpyxl'])
            import pandas as pd
        except Exception as e:
            logger.error(f"Failed to install pandas: {e}")
            return None
    
    try:
        # Read Excel file
        # Try to read all sheets, but use the first one by default
        df = pd.read_excel(excel_path, sheet_name=0, engine='openpyxl')
        
        # If output_path not provided, create temp file
        if output_path is None:
            # Create temp file with .txt extension
            temp_fd, temp_path = tempfile.mkstemp(suffix='.txt')
            os.close(temp_fd)
            output_path = temp_path
        
        # Write to TXT with tab-separated values (TSV format)
        # This preserves the table structure while using a supported format
        df.to_csv(output_path, index=False, sep='\t', encoding='utf-8')
        
        # Verify the file has .txt extension
        if not output_path.endswith('.txt'):
            # Rename to ensure .txt extension
            txt_path = output_path.rsplit('.', 1)[0] + '.txt'
            if os.path.exists(output_path):
                os.rename(output_path, txt_path)
                output_path = txt_path
        
        logger.info(f"Converted Excel file {excel_path} to TXT: {output_path}")
        logger.info(f"File size: {os.path.getsize(output_path)} bytes")
        
        # Verify file exists and has correct extension
        if not os.path.exists(output_path):
            logger.error(f"Converted file does not exist: {output_path}")
            return None
        
        if not output_path.lower().endswith('.txt'):
            logger.error(f"Converted file does not have .txt extension: {output_path}")
            return None
        
        return output_path
        
    except ImportError as e:
        logger.error(f"Required library not installed: {e}")
        logger.error("Please install: pip install pandas openpyxl")
        return None
    except Exception as e:
        logger.error(f"Failed to convert Excel file {excel_path}: {e}", exc_info=True)
        return None


def is_excel_file(filename: str) -> bool:
    """Check if a file is an Excel file based on extension."""
    ext = Path(filename).suffix.lower()
    return ext in EXCEL_EXTENSIONS


def convert_if_excel(
    file_path: str,
    original_filename: str,
    keep_original: bool = False
) -> Tuple[str, str, bool]:
    """
    Convert file to TXT if it's an Excel file, otherwise return original.
    OpenAI Responses API doesn't support .csv or .xlsx as input_file attachments.
    These must go through Code Interpreter instead.
    
    Args:
        file_path: Path to the file
        original_filename: Original filename
        keep_original: Whether to keep the original file after conversion
        
    Returns:
        Tuple of (converted_file_path, converted_filename, was_converted)
    """
    if not is_excel_file(original_filename):
        return file_path, original_filename, False
    
    logger.info(f"Detected Excel file: {original_filename}. Converting to TXT...")
    
    # Convert to TXT (tab-separated format)
    txt_path = convert_excel_to_txt(file_path)
    
    if txt_path is None:
        logger.error(f"Failed to convert {original_filename}. Using original file.")
        return file_path, original_filename, False
    
    # Generate new filename
    original_stem = Path(original_filename).stem
    txt_filename = f"{original_stem}.txt"
    
    # Clean up original if requested
    if not keep_original and os.path.exists(file_path):
        try:
            os.unlink(file_path)
        except Exception as e:
            logger.warning(f"Failed to remove original file {file_path}: {e}")
    
    return txt_path, txt_filename, True
