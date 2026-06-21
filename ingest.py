import os
import PyPDF2
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector

load_dotenv()

db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
client = genai.Client()

def process_pdf(file_path):
    print(f"Reading {file_path}...")
    
    # 1. Extract text
    reader = PyPDF2.PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    # 2. Chunk text (Splitting by paragraphs)
    chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 50]
    print(f"Created {len(chunks)} chunks. Embedding and uploading to Firestore...")

    # 3 & 4. Embed and Store
    kb_ref = db.collection("knowledge_base")
    
    for i, chunk in enumerate(chunks):
        response = client.models.embed_content(
            model="text-embedding-004", 
            contents=chunk
        )
        
        kb_ref.add({
            "text": chunk,
            # Convert Gemini's array into a Firestore Vector object
            "embedding": Vector(response.embeddings[0].values)
        })
        print(f"Uploaded chunk {i+1}/{len(chunks)}")
        
    print("Ingestion complete!")

if __name__ == "__main__":
    process_pdf("sample.pdf") # Change this to your actual PDF name