from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import os
import json
import fitz  # PyMuPDF
import pdfplumber
import csv

app = Flask(__name__, template_folder='templates')

# Configuration
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'jfif', 'webp', 'bmp', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Image text extraction
def extract_text_from_image(image_path):
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        return str(e)

# PDF text extraction functions
def extract_text_pymupdf(pdf_path):
    """Extract text from PDF using PyMuPDF."""
    text = ''
    try:
        pdf_document = fitz.open(pdf_path)
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            page_text = page.get_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        return f"Error extracting text with PyMuPDF: {e}"
    return text

def extract_text_and_tables_pdfplumber(pdf_path):
    """Extract text and tables from PDF using pdfplumber."""
    text = ''
    tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                
                # Extract tables
                page_tables = page.extract_tables()
                for table in page_tables:
                    tables.append(table)
    except Exception as e:
        return f"Error extracting text and tables with pdfplumber: {e}", []
    return text, tables

def save_tables_as_csv(tables, filename):
    """Save extracted tables as a CSV file."""
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for table in tables:
                for row in table:
                    writer.writerow(row)
                writer.writerow([])  # Add an empty line between tables
    except Exception as e:
        return f"Error saving tables to CSV: {e}"

def extract_text_from_pdf(pdf_path):
    """Extract text and tables from PDF using both PyMuPDF and pdfplumber."""
    text_pymupdf = extract_text_pymupdf(pdf_path)
    text_pdfplumber, tables = extract_text_and_tables_pdfplumber(pdf_path)

    # Combine the results from both methods
    combined_text = f"--- PyMuPDF Extraction ---\n{text_pymupdf.strip()}\n\n--- pdfplumber Extraction ---\n{text_pdfplumber.strip()}"
    
    if not combined_text.strip():
        combined_text = "No text extracted from the PDF."
    
    return combined_text, tables

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        if filename.lower().endswith('.pdf'):
            # Process PDF file
            combined_text, tables = extract_text_from_pdf(file_path)
            csv_filename = os.path.splitext(filename)[0] + '_tables.csv'
            csv_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
            save_tables_as_csv(tables, csv_path)
            
            pdf_json_output = {
                'text': combined_text,
                'csv': csv_filename
            }
            json_filename = os.path.splitext(filename)[0] + '_output.json'
            json_path = os.path.join(app.config['UPLOAD_FOLDER'], json_filename)
            with open(json_path, 'w', encoding='utf-8') as json_file:
                json.dump(pdf_json_output, json_file, ensure_ascii=False, indent=4)
            
            return jsonify({
                'text': combined_text,
                'csv': csv_filename,
                'json': json_filename
            })
        else:
            # Process image file
            text = extract_text_from_image(file_path)
            csv_filename = os.path.splitext(filename)[0] + '.csv'
            csv_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['text'])
                writer.writerow([text])
            
            image_json_output = {
                'text': text,
                'csv': csv_filename
            }
            json_filename = os.path.splitext(filename)[0] + '_output.json'
            json_path = os.path.join(app.config['UPLOAD_FOLDER'], json_filename)
            with open(json_path, 'w', encoding='utf-8') as json_file:
                json.dump(image_json_output, json_file, ensure_ascii=False, indent=4)
            
            return jsonify({
                'text': text,
                'csv': csv_filename,
                'json': json_filename
            })
    return jsonify({'error': 'Invalid file type'}), 400

if __name__ == '__main__':
    app.run(debug=True)
