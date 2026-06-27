"""
PDF Parser Module

Extracts text content from PDF files for quiz generation.
Designed to work with Streamlit's UploadedFile objects.
"""

from io import BytesIO
from pypdf import PdfReader


def extract_pdf_text(uploaded_file):
    """
    Extract text from a PDF file uploaded via Streamlit.

    Args:
        uploaded_file: A Streamlit UploadedFile object or file-like object
                       containing a .pdf file

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
        # Get file name
        file_name = getattr(uploaded_file, "name", "unknown.pdf")

        # Read file content
        uploaded_file.seek(0)
        file_content = uploaded_file.read()

        if not file_content:
            raise ValueError(f"File '{file_name}' is empty")

        pdf_stream = BytesIO(file_content)

        try:
            reader = PdfReader(pdf_stream)
        except Exception as e:
            raise ValueError(
                f"Failed to open '{file_name}' as PDF. "
                f"File may be corrupted or invalid: {str(e)}"
            )

        pages_data = []
        all_text = []

        for page_idx, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
                page_text = page_text.strip()
            except Exception:
                page_text = ""

            pages_data.append({
                "page_number": page_idx,
                "text": page_text
            })

            if page_text:
                all_text.append(page_text)

        result = {
            "file_name": file_name,
            "page_count": len(reader.pages),
            "pages": pages_data,
            "combined_text": "\n\n".join(all_text)
        }

        return result

    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Unexpected error parsing PDF: {str(e)}")


if __name__ == "__main__":
    print("PDF Parser Module")
    print("Use extract_pdf_text(uploaded_file) inside Streamlit.")