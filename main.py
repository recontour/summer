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

@app.post("/chat")
def chat(request: ChatRequest):
    session_ref = db.collection("sessions").document(request.session_id).collection("messages")
    
    # 1. Fetch history from Firestore, ordered by time
    past_messages = session_ref.order_by("timestamp").stream()
    
    # 2. Build the history format Gemini expects
    history = []
    for msg in past_messages:
        data = msg.to_dict()
        if "user_message" in data and "bot_reply" in data:
            history.append(types.Content(role="user", parts=[types.Part.from_text(text=data["user_message"])]))
            history.append(types.Content(role="model", parts=[types.Part.from_text(text=data["bot_reply"])]))

    # --- NEW: Print the payload to the VS Code terminal ---
    print("\n--- WHAT WE ARE SENDING TO GEMINI ---")
    for item in history:
        print(f"[{item.role.upper()}]: {item.parts[0].text}")
    print(f"[NEW USER MESSAGE]: {request.message}")
    print("---------------------------------------\n")

    # 3. Initialize a chat session with the history
    chat_session = client.chats.create(
        model="gemini-3.1-flash-lite",
        history=history
    )

    # 4. Send the new message
    response = chat_session.send_message(request.message)
    bot_reply = response.text

    # 5. Send the new message
    response = chat_session.send_message(request.message)
    bot_reply = response.text

    # --- NEW: Grab the token counts directly from the response ---
    prompt_tokens = response.usage_metadata.prompt_token_count
    reply_tokens = response.usage_metadata.candidates_token_count
    total_tokens = response.usage_metadata.total_token_count

    # 6. Log the new exchange to Firestore (Now with tokens!)
    session_ref.add({
        "user_message": request.message,
        "bot_reply": bot_reply,
        "prompt_tokens": prompt_tokens,
        "reply_tokens": reply_tokens,
        "total_tokens": total_tokens,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    
    return {"reply": bot_reply}