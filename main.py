import os
from dotenv import load_dotenv
from google.genai import types

# 1. This MUST be at the very top so the credentials load first
load_dotenv()

from fastapi import FastAPI
from google import genai
from google.cloud import firestore
from pydantic import BaseModel

# 2. Initialize your clients after loading env variables
db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
client = genai.Client()
app = FastAPI()

# 3. Request structure
class ChatRequest(BaseModel):
    message: str
    session_id: str

@app.get("/")
def home():
    return {"status": "Chatbot engine is running!"}