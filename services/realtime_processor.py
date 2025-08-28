"""
Real-time processing service for WebSocket-based 3D to SVG conversion

This service manages cached processing state and provides incremental updates
for improved performance during real-time preview.
"""

import base64
import hashlib
import time
import asyncio
from typing import Dict, Optional, Any
import tempfile
import os
import logging

from config import OCCT_AVAILABLE
from services.step_processor import StepUnfoldGenerator
from models.request_models import BrepPapercraftRequest
from models.websocket_models import ProcessingResult
from core.cache_manager import CacheManager

logger = logging.getLogger(__name__)

class RealtimeProcessor:
    """
    Manages real-time processing with caching and incremental updates
    """
    
    def __init__(self):
        # Cache manager for storing processed data
        self.cache_manager = CacheManager()
        
        # Client-specific processors
        self.client_processors: Dict[str, StepUnfoldGenerator] = {}
        
        # Client model hashes for cache invalidation
        self.client_model_hashes: Dict[str, str] = {}
        
    def cleanup_client(self, client_id: str):
        """Clean up resources for a disconnected client"""
        if client_id in self.client_processors:
            del self.client_processors[client_id]
        if client_id in self.client_model_hashes:
            # Clean up cache entries
            self.cache_manager.remove_client_cache(client_id)
            del self.client_model_hashes[client_id]
        logger.info(f"Cleaned up resources for client {client_id}")
    
    async def process_model(self, client_id: str, model_data: str, parameters: Dict[str, Any]) -> ProcessingResult:
        """
        Process a new 3D model with given parameters
        
        Args:
            client_id: Unique client identifier
            model_data: Base64 encoded STEP file data
            parameters: Processing parameters
            
        Returns:
            ProcessingResult with SVG content or error
        """
        start_time = time.time()
        
        try:
            # Decode model data
            try:
                model_bytes = base64.b64decode(model_data)
            except Exception as e:
                return ProcessingResult(
                    success=False,
                    error_message=f"Failed to decode model data: {str(e)}"
                )
            
            # Calculate model hash for caching
            model_hash = hashlib.md5(model_bytes).hexdigest()
            
            # Check if we have cached geometry for this model
            cached_geometry = self.cache_manager.get_geometry(model_hash)
            
            # Create or get processor for this client
            if client_id not in self.client_processors:
                self.client_processors[client_id] = StepUnfoldGenerator()
            
            processor = self.client_processors[client_id]
            
            # If geometry is cached and model hasn't changed, skip loading
            if cached_geometry and self.client_model_hashes.get(client_id) == model_hash:
                logger.info(f"Using cached geometry for client {client_id}")
                # Restore cached state
                processor.faces_data = cached_geometry['faces_data']
                processor.edges_data = cached_geometry['edges_data']
                processor.solid_shape = cached_geometry.get('solid_shape')
            else:
                # Load new model
                logger.info(f"Loading new model for client {client_id}")
                
                # Load model from bytes
                success = processor.load_from_bytes(model_bytes, "step")
                if not success:
                    return ProcessingResult(
                        success=False,
                        error_message="Failed to load STEP file"
                    )
                
                # Cache the geometry
                self.cache_manager.set_geometry(model_hash, {
                    'faces_data': processor.faces_data,
                    'edges_data': processor.edges_data,
                    'solid_shape': processor.solid_shape
                })
                
                # Update client model hash
                self.client_model_hashes[client_id] = model_hash
            
            # Apply parameters and generate SVG
            result = await self._generate_svg(processor, parameters)
            
            # Add timing information
            result.processing_time = time.time() - start_time
            result.used_cache = cached_geometry is not None
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing model for {client_id}: {str(e)}")
            return ProcessingResult(
                success=False,
                error_message=f"Processing error: {str(e)}",
                processing_time=time.time() - start_time
            )
    
    async def update_parameters(self, client_id: str, parameters: Dict[str, Any]) -> ProcessingResult:
        """
        Update only parameters using cached geometry
        
        Args:
            client_id: Unique client identifier
            parameters: New processing parameters
            
        Returns:
            ProcessingResult with updated SVG
        """
        start_time = time.time()
        
        try:
            # Check if we have a processor for this client
            if client_id not in self.client_processors:
                return ProcessingResult(
                    success=False,
                    error_message="No model loaded for this client. Please upload a model first."
                )
            
            processor = self.client_processors[client_id]
            
            # Check if processor has loaded model
            if processor.solid_shape is None:
                return ProcessingResult(
                    success=False,
                    error_message="No model data available. Please upload a model first."
                )
            
            # Generate SVG with new parameters
            result = await self._generate_svg(processor, parameters)
            
            # Mark as cached since we're using existing geometry
            result.used_cache = True
            result.processing_time = time.time() - start_time
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating parameters for {client_id}: {str(e)}")
            return ProcessingResult(
                success=False,
                error_message=f"Parameter update error: {str(e)}",
                processing_time=time.time() - start_time
            )
    
    async def _generate_svg(self, processor: StepUnfoldGenerator, parameters: Dict[str, Any]) -> ProcessingResult:
        """
        Generate SVG from processor with given parameters
        
        Args:
            processor: StepUnfoldGenerator instance with loaded model
            parameters: Processing parameters
            
        Returns:
            ProcessingResult with SVG content
        """
        try:
            # Create request object with parameters
            request = BrepPapercraftRequest(
                scale_factor=parameters.get('scale_factor', 10.0),
                layout_mode=parameters.get('layout_mode', 'canvas'),
                page_format=parameters.get('page_format', 'A4'),
                page_orientation=parameters.get('page_orientation', 'portrait'),
                units=parameters.get('units', 'mm'),
                tab_width=parameters.get('tab_width', 5.0),
                min_face_area=parameters.get('min_face_area', 1.0),
                max_faces=parameters.get('max_faces', 20),
                show_scale=parameters.get('show_scale', True),
                show_fold_lines=parameters.get('show_fold_lines', True),
                show_cut_lines=parameters.get('show_cut_lines', True)
            )
            
            # Generate papercraft in temporary file
            output_path = os.path.join(tempfile.mkdtemp(), "preview.svg")
            
            # Run generation in executor to avoid blocking
            loop = asyncio.get_event_loop()
            svg_path, stats = await loop.run_in_executor(
                None,
                processor.generate_brep_papercraft,
                request,
                output_path
            )
            
            # Read SVG content
            with open(svg_path, 'r', encoding='utf-8') as svg_file:
                svg_content = svg_file.read()
            
            # Clean up temporary file
            try:
                os.unlink(svg_path)
            except:
                pass
            
            return ProcessingResult(
                success=True,
                svg_content=svg_content,
                stats=stats
            )
            
        except Exception as e:
            logger.error(f"SVG generation error: {str(e)}")
            return ProcessingResult(
                success=False,
                error_message=f"SVG generation failed: {str(e)}"
            )