from pypdf import PdfReader

def read_pdf():
    try:
        reader = PdfReader("silver_features_v1.pdf")
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        print(text)
    except Exception as e:
        print(f"Error reading PDF: {e}")

if __name__ == "__main__":
    read_pdf()
