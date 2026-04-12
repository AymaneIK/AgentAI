import pdfplumber
import pytesseract
from PIL import Image
import docx
import io
import PyPDF2
import os

def parse_pdf(file_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                else:
                    # Fallback to OCR for this page if image-based
                    im = page.to_image()
                    text += pytesseract.image_to_string(im.original) + "\n"
    except Exception as e:
        print(f"pdfplumber error: {e}, falling back to PyPDF2")
        text = parse_pdf_fallback(file_path)
    return text.strip()

def parse_pdf_fallback(file_path: str) -> str:
    text = ""
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"PyPDF2 error: {e}")
    return text.strip()

def parse_docx(file_path: str) -> str:
    text = ""
    try:
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        print(f"docx error: {e}")
    return text.strip()

def parse_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return parse_pdf(file_path)
    elif ext in ['.doc', '.docx']:
        return parse_docx(file_path)
    elif ext == '.txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file format: {ext}")
