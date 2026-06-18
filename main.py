import os
from dotenv import load_dotenv
from fastapi import FastAPI
from google import genai
from pydantic import BaseModel

# 1. Load environment variables FIRST
load_dotenv()

# 2. Initialize FastAPI and the Gemini Client
app = FastAPI()
client = genai.Client()

# 3. Define the incoming request structure
class ChatRequest(BaseModel):
    message: str

# 4. Your home route
@app.get("/")
def home():
    return {"status": "Chatbot engine is running!"}

# 5. Your chat route connected to Gemini
@app.post("/chat")
def chat(request: ChatRequest):
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=request.message,
    )
    return {"reply": response.text}