"""
WebSocket endpoint for real-time 3D to SVG preview

This module provides WebSocket support for real-time conversion of STEP files
to SVG papercraft patterns, enabling instant preview updates when parameters change.
"""

import json
import asyncio
import hashlib
import base64
from typing import Dict, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.routing import APIRouter
import logging

from config import OCCT_AVAILABLE
from services.realtime_processor import RealtimeProcessor
from models.websocket_models import (
    WebSocketMessage,
    UpdateModelMessage,
    UpdateParametersMessage,
    PreviewUpdateResponse,
    ErrorResponse,
    ConnectionStatus
)

logger = logging.getLogger(__name__)

# WebSocket router
websocket_router = APIRouter()

class ConnectionManager:
    """Manages WebSocket connections and message routing"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.processor = RealtimeProcessor()
        
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")
        
        # Send connection status
        await self.send_message(client_id, {
            "type": "connection_status",
            "data": {
                "status": "connected",
                "client_id": client_id,
                "opencascade_available": OCCT_AVAILABLE
            }
        })
    
    def disconnect(self, client_id: str):
        """Remove a disconnected client"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            # Clean up cached data for this client
            self.processor.cleanup_client(client_id)
            logger.info(f"Client {client_id} disconnected. Remaining connections: {len(self.active_connections)}")
    
    async def send_message(self, client_id: str, message: dict):
        """Send a message to a specific client"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)
    
    async def broadcast(self, message: dict, exclude_client: Optional[str] = None):
        """Broadcast a message to all connected clients except one"""
        disconnected_clients = []
        for client_id, websocket in self.active_connections.items():
            if client_id != exclude_client:
                try:
                    await websocket.send_json(message)
                except:
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    async def handle_message(self, client_id: str, raw_message: str):
        """Process incoming WebSocket messages"""
        try:
            message_data = json.loads(raw_message)
            message_type = message_data.get("type")
            data = message_data.get("data", {})
            
            if not OCCT_AVAILABLE and message_type in ["update_model", "update_parameters"]:
                await self.send_error(client_id, "OpenCASCADE not available")
                return
            
            if message_type == "update_model":
                await self.handle_model_update(client_id, data)
            elif message_type == "update_parameters":
                await self.handle_parameter_update(client_id, data)
            elif message_type == "ping":
                await self.send_message(client_id, {"type": "pong"})
            else:
                await self.send_error(client_id, f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError as e:
            await self.send_error(client_id, f"Invalid JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {str(e)}")
            await self.send_error(client_id, f"Processing error: {str(e)}")
    
    async def handle_model_update(self, client_id: str, data: dict):
        """Handle full model update with new STEP data"""
        try:
            # Extract model data
            model_data = data.get("model")
            parameters = data.get("parameters", {})
            
            if not model_data:
                await self.send_error(client_id, "No model data provided")
                return
            
            # Send processing status
            await self.send_message(client_id, {
                "type": "status",
                "data": {"status": "processing", "message": "Processing 3D model..."}
            })
            
            # Process the model
            result = await self.processor.process_model(
                client_id=client_id,
                model_data=model_data,
                parameters=parameters
            )
            
            if result.success:
                await self.send_message(client_id, {
                    "type": "preview_update",
                    "data": {
                        "svg": result.svg_content,
                        "stats": result.stats,
                        "status": "success"
                    }
                })
            else:
                await self.send_error(client_id, result.error_message or "Processing failed")
                
        except Exception as e:
            logger.error(f"Model update error for {client_id}: {str(e)}")
            await self.send_error(client_id, str(e))
    
    async def handle_parameter_update(self, client_id: str, data: dict):
        """Handle parameter-only update (uses cached geometry)"""
        try:
            parameters = data.get("parameters", {})
            
            # Send processing status
            await self.send_message(client_id, {
                "type": "status",
                "data": {"status": "processing", "message": "Updating parameters..."}
            })
            
            # Process parameter update
            result = await self.processor.update_parameters(
                client_id=client_id,
                parameters=parameters
            )
            
            if result.success:
                await self.send_message(client_id, {
                    "type": "preview_update",
                    "data": {
                        "svg": result.svg_content,
                        "stats": result.stats,
                        "status": "success",
                        "cached": True
                    }
                })
            else:
                await self.send_error(client_id, result.error_message or "Parameter update failed")
                
        except Exception as e:
            logger.error(f"Parameter update error for {client_id}: {str(e)}")
            await self.send_error(client_id, str(e))
    
    async def send_error(self, client_id: str, error_message: str):
        """Send error message to client"""
        await self.send_message(client_id, {
            "type": "error",
            "data": {
                "message": error_message,
                "status": "error"
            }
        })

# Global connection manager instance
manager = ConnectionManager()

@websocket_router.websocket("/ws/preview")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time preview"""
    import uuid
    client_id = str(uuid.uuid4())
    
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            # Process message asynchronously
            await manager.handle_message(client_id, data)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {str(e)}")
        manager.disconnect(client_id)