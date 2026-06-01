import asyncio
import json
from typing import Dict, List
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Ustaad Dashboard Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, workflow_id: str):
        await websocket.accept()
        if workflow_id not in self.active_connections:
            self.active_connections[workflow_id] = []
        self.active_connections[workflow_id].append(websocket)

    def disconnect(self, websocket: WebSocket, workflow_id: str):
        if workflow_id in self.active_connections and websocket in self.active_connections[workflow_id]:
            self.active_connections[workflow_id].remove(websocket)

    async def broadcast_event(self, workflow_id: str, event_data: dict):
        if workflow_id in self.active_connections:
            message = json.dumps(event_data)
            dead_sockets = []
            for connection in self.active_connections[workflow_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    dead_sockets.append(connection)
            
            for dead in dead_sockets:
                self.disconnect(dead, workflow_id)

manager = ConnectionManager()

@app.websocket("/ws/workflow/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str):
    await manager.connect(websocket, workflow_id)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket, workflow_id)

class EventPayload(BaseModel):
    workflow_id: str
    event_type: str
    node_id: str
    agent: str
    status: str
    payload: dict

@app.post("/api/events")
async def receive_event(event: EventPayload):
    """Internal endpoint for agents to push events to the dashboard"""
    await manager.broadcast_event(
        event.workflow_id,
        {
            "event_type": event.event_type,
            "node_id": event.node_id,
            "agent": event.agent,
            "status": event.status,
            "payload": event.payload
        }
    )
    return {"status": "ok"}

# Mount the Next.js exported static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ustaad-visualizer", "out")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

@app.exception_handler(404)
async def custom_404_handler(request, __):
    if os.path.exists(static_dir):
        index_file = os.path.join(static_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
    return {"error": "Dashboard not built. Run npm run build in ustaad-visualizer"}
