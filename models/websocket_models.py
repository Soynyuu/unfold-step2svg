"""
WebSocket message models for real-time preview communication
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from enum import Enum

class MessageType(str, Enum):
    """WebSocket message types"""
    # Client to Server
    UPDATE_MODEL = "update_model"
    UPDATE_PARAMETERS = "update_parameters"
    PING = "ping"
    
    # Server to Client
    PREVIEW_UPDATE = "preview_update"
    STATUS = "status"
    ERROR = "error"
    CONNECTION_STATUS = "connection_status"
    PONG = "pong"

class ConnectionStatus(str, Enum):
    """Connection status types"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

class ProcessingStatus(str, Enum):
    """Processing status types"""
    IDLE = "idle"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"
    CACHED = "cached"

# Client to Server Messages
class WebSocketMessage(BaseModel):
    """Base WebSocket message structure"""
    type: MessageType
    data: Dict[str, Any]

class UpdateModelMessage(BaseModel):
    """Message for updating the 3D model"""
    model: str  # Base64 encoded STEP data
    parameters: Optional[Dict[str, Any]] = None

class UpdateParametersMessage(BaseModel):
    """Message for updating only parameters (uses cached model)"""
    parameters: Dict[str, Any]

# Server to Client Messages
class PreviewUpdateResponse(BaseModel):
    """Response containing updated SVG preview"""
    svg: str  # SVG content
    stats: Dict[str, Any]  # Processing statistics
    status: ProcessingStatus
    cached: bool = False  # Whether cached data was used

class StatusMessage(BaseModel):
    """Processing status update"""
    status: ProcessingStatus
    message: Optional[str] = None
    progress: Optional[float] = None  # 0.0 to 1.0

class ErrorResponse(BaseModel):
    """Error message response"""
    message: str
    status: str = "error"
    details: Optional[Dict[str, Any]] = None

class ConnectionStatusMessage(BaseModel):
    """Connection status message"""
    status: ConnectionStatus
    client_id: str
    opencascade_available: bool

# Processing Results
class ProcessingResult(BaseModel):
    """Internal processing result"""
    success: bool
    svg_content: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0
    used_cache: bool = False