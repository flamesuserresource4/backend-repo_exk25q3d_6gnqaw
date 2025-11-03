import os
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import ChatMessage, ChatThread, MemoryItem, CodeDoc, ApiKeys

app = FastAPI(title="FlareOS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "FlareOS Backend Running"}


@app.get("/test")
def test_database():
    ok = db is not None
    collections = []
    if ok:
        try:
            collections = db.list_collection_names()
        except Exception:
            pass
    return {
        "backend": "✅ Running",
        "database": "✅ Connected" if ok else "❌ Not Available",
        "collections": collections[:10],
    }


# Utility
class ChatRequest(BaseModel):
    client_id: str
    thread_id: Optional[str] = None
    message: str


@app.get("/api/chats/{client_id}")
def list_threads(client_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    threads = list(db["chatthread"].find({"client_id": client_id}).sort("updatedAt", -1))
    for t in threads:
        t["id"] = str(t.pop("_id"))
    return {"threads": threads}


@app.post("/api/chats/send")
def send_message(req: ChatRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    now = int(time.time() * 1000)
    user_msg = {"role": "user", "content": req.message, "ts": now}

    # Very simple AI echo; replace with provider calls using stored keys
    assistant_msg = {"role": "assistant", "content": f"Echo: {req.message}", "ts": now}

    # Upsert thread
    title = req.message.strip()[:30] if req.message else "New Chat"
    if req.thread_id:
        try:
            _id = ObjectId(req.thread_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid thread id")
        thread = db["chatthread"].find_one({"_id": _id, "client_id": req.client_id})
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        db["chatthread"].update_one(
            {"_id": _id},
            {
                "$set": {"updatedAt": now},
                "$setOnInsert": {"title": title},
                "$push": {"messages": {"$each": [user_msg, assistant_msg]}}
            },
        )
        thread = db["chatthread"].find_one({"_id": _id})
    else:
        doc = {
            "client_id": req.client_id,
            "title": title,
            "messages": [user_msg, assistant_msg],
            "createdAt": now,
            "updatedAt": now,
        }
        inserted_id = db["chatthread"].insert_one(doc).inserted_id
        thread = db["chatthread"].find_one({"_id": inserted_id})

    thread["id"] = str(thread.pop("_id"))
    return {"thread": thread}


@app.delete("/api/chats/{client_id}/{thread_id}")
def delete_thread(client_id: str, thread_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    try:
        _id = ObjectId(thread_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid thread id")
    res = db["chatthread"].delete_one({"_id": _id, "client_id": client_id})
    return {"deleted": res.deleted_count == 1}


# Memory CRUD
class MemoryUpsert(BaseModel):
    client_id: str
    key: str
    value: str


@app.get("/api/memory/{client_id}")
def get_memory(client_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    items = list(db["memoryitem"].find({"client_id": client_id}).sort("ts", -1))
    for it in items:
        it["id"] = str(it.pop("_id"))
    return {"items": items}


@app.post("/api/memory")
def upsert_memory(body: MemoryUpsert):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    now = int(time.time() * 1000)
    db["memoryitem"].update_one(
        {"client_id": body.client_id, "key": body.key},
        {"$set": {"value": body.value, "ts": now}},
        upsert=True,
    )
    doc = db["memoryitem"].find_one({"client_id": body.client_id, "key": body.key})
    doc["id"] = str(doc.pop("_id"))
    return {"item": doc}


@app.delete("/api/memory/{client_id}/{key}")
def delete_memory(client_id: str, key: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    res = db["memoryitem"].delete_one({"client_id": client_id, "key": key})
    return {"deleted": res.deleted_count == 1}


# Code storage
class CodeSave(BaseModel):
    client_id: str
    html: str


@app.get("/api/code/{client_id}")
def get_code(client_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    doc = db["codedoc"].find_one({"client_id": client_id})
    if not doc:
        return {"html": ""}
    return {"html": doc.get("html", ""), "updatedAt": doc.get("updatedAt")}


@app.post("/api/code")
def save_code(body: CodeSave):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    now = int(time.time() * 1000)
    db["codedoc"].update_one(
        {"client_id": body.client_id},
        {"$set": {"html": body.html, "updatedAt": now}},
        upsert=True,
    )
    return {"ok": True, "updatedAt": now}


# API keys storage (demo; store plaintext)
class KeysBody(BaseModel):
    client_id: str
    providers: dict


@app.get("/api/keys/{client_id}")
def get_keys(client_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    doc = db["apikeys"].find_one({"client_id": client_id})
    if not doc:
        return {"providers": {}, "updatedAt": None}
    return {"providers": doc.get("providers", {}), "updatedAt": doc.get("updatedAt")}


@app.post("/api/keys")
def save_keys(body: KeysBody):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    now = int(time.time() * 1000)
    db["apikeys"].update_one(
        {"client_id": body.client_id},
        {"$set": {"providers": body.providers, "updatedAt": now}},
        upsert=True,
    )
    return {"ok": True, "updatedAt": now}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
