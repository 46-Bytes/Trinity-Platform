"""
Document Template Service
Generates documents from Word templates by replacing placeholders with diagnostic data
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import io
import re
import logging

try:
    from docx import Document
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.run import CT_R
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

logger = logging.getLogger(__name__)


class DocumentTemplateService:
    """
    Service for generating documents from Word templates.
    
    Supports:
    - Listing available templates
    - Extracting placeholders from templates
    - Replacing placeholders with diagnostic data
    - Generating downloadable documents
    """
    
    # Placeholder pattern: {{field_name}}
    PLACEHOLDER_PATTERN = re.compile(r'\{\{(\w+)\}\}')
    
    def __init__(self):
        if not DOCX_AVAILABLE:
            raise ImportError(
                "python-docx is required for document template generation. "
                "Install it with: pip install python-docx"
            )
        
        # Set up template directory
        base_dir = Path(__file__).resolve().parents[2]  # Go up to backend/
        self.templates_dir = base_dir / "files" / "templates" / "diagnostic"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
    
    def list_available_templates(self) -> List[Dict[str, str]]:
        """
        List all available .docx templates in the templates directory.
        
        Returns:
            List of dictionaries with 'name' and 'display_name' keys
        """
        templates = []
        
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory does not exist: {self.templates_dir}")
            return templates
        
        # Log directory path for debugging
        logger.debug(f"Scanning for templates in: {self.templates_dir}")
        
        # Scan for .docx files
        template_files = list(self.templates_dir.glob("*.docx"))
        logger.info(f"Found {len(template_files)} template file(s) in {self.templates_dir}")
        
        for template_file in template_files:
            try:
                # Get display name by removing extension and replacing hyphens/underscores with spaces
                display_name = template_file.stem.replace("_", " ").replace("-", " ")
                # Capitalize first letter of each word
                display_name = " ".join(word.capitalize() for word in display_name.split())
                
                templates.append({
                    "name": template_file.name,
                    "display_name": display_name
                })
                logger.debug(f"Added template: {template_file.name} -> {display_name}")
            except Exception as e:
                logger.error(f"Error processing template file {template_file.name}: {str(e)}")
                continue
        
        logger.info(f"Returning {len(templates)} available template(s)")
        return sorted(templates, key=lambda x: x["display_name"])
    
    def extract_placeholders(self, template_path: Path) -> List[str]:
        """
        Extract all placeholders from a Word template.
        
        Scans paragraphs and table cells for {{field_name}} patterns.
        
        Args:
            template_path: Path to the .docx template file
            
        Returns:
            List of unique placeholder field names (without braces)
        """
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        placeholders = set()
        
        try:
            doc = Document(template_path)
            
            # Extract from paragraphs
            for paragraph in doc.paragraphs:
                matches = self.PLACEHOLDER_PATTERN.findall(paragraph.text)
                placeholders.update(matches)
            
            # Extract from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        # Check cell paragraphs
                        for paragraph in cell.paragraphs:
                            matches = self.PLACEHOLDER_PATTERN.findall(paragraph.text)
                            placeholders.update(matches)
            
        except Exception as e:
            logger.error(f"Error extracting placeholders from {template_path}: {str(e)}")
            raise
        
        return sorted(list(placeholders))
    
    def _replace_text_in_paragraph(self, paragraph, replacements: Dict[str, str]):
        """
        Replace placeholders in a paragraph while preserving formatting.
        
        Args:
            paragraph: docx paragraph object
            replacements: Dictionary mapping placeholder names to values
        """
        if not paragraph.text:
            return
        
        # Find all placeholders in the paragraph
        text = paragraph.text
        matches = list(self.PLACEHOLDER_PATTERN.finditer(text))
        
        if not matches:
            return
        
        # Build new runs with replacements
        # This is complex because we need to preserve formatting
        # Strategy: Clear paragraph and rebuild with replacements
        
        # Store original runs
        original_runs = list(paragraph.runs)
        if not original_runs:
            return
        
        # Clear the paragraph
        paragraph.clear()
        
        # Process text with replacements
        last_end = 0
        new_runs = []
        
        for match in matches:
            # Add text before the match
            if match.start() > last_end:
                before_text = text[last_end:match.start()]
                if before_text:
                    new_runs.append(("text", before_text))
            
            # Add replacement value
            placeholder_name = match.group(1)
            replacement_value = replacements.get(placeholder_name, f"{{{{{placeholder_name}}}}}")
            new_runs.append(("text", replacement_value))
            
            last_end = match.end()
        
        # Add remaining text after last match
        if last_end < len(text):
            after_text = text[last_end:]
            if after_text:
                new_runs.append(("text", after_text))
        
        # If no matches were processed, just replace the whole text
        if not matches:
            # Simple replacement for paragraphs without placeholders
            return
        
        # Rebuild paragraph with new runs
        # Use formatting from first original run if available
        base_formatting = original_runs[0] if original_runs else None
        
        for run_type, run_text in new_runs:
            run = paragraph.add_run(run_text)
            if base_formatting:
                run.font.name = base_formatting.font.name
                try:
                    run.font.size = base_formatting.font.size
                except (ValueError, TypeError):
                    pass  # Template has non-integer font size; skip to keep default
                run.font.bold = base_formatting.font.bold
                run.font.italic = base_formatting.font.italic
                run.font.underline = base_formatting.font.underline
                if base_formatting.font.color and base_formatting.font.color.rgb:
                    run.font.color.rgb = base_formatting.font.color.rgb
    
    def _replace_text_in_cell(self, cell, replacements: Dict[str, str]):
        """
        Replace placeholders in a table cell.
        
        Args:
            cell: docx table cell object
            replacements: Dictionary mapping placeholder names to values
        """
        for paragraph in cell.paragraphs:
            self._replace_text_in_paragraph(paragraph, replacements)
    
    def generate_document(
        self,
        template_name: str,
        user_responses: Dict[str, Any]
    ) -> bytes:
        """
        Generate a document from a template by replacing placeholders with diagnostic data.
        
        Args:
            template_name: Name of the template file (e.g., "business-plan-template.docx")
            user_responses: Dictionary of diagnostic responses to use for replacements
            
        Returns:
            Bytes of the generated Word document
        """
        template_path = self.templates_dir / template_name
        
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        logger.info(f"Generating document from template: {template_name}")
        
        try:
            # Load template
            doc = Document(template_path)
            
            # Extract placeholders from template
            placeholders = self.extract_placeholders(template_path)
            logger.info(f"Found {len(placeholders)} unique placeholders in template")
            
            # Build replacements dictionary
            # Only include fields that exist in user_responses
            replacements = {}
            missing_fields = []
            
            for placeholder in placeholders:
                if placeholder in user_responses:
                    value = user_responses[placeholder]
                    # Convert value to string, handle None/empty
                    if value is None:
                        replacements[placeholder] = "[Not provided]"
                    elif isinstance(value, (list, dict)):
                        # Handle complex types - convert to readable string
                        replacements[placeholder] = str(value)
                    else:
                        replacements[placeholder] = str(value)
                else:
                    missing_fields.append(placeholder)
                    replacements[placeholder] = "[Not provided]"
            
            if missing_fields:
                logger.warning(f"Missing fields in user_responses: {missing_fields}")
            
            # Replace placeholders in paragraphs
            for paragraph in doc.paragraphs:
                if paragraph.text:
                    # Simple text replacement for paragraphs
                    text = paragraph.text
                    for placeholder, replacement in replacements.items():
                        text = text.replace(f"{{{{{placeholder}}}}}", replacement)
                    
                    # Clear and set new text (preserves basic formatting)
                    if text != paragraph.text:
                        # Store formatting from first run
                        if paragraph.runs:
                            first_run = paragraph.runs[0]
                            paragraph.clear()
                            new_run = paragraph.add_run(text)
                            # Preserve basic formatting
                            new_run.font.name = first_run.font.name
                            try:
                                new_run.font.size = first_run.font.size
                            except (ValueError, TypeError):
                                pass  # Template has non-integer font size; skip
                            new_run.font.bold = first_run.font.bold
                            new_run.font.italic = first_run.font.italic
                        else:
                            paragraph.text = text

            # Replace placeholders in tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            if paragraph.text:
                                text = paragraph.text
                                for placeholder, replacement in replacements.items():
                                    text = text.replace(f"{{{{{placeholder}}}}}", replacement)
                                
                                if text != paragraph.text:
                                    # Store formatting from first run
                                    if paragraph.runs:
                                        first_run = paragraph.runs[0]
                                        paragraph.clear()
                                        new_run = paragraph.add_run(text)
                                        # Preserve basic formatting
                                        new_run.font.name = first_run.font.name
                                        try:
                                            new_run.font.size = first_run.font.size
                                        except (ValueError, TypeError):
                                            pass  # Template has non-integer font size; skip
                                        new_run.font.bold = first_run.font.bold
                                        new_run.font.italic = first_run.font.italic
                                    else:
                                        paragraph.text = text
            
            # Save to bytes
            buffer = io.BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            
            logger.info(f"Document generated successfully from template: {template_name}")
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error generating document from template {template_name}: {str(e)}")
            raise


# Singleton instance
_document_template_service = None

def get_document_template_service() -> DocumentTemplateService:
    """Get or create the document template service singleton."""
    global _document_template_service
    if _document_template_service is None:
        _document_template_service = DocumentTemplateService()
    return _document_template_service

