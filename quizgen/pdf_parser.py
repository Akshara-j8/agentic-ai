"""
PDF Parser Module

Extracts text content from PDF files for quiz generation.
Designed to work with Streamlit's UploadedFile objects.
"""

from pypdf import PdfReader
from io import BytesIO


def extract_pdf_text(uploaded_file):
    """
    Extract text from a PDF file uploaded via Streamlit.
    
    Args:
        uploaded_file: A Streamlit UploadedFile object or file-like object
                      containing a PDF file
    
    Returns:
        dict: A dictionary containing:
            - file_name (str): Name of the uploaded file
            - page_count (int): Total number of pages
            - pages (list): List of dicts with page_number and text
            - combined_text (str): All page text joined together
    
    Raises:
        ValueError: If the file is empty or corrupted
        Exception: For other unexpected errors during parsing
    """
    try:
        # Get file name (handle both UploadedFile and regular file objects)
        file_name = getattr(uploaded_file, 'name', 'unknown.pdf')
        
        # Read file content into BytesIO for pypdf
        # Reset file pointer to beginning in case it was already read
        uploaded_file.seek(0)
        file_content = uploaded_file.read()
        
        # Check if file is empty
        if not file_content or len(file_content) == 0:
            raise ValueError(f"File '{file_name}' is empty")
        
        # Load PDF from BytesIO
        pdf_stream = BytesIO(file_content)
        try:
            pdf_reader = PdfReader(pdf_stream)
        except Exception as e:
            raise ValueError(f"Failed to open '{file_name}' as PDF file. "
                           f"File may be corrupted or not a valid PDF: {str(e)}")
        
        # Check if PDF has pages
        if len(pdf_reader.pages) == 0:
            raise ValueError(f"PDF '{file_name}' contains no pages")
        
        # Extract text from all pages
        pages_data = []
        all_text = []
        
        for page_idx, page in enumerate(pdf_reader.pages, start=1):
            page_text = _extract_text_from_page(page)
            
            pages_data.append({
                "page_number": page_idx,
                "text": page_text
            })
            
            # Collect non-empty text for combined output
            if page_text.strip():
                all_text.append(page_text)
        
        # Check if any text was extracted
        if not all_text:
            raise ValueError(f"No text could be extracted from '{file_name}'. "
                           f"The PDF may be image-based or encrypted.")
        
        # Prepare result dictionary
        result = {
            "file_name": file_name,
            "page_count": len(pdf_reader.pages),
            "pages": pages_data,
            "combined_text": "\n\n".join(all_text)
        }
        
        return result
    
    except ValueError:
        # Re-raise ValueError with our custom message
        raise
    except Exception as e:
        # Catch any other unexpected errors
        raise Exception(f"Unexpected error parsing PDF: {str(e)}")


def _extract_text_from_page(page):
    """
    Extract all text from a single PDF page and clean it.
    
    Args:
        page: A pypdf Page object
    
    Returns:
        str: Cleaned text found in the page
    """
    try:
        # Extract text from the page
        text = page.extract_text()
        
        if not text:
            return ""
        
        # Clean up scanning artifacts and watermarks
        text = _clean_scanning_artifacts(text)
        
        # Return cleaned text (strip extra whitespace)
        return text.strip() if text else ""
    
    except Exception as e:
        # If extraction fails for this page, return empty string
        # This prevents one bad page from breaking the entire extraction
        return ""


def _clean_scanning_artifacts(text: str) -> str:
    """
    Remove common scanning artifacts, watermarks, and repetitive text.
    
    Args:
        text: Raw extracted text
    
    Returns:
        str: Cleaned text
    """
    import re
    
    # Common scanning artifacts and watermarks to remove
    artifacts = [
        r"Scanned with CamScanner",
        r"Scanned by CamScanner",
        r"Created with CamScanner",
        r"www\.camscanner\.com",
        r"Downloaded from.*",
        r"Page \d+ of \d+",
        r"Copyright ©.*",
        r"\[Type here\]",
        r"\[Type text\]",
    ]
    
    # Remove artifacts (case insensitive)
    for artifact in artifacts:
        text = re.sub(artifact, "", text, flags=re.IGNORECASE)
    
    # Remove excessive newlines and whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 newlines
    text = re.sub(r' {2,}', ' ', text)      # Max 1 space
    
    # Remove lines that are just numbers or single characters (likely page numbers)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Keep lines that have meaningful content (more than 3 characters or contain letters)
        if len(stripped) > 3 or (stripped and any(c.isalpha() for c in stripped)):
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


# Optional test block for standalone execution
if __name__ == "__main__":
    """
    Simple test to verify the parser works with a sample file.
    Usage: python pdf_parser.py
    """
    print("PDF Parser Test")
    print("-" * 50)
    print("To test with a real file, create a simple test script:")
    print()
    print("  with open('sample.pdf', 'rb') as f:")
    print("      result = extract_pdf_text(f)")
    print("      print(f\"File: {result['file_name']}\")")
    print("      print(f\"Pages: {result['page_count']}\")")
    print("      print(f\"Text length: {len(result['combined_text'])}\")")
    print()
    print("Note: This module is designed for Streamlit integration.")
    print("The extract_pdf_text() function accepts file-like objects.")
