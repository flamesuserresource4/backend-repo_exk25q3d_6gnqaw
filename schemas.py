"""
Database Schemas for FlareOS

Each Pydantic model below maps to a MongoDB collection with the lowercase name
of the class. Example: ChatThread -> "chatthread".

These schemas validate input/output for API endpoints and document our data
shapes for the built-in database viewer.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Core user-less identity (device-based)
class Client(BaseModel):
    device_id: str = Field(..., description="Anonymous device identifier generated client-side")

# Chat models
class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' | 'assistant'")
    content: str
    ts: Optional[int] = Field(None, description="Epoch milliseconds")

class ChatThread(BaseModel):
    client_id: str = Field(..., description="Device id owner")
    title: str = Field(..., description="Short title for the chat thread")
    messages: List[ChatMessage] = Field(default_factory=list)
    createdAt: int = Field(..., description="Epoch ms when created")
    updatedAt: int = Field(..., description="Epoch ms when last updated")

# Memory items
class MemoryItem(BaseModel):
    client_id: str
    key: str
    value: str
    ts: int

# Code document (simple HTML snippet)
class CodeDoc(BaseModel):
    client_id: str
    html: str
    updatedAt: int

# API Keys (stored as plain for demo; in production encrypt at rest)
class ApiKeys(BaseModel):
    client_id: str
    providers: Dict[str, str] = Field(default_factory=dict, description="Map of provider -> key")
    updatedAt: int

# Optional generic document model for database modeling playground
class GenericDoc(BaseModel):
    client_id: str
    collection: str
    data: Dict[str, Any]
    createdAt: int
    updatedAt: int
