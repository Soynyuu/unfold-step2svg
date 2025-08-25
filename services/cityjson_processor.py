"""
CityJSON Processing Service

This service orchestrates the complete CityJSON-based conversion pipeline
for CityGML to BREP/STEP conversion with improved geometry handling.
"""

import os
import tempfile
import uuid
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from config import OCCT_AVAILABLE
from core.cityjson_converter import CityJSONConverter, CityJSONBuilding
from core.cityjson_solidifier import CityJSONSolidifier, CityJSONSolidificationResult
from core.cityjson_validator import CityJSONValidator, ValidationResult, PreprocessingResult
from core.step_exporter import STEPExporter, STEPExportResult
from core.brep_exporter import BREPExporter, BREPExportResult


@dataclass
class CityJSONProcessingOptions:
    """Configuration options for CityJSON-based processing"""
    # Conversion options
    use_citygml_tools: bool = True  # Use citygml-tools for conversion
    fallback_to_builtin: bool = True  # Fall back to built-in converter
    
    # Validation options
    validate_geometry: bool = True  # Run geometry validation
    validation_level: str = "full"  # "full", "basic", or "none"
    
    # Preprocessing options
    preprocess_operations: List[str] = None  # e.g., ["triangulate", "clean"]
    triangulate_surfaces: bool = False  # Triangulate non-planar surfaces
    remove_duplicate_vertices: bool = True  # Remove duplicate vertices
    
    # Solidification options
    tolerance: float = 1e-5  # Geometric tolerance (building scale)
    fix_orientation: bool = True  # Auto-fix face orientations
    enable_healing: bool = True  # Enable shape healing
    
    # Filtering options
    preferred_lod: int = 2  # Preferred Level of Detail
    min_building_area: Optional[float] = None  # Minimum building area
    max_building_count: Optional[int] = None  # Maximum buildings to process
    
    # Export options
    export_format: str = "step"  # "step" or "brep"
    export_individual_files: bool = False  # Export each building separately
    enable_xde: bool = False  # Use XDE for colors/attributes (STEP only)
    
    # Streaming options
    use_streaming: bool = False  # Use CityJSONSeq for streaming
    chunk_size: int = 100  # Buildings per chunk for streaming
    
    # Debug options
    debug_mode: bool = False  # Enable debug logging
    save_intermediate: bool = False  # Save intermediate files
    
    def __post_init__(self):
        """Initialize default preprocessing operations if not provided"""
        if self.preprocess_operations is None:
            self.preprocess_operations = []
            if self.remove_duplicate_vertices:
                self.preprocess_operations.append("remove_duplicate_vertices")
            if self.triangulate_surfaces:
                self.preprocess_operations.append("triangulate")


@dataclass
class CityJSONProcessingResult:
    """Result of CityJSON-based processing pipeline"""
    success: bool
    output_file_path: Optional[str] = None
    error_message: Optional[str] = None
    
    # Processing statistics
    buildings_parsed: int = 0
    buildings_processed: int = 0
    buildings_converted: int = 0
    solids_created: int = 0
    shells_created: int = 0
    compounds_created: int = 0
    
    # Validation results
    validation_performed: bool = False
    validation_result: Optional[ValidationResult] = None
    preprocessing_result: Optional[PreprocessingResult] = None
    
    # Performance metrics
    conversion_time: float = 0.0  # CityGML to CityJSON
    validation_time: float = 0.0
    preprocessing_time: float = 0.0
    solidification_time: float = 0.0
    export_time: float = 0.0
    total_time: float = 0.0
    
    # File information
    input_file_size: Optional[int] = None
    output_file_size: Optional[int] = None
    intermediate_files: List[str] = None
    
    # Detailed statistics
    cityjson_stats: Optional[Dict[str, Any]] = None
    solidification_stats: Optional[Dict[str, Any]] = None
    export_stats: Optional[Dict[str, Any]] = None


