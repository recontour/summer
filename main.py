"""
main.py - Summer chatbot entry point (FastAPI)

Keep this file small and focused on wiring.
All interesting logic should live in their own modules (chat_log.py, routes/, etc).
"""

from dotenv import load_dotenv
load_dotenv()  # credentials first

from fastapi import FastAPI
from routes.chat import router as chat_router

app = FastAPI(title="Summer", description="Truth-seeking chatbot")

app.include_router(chat_router)   # mounts /chat

@app.get("/")
def home():
    return {"status": "Summer is running. Use POST /chat"}