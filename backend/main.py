from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import uuid
import os

from schemas import ContractionCreate, ContractionUpdate, ContractionResponse, UpdateResponse
import database
from auth import (
    LoginRequest,
    TokenResponse,
    create_access_token,
    authenticate_user,
    get_current_user,
)

app = FastAPI(title="Lily - Birth Day Updates")

# Create uploads directory
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


@app.get("/")
async def root():
    return {"message": "Lily API", "status": "running"}


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    if not authenticate_user(request.username, request.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )
    access_token = create_access_token(request.username)
    return TokenResponse(access_token=access_token)


# ============ Contractions ============

@app.get("/contractions", response_model=List[ContractionResponse])
async def get_contractions():
    return database.get_all_contractions()


@app.post("/contraction", response_model=ContractionResponse)
async def create_contraction(
    contraction: ContractionCreate,
    username: str = Depends(get_current_user)
):
    result = database.create_contraction(contraction.start_time, contraction.end_time)
    await manager.broadcast({"type": "contraction_new", "data": result})
    return result


@app.put("/contraction/{contraction_id}", response_model=ContractionResponse)
async def update_contraction(
    contraction_id: int,
    update: ContractionUpdate,
    username: str = Depends(get_current_user)
):
    result = database.update_contraction(contraction_id, update.end_time)
    if not result:
        raise HTTPException(status_code=404, detail="Contraction not found")
    await manager.broadcast({"type": "contraction_update", "data": result})
    return result


@app.delete("/contraction/{contraction_id}")
async def delete_contraction(
    contraction_id: int,
    username: str = Depends(get_current_user)
):
    if database.delete_contraction(contraction_id):
        await manager.broadcast({"type": "contraction_delete", "id": contraction_id})
        return {"success": True}
    raise HTTPException(status_code=404, detail="Contraction not found")


@app.post("/contraction/{contraction_id}/toggle-ignore")
async def toggle_ignore_interval(
    contraction_id: int,
    username: str = Depends(get_current_user)
):
    result = database.toggle_ignore_interval(contraction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Contraction not found")
    await manager.broadcast({"type": "contraction_update", "data": result})
    return result


# ============ Updates (Photos, Notes, Milestones) ============

@app.get("/updates", response_model=List[UpdateResponse])
async def get_updates():
    return database.get_all_updates()


@app.post("/update/photo", response_model=UpdateResponse)
async def upload_photo(
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    username: str = Depends(get_current_user)
):
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Generate unique filename
    ext = Path(file.filename).suffix or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / filename

    # Save file
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # Create database entry
    result = database.create_update(
        timestamp=datetime.now(),
        update_type="photo",
        content=caption,
        photo_filename=filename
    )

    await manager.broadcast({"type": "update_new", "data": result})
    return result


@app.post("/update/note", response_model=UpdateResponse)
async def create_note(
    content: str = Form(...),
    username: str = Depends(get_current_user)
):
    result = database.create_update(
        timestamp=datetime.now(),
        update_type="note",
        content=content
    )

    await manager.broadcast({"type": "update_new", "data": result})
    return result


@app.post("/update/milestone", response_model=UpdateResponse)
async def create_milestone(
    milestone: str = Form(...),
    content: Optional[str] = Form(None),
    username: str = Depends(get_current_user)
):
    result = database.create_update(
        timestamp=datetime.now(),
        update_type="milestone",
        content=content,
        milestone=milestone
    )

    await manager.broadcast({"type": "update_new", "data": result})
    return result


@app.post("/update/audio", response_model=UpdateResponse)
async def upload_audio(
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    username: str = Depends(get_current_user)
):
    # Validate file type
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio file")

    # Generate unique filename
    ext = Path(file.filename).suffix or ".webm"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / filename

    # Save file
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # Create database entry
    result = database.create_update(
        timestamp=datetime.now(),
        update_type="audio",
        content=caption,
        audio_filename=filename
    )

    await manager.broadcast({"type": "update_new", "data": result})
    return result


@app.put("/update/{update_id}", response_model=UpdateResponse)
async def edit_update(
    update_id: int,
    content: str = Form(...),
    username: str = Depends(get_current_user)
):
    result = database.update_update(update_id, content)

    if not result:
        raise HTTPException(status_code=404, detail="Update not found")

    await manager.broadcast({"type": "update_edit", "data": result})
    return result


@app.delete("/update/{update_id}")
async def delete_update(
    update_id: int,
    username: str = Depends(get_current_user)
):
    media_files = database.delete_update(update_id)

    if media_files is None:
        raise HTTPException(status_code=404, detail="Update not found")

    # Delete media files if they exist
    for filename in [media_files.get("photo_filename"), media_files.get("audio_filename")]:
        if filename:
            filepath = UPLOAD_DIR / filename
            if filepath.exists():
                os.remove(filepath)

    await manager.broadcast({"type": "update_delete", "id": update_id})
    return {"success": True}


# ============ Combined Feed ============

@app.get("/feed")
async def get_feed():
    """Get combined timeline of contractions and updates"""
    contractions = database.get_all_contractions()
    updates = database.get_all_updates()

    # Add type markers and normalize timestamp field
    feed = []

    for c in contractions:
        feed.append({
            "feed_type": "contraction",
            "timestamp": c["start_time"],
            **c
        })

    for u in updates:
        feed.append({
            "feed_type": u["type"],
            "timestamp": u["timestamp"],
            **u
        })

    # Sort by timestamp descending
    feed.sort(key=lambda x: x["timestamp"], reverse=True)

    return feed


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