class CityJSONProcessor:
    """
    Orchestrates the CityJSON-based conversion pipeline for improved
    CityGML to BREP/STEP conversion with better geometry handling.
    """
    
    def __init__(self, options: Optional[CityJSONProcessingOptions] = None):
        """
        Initialize processor with options
        
        Args:
            options: Processing options or None for defaults
        """
        if not OCCT_AVAILABLE:
            raise RuntimeError("OpenCASCADE Technology is required for CityJSON processing")
        
        self.options = options or CityJSONProcessingOptions()
        
        # Initialize components
        self.converter = CityJSONConverter()
        self.validator = CityJSONValidator()
        self.solidifier = CityJSONSolidifier(tolerance=self.options.tolerance)
        
        # Configure components
        if self.options.debug_mode:
            self.converter.enable_debug(True)
            self.validator.enable_debug(True)
            self.solidifier.enable_debug(True)
        
        self.solidifier.fix_orientation = self.options.fix_orientation
        self.solidifier.enable_healing = self.options.enable_healing
        
        # Initialize exporters based on format
        if self.options.export_format.lower() == "brep":
            self.exporter = BREPExporter()
        else:
            self.exporter = STEPExporter()
        
        if self.options.debug_mode:
            self.exporter.enable_debug(True)
    
    def process_citygml(self, citygml_content: bytes, output_path: str) -> CityJSONProcessingResult:
        """
        Process CityGML content through CityJSON pipeline
        
        Args:
            citygml_content: Raw CityGML file content
            output_path: Path for output file
            
        Returns:
            CityJSONProcessingResult with processing details
        """
        start_time = time.time()
        result = CityJSONProcessingResult(
            success=False,
            input_file_size=len(citygml_content),
            intermediate_files=[]
        )
        
        try:
            # Step 1: Convert CityGML to CityJSON
            if self.options.debug_mode:
                print("Step 1: Converting CityGML to CityJSON")
            
            conversion_start = time.time()
            cityjson_data = self.converter.convert_citygml_to_cityjson(citygml_content)
            result.conversion_time = time.time() - conversion_start
            
            if not cityjson_data:
                result.error_message = "Failed to convert CityGML to CityJSON"
                result.total_time = time.time() - start_time
                return result
            
            # Save intermediate CityJSON if requested
            if self.options.save_intermediate:
                intermediate_path = self._save_intermediate_cityjson(cityjson_data, "converted")
                result.intermediate_files.append(intermediate_path)
            
            # Load CityJSON data
            if not self.converter.load_cityjson(cityjson_data):
                result.error_message = "Failed to load CityJSON data"
                result.total_time = time.time() - start_time
                return result
            
            result.cityjson_stats = self.converter.get_statistics()
            result.buildings_parsed = result.cityjson_stats.get('building_count', 0)
            
            if self.options.debug_mode:
                print(f"Converted to CityJSON: {result.buildings_parsed} buildings")
            
            # Step 2: Validate geometry if enabled
            if self.options.validate_geometry:
                if self.options.debug_mode:
                    print("Step 2: Validating CityJSON geometry")
                
                validation_start = time.time()
                validation_result = self.validator.validate_cityjson(cityjson_data)
                result.validation_time = time.time() - validation_start
                result.validation_performed = True
                result.validation_result = validation_result
                
                if self.options.debug_mode:
                    print(f"Validation: {'VALID' if validation_result.is_valid else 'INVALID'}")
                    if not validation_result.is_valid:
                        print(f"Validation errors: {validation_result.error_count}")
                
                # Optionally stop if validation fails
                if self.options.validation_level == "full" and not validation_result.is_valid:
                    result.error_message = f"Geometry validation failed with {validation_result.error_count} errors"
                    result.total_time = time.time() - start_time
                    return result
            
            # Step 3: Preprocess CityJSON if operations specified
            if self.options.preprocess_operations:
                if self.options.debug_mode:
                    print(f"Step 3: Preprocessing with operations: {self.options.preprocess_operations}")
                
                preprocessing_start = time.time()
                preprocessing_result = self.validator.preprocess_cityjson(
                    cityjson_data, 
                    self.options.preprocess_operations
                )
                result.preprocessing_time = time.time() - preprocessing_start
                result.preprocessing_result = preprocessing_result
                
                if preprocessing_result.success and preprocessing_result.cityjson_data:
                    cityjson_data = preprocessing_result.cityjson_data
                    # Reload processed data
                    self.converter.load_cityjson(cityjson_data)
                    
                    if self.options.save_intermediate:
                        intermediate_path = self._save_intermediate_cityjson(cityjson_data, "preprocessed")
                        result.intermediate_files.append(intermediate_path)
                    
                    if self.options.debug_mode:
                        print(f"Applied operations: {preprocessing_result.operations_applied}")
            
            # Step 4: Extract and filter buildings
            buildings = self.converter.get_buildings()
            filtered_buildings = self._filter_buildings(buildings)
            
            if not filtered_buildings:
                result.error_message = "No buildings remain after filtering"
                result.total_time = time.time() - start_time
                return result
            
            result.buildings_processed = len(filtered_buildings)
            
            if self.options.debug_mode:
                print(f"Step 4: Processing {len(filtered_buildings)} buildings")
            
            # Step 5: Convert to B-Rep solids
            solidification_start = time.time()
            
            # Prepare building data with surfaces
            buildings_data = []
            for building in filtered_buildings:
                # Extract surfaces with proper ring structure
                surfaces = self._extract_building_surfaces(building)
                if surfaces:
                    buildings_data.append((building, surfaces))
            
            if not buildings_data:
                result.error_message = "No valid building surfaces could be extracted"
                result.total_time = time.time() - start_time
                return result
            
            # Convert to B-Rep
            solidification_results = self.solidifier.convert_multiple_buildings(buildings_data)
            result.solidification_time = time.time() - solidification_start
            
            # Count successful conversions
            successful_results = [r for r in solidification_results if r.success]
            result.buildings_converted = len(successful_results)
            result.solids_created = sum(1 for r in successful_results if r.solid is not None)
            result.shells_created = sum(1 for r in successful_results if r.shell is not None)
            result.compounds_created = sum(1 for r in successful_results if r.compound is not None)
            
            result.solidification_stats = self.solidifier.get_conversion_statistics(solidification_results)
            
            if self.options.debug_mode:
                print(f"Solidification complete: {result.buildings_converted} successful")
                print(f"Created: {result.solids_created} solids, {result.shells_created} shells")
            
            if not successful_results:
                result.error_message = "No buildings could be converted to B-Rep shapes"
                result.total_time = time.time() - start_time
                return result
            
            # Step 6: Export to STEP or BREP
            if self.options.debug_mode:
                print(f"Step 6: Exporting to {self.options.export_format.upper()}")
            
            export_start = time.time()
            
            if self.options.export_format.lower() == "brep":
                export_result = self._export_to_brep(successful_results, output_path)
            else:
                export_result = self._export_to_step(successful_results, output_path)
            
            result.export_time = time.time() - export_start
            
            if export_result.success:
                result.success = True
                result.output_file_path = export_result.file_path
                result.output_file_size = export_result.file_size_bytes
                result.export_stats = {
                    'shapes_exported': export_result.shapes_exported,
                    'file_size': export_result.file_size_bytes
                }
            else:
                result.error_message = f"Export failed: {export_result.error_message}"
            
            result.total_time = time.time() - start_time
            
            if self.options.debug_mode:
                print(f"Processing complete in {result.total_time:.2f}s")
                if result.success:
                    print(f"Output file: {result.output_file_path}")
            
            return result
            
        except Exception as e:
            result.error_message = f"Processing error: {str(e)}"
            result.total_time = time.time() - start_time
            return result
    
    def process_cityjson_direct(self, cityjson_content: bytes, output_path: str) -> CityJSONProcessingResult:
        """
        Process CityJSON content directly (skip CityGML conversion)
        
        Args:
            cityjson_content: Raw CityJSON file content
            output_path: Path for output file
            
        Returns:
            CityJSONProcessingResult with processing details
        """
        # Parse CityJSON
        try:
            cityjson_data = json.loads(cityjson_content)
        except json.JSONDecodeError as e:
            result = CityJSONProcessingResult(
                success=False,
                error_message=f"Invalid CityJSON: {str(e)}"
            )
            return result
        
        # Process using main pipeline (skip conversion step)
        result = CityJSONProcessingResult(
            success=False,
            input_file_size=len(cityjson_content)
        )
        
        # Continue with validation, preprocessing, etc.
        # (Implementation similar to process_citygml but starting from loaded CityJSON)
        
        # This is a simplified version - full implementation would follow
        # the same pattern as process_citygml but skip the conversion step
        
        return result
    
    def _extract_building_surfaces(self, building: CityJSONBuilding) -> List[List[List[Tuple[float, float, float]]]]:
        """
        Extract surfaces with ring structure from CityJSON building
        
        Args:
            building: CityJSONBuilding object
            
        Returns:
            List of surfaces, each with rings (outer + holes)
        """
        surfaces = []
        
        for geom in building.geometry:
            geom_type = geom.get("type")
            
            if geom_type == "Solid":
                # Solid: boundaries[shell][surface][ring][vertex_indices]
                for shell in geom.get("boundaries", []):
                    for surface_rings in shell:
                        # surface_rings = [outer_ring_indices, hole1_indices, ...]
                        rings = []
                        for ring_indices in surface_rings:
                            vertices = self._get_vertices_from_indices(ring_indices, building.vertices)
                            if vertices:
                                rings.append(vertices)
                        if rings:
                            surfaces.append(rings)
                            
            elif geom_type in ["MultiSurface", "CompositeSurface"]:
                # MultiSurface: boundaries[surface][ring][vertex_indices]
                for surface_rings in geom.get("boundaries", []):
                    rings = []
                    for ring_indices in surface_rings:
                        vertices = self._get_vertices_from_indices(ring_indices, building.vertices)
                        if vertices:
                            rings.append(vertices)
                    if rings:
                        surfaces.append(rings)
        
        return surfaces
    
    def _get_vertices_from_indices(self, indices: List[int], vertices: List[List[float]]) -> List[Tuple[float, float, float]]:
        """Convert vertex indices to coordinates"""
        coords = []
        for idx in indices:
            if 0 <= idx < len(vertices):
                v = vertices[idx]
                coords.append((v[0], v[1], v[2]))
        return coords
    
    def _filter_buildings(self, buildings: List[CityJSONBuilding]) -> List[CityJSONBuilding]:
        """Apply filtering options to building list"""
        filtered = buildings
        
        # Filter by preferred LoD
        if self.options.preferred_lod is not None:
            filtered = [b for b in filtered if b.lod >= self.options.preferred_lod]
            if not filtered:  # If no buildings match, use all
                filtered = buildings
        
        # Limit number of buildings
        if self.options.max_building_count is not None and self.options.max_building_count > 0:
            filtered = filtered[:self.options.max_building_count]
        
        return filtered
    
    def _export_to_brep(self, solidification_results: List[CityJSONSolidificationResult], 
                       output_path: str) -> BREPExportResult:
        """Export solidification results to BREP"""
        if isinstance(self.exporter, BREPExporter):
            return self.exporter.export_solidification_results(solidification_results, output_path)
        else:
            # Convert to format expected by BREPExporter
            from core.citygml_solidifier import SolidificationResult
            converted_results = []
            for r in solidification_results:
                converted = SolidificationResult()
                converted.success = r.success
                converted.solid = r.solid
                converted.shell = r.shell
                converted.compound = r.compound
                converted.error_message = r.error_message
                converted.is_valid = r.is_valid
                converted.is_closed = r.is_closed
                converted_results.append(converted)
            
            brep_exporter = BREPExporter()
            if self.options.debug_mode:
                brep_exporter.enable_debug(True)
            return brep_exporter.export_solidification_results(converted_results, output_path)
    
    def _export_to_step(self, solidification_results: List[CityJSONSolidificationResult], 
                       output_path: str) -> STEPExportResult:
        """Export solidification results to STEP"""
        if isinstance(self.exporter, STEPExporter):
            # Convert to format expected by STEPExporter
            from core.citygml_solidifier import SolidificationResult
            converted_results = []
            for r in solidification_results:
                converted = SolidificationResult()
                converted.success = r.success
                converted.solid = r.solid
                converted.shell = r.shell
                converted.compound = r.compound
                converted.error_message = r.error_message
                converted.is_valid = r.is_valid
                converted.is_closed = r.is_closed
                converted_results.append(converted)
            return self.exporter.export_solidification_results(converted_results, output_path)
        else:
            # Should not happen, but handle gracefully
            step_exporter = STEPExporter()
            if self.options.debug_mode:
                step_exporter.enable_debug(True)
            # Similar conversion as above
            from core.citygml_solidifier import SolidificationResult
            converted_results = []
            for r in solidification_results:
                converted = SolidificationResult()
                converted.success = r.success
                converted.solid = r.solid
                converted.shell = r.shell
                converted.compound = r.compound
                converted.error_message = r.error_message
                converted.is_valid = r.is_valid
                converted.is_closed = r.is_closed
                converted_results.append(converted)
            return step_exporter.export_solidification_results(converted_results, output_path)
    
    def _save_intermediate_cityjson(self, cityjson_data: Dict[str, Any], suffix: str) -> str:
        """Save intermediate CityJSON file for debugging"""
        temp_path = os.path.join(
            tempfile.gettempdir(),
            f"cityjson_{suffix}_{uuid.uuid4().hex[:8]}.json"
        )
        with open(temp_path, 'w') as f:
            json.dump(cityjson_data, f, indent=2)
        
        if self.options.debug_mode:
            print(f"Saved intermediate CityJSON: {temp_path}")
        
        return temp_path
    
    def get_processing_capabilities(self) -> Dict[str, Any]:
        """Get information about processing capabilities"""
        return {
            "cityjson_converter": {
                "citygml_tools_available": True,  # Check actual availability
                "builtin_converter": True,
                "supported_versions": ["1.0", "1.1"]
            },
            "validator": {
                "val3dity_available": self.validator.val3dity_available,
                "cjio_available": self.validator.cjio_available,
                "iso_19107_compliant": self.validator.val3dity_available
            },
            "preprocessing": {
                "triangulation": True,
                "duplicate_removal": True,
                "lod_filtering": True,
                "operations": ["triangulate", "clean", "remove_duplicate_vertices", "lod_filter"]
            },
            "solidification": {
                "face_orientation_fix": True,
                "hole_support": True,
                "shape_healing": True,
                "sewing": True
            },
            "export_formats": ["step", "brep"],
            "streaming_support": False  # TODO: Implement CityJSONSeq support
        }