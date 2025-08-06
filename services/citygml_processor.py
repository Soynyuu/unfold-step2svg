"""
CityGML Processing Service

This service orchestrates the complete CityGML to STEP conversion pipeline.
It coordinates parsing, solidification, and export operations.
"""

import os
import tempfile
import uuid
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from config import OCCT_AVAILABLE
from core.citygml_parser import CityGMLParser, BuildingGeometry
from core.citygml_solidifier import CityGMLSolidifier, SolidificationResult
from core.step_exporter import STEPExporter, STEPExportResult
from core.brep_exporter import BREPExporter, BREPExportResult
from core.citygml_to_ifc_converter import CityGMLToIFCConverter, IFCConversionResult
from core.ifc_to_step_converter import IFCToSTEPConverter, STEPConversionResult


@dataclass
class CityGMLProcessingOptions:
    """Configuration options for CityGML processing"""
    # Parsing options
    preferred_lod: int = 2  # Preferred Level of Detail (0, 1, 2)
    min_building_area: Optional[float] = None  # Minimum building area to process
    max_building_count: Optional[int] = None  # Maximum number of buildings to process
    
    # Solidification options
    tolerance: float = 1e-6  # Geometric tolerance
    enable_shell_closure: bool = True  # Attempt to close open shells
    
    # Export options
    export_individual_files: bool = False  # Export each building separately
    output_format: str = "step"  # Output format (currently only STEP)
    
    # Conversion pipeline options
    use_ifc_pipeline: bool = True  # Use CityGML → IFC → STEP pipeline (recommended)
    ifc_schema_version: str = "IFC4"  # IFC schema version
    save_intermediate_ifc: bool = False  # Save intermediate IFC file
    
    # Processing options
    debug_mode: bool = False  # Enable debug logging
    save_intermediate_results: bool = False  # Save intermediate processing results


@dataclass
class CityGMLProcessingResult:
    """Result of complete CityGML processing"""
    success: bool
    step_file_path: Optional[str] = None
    brep_file_path: Optional[str] = None  # Support for BREP output
    error_message: Optional[str] = None
    
    # Processing statistics
    buildings_parsed: int = 0
    buildings_solidified: int = 0
    solids_created: int = 0
    shells_created: int = 0
    
    # Performance metrics
    parse_time: float = 0.0
    solidify_time: float = 0.0
    export_time: float = 0.0
    total_time: float = 0.0
    
    # File information
    input_file_size: Optional[int] = None
    output_file_size: Optional[int] = None
    
    # Detailed results
    parsing_stats: Optional[Dict[str, Any]] = None
    solidification_stats: Optional[Dict[str, Any]] = None
    export_stats: Optional[Dict[str, Any]] = None


class CityGMLProcessor:
    """
    Orchestrates the complete CityGML to STEP conversion pipeline.
    """
    
    def __init__(self, options: Optional[CityGMLProcessingOptions] = None):
        if not OCCT_AVAILABLE:
            raise RuntimeError("OpenCASCADE Technology is required for CityGML processing")
        
        self.options = options or CityGMLProcessingOptions()
        
        # Initialize components
        self.parser = CityGMLParser()
        
        # Initialize conversion pipeline based on options
        if self.options.use_ifc_pipeline:
            self.ifc_converter = CityGMLToIFCConverter(schema_version=self.options.ifc_schema_version)
            self.step_converter = IFCToSTEPConverter()
            if self.options.debug_mode:
                self.ifc_converter.enable_debug(True)
                self.step_converter.enable_debug(True)
        else:
            # Legacy pipeline
            self.solidifier = CityGMLSolidifier(tolerance=self.options.tolerance)
            self.exporter = STEPExporter()
            if self.options.debug_mode:
                self.solidifier.enable_debug(True)
                self.exporter.enable_debug(True)
        
        # BREP exporter (always available for legacy pipeline)
        self.brep_exporter = BREPExporter()
        if self.options.debug_mode:
            self.brep_exporter.enable_debug(True)
    
    def process_from_file(self, input_file_path: str, output_file_path: str) -> CityGMLProcessingResult:
        """
        Process CityGML file and convert to STEP format
        
        Args:
            input_file_path: Path to input CityGML file
            output_file_path: Path for output STEP file
            
        Returns:
            CityGMLProcessingResult with processing results
        """
        start_time = time.time()
        
        try:
            # Get input file size
            input_file_size = os.path.getsize(input_file_path) if os.path.exists(input_file_path) else None
            
            # Read file content
            with open(input_file_path, 'rb') as f:
                content = f.read()
            
            return self.process_from_bytes(content, output_file_path, input_file_size)
            
        except Exception as e:
            return CityGMLProcessingResult(
                success=False,
                error_message=f"File processing error: {str(e)}",
                total_time=time.time() - start_time,
                input_file_size=input_file_size
            )
    
    def process_from_bytes(self, content: bytes, output_file_path: str, 
                          input_file_size: Optional[int] = None) -> CityGMLProcessingResult:
        """
        Process CityGML content and convert to STEP format
        
        Args:
            content: Raw CityGML file content
            output_file_path: Path for output STEP file
            input_file_size: Size of input file in bytes
            
        Returns:
            CityGMLProcessingResult with processing results
        """
        start_time = time.time()
        result = CityGMLProcessingResult(
            success=False,
            input_file_size=input_file_size or len(content)
        )
        
        try:
            # Step 1: Parse CityGML
            parse_start = time.time()
            parse_success = self.parser.parse_from_bytes(content)
            result.parse_time = time.time() - parse_start
            
            if not parse_success:
                result.error_message = "Failed to parse CityGML file"
                result.total_time = time.time() - start_time
                return result
            
            buildings = self.parser.get_buildings()
            result.buildings_parsed = len(buildings)
            result.parsing_stats = self.parser.get_statistics()
            
            if self.options.debug_mode:
                print(f"Parsed {len(buildings)} buildings from CityGML")
            
            # Apply filtering
            filtered_buildings = self._filter_buildings(buildings)
            if self.options.debug_mode and len(filtered_buildings) != len(buildings):
                print(f"Filtered to {len(filtered_buildings)} buildings")
            
            if not filtered_buildings:
                result.error_message = "No buildings remain after filtering"
                result.total_time = time.time() - start_time
                return result
            
            # Use different conversion pipeline based on options
            if self.options.use_ifc_pipeline:
                # Step 2: Convert CityGML to IFC
                solidify_start = time.time()
                
                # Save intermediate IFC file if requested
                ifc_file_path = None
                if self.options.save_intermediate_ifc:
                    ifc_file_path = os.path.splitext(output_file_path)[0] + ".ifc"
                
                ifc_result = self.ifc_converter.convert_buildings_to_ifc(
                    filtered_buildings, ifc_file_path
                )
                result.solidify_time = time.time() - solidify_start
                
                if not ifc_result.success:
                    result.error_message = f"CityGML to IFC conversion failed: {ifc_result.error_message}"
                    result.total_time = time.time() - start_time
                    return result
                
                result.buildings_solidified = ifc_result.buildings_converted
                result.solidification_stats = self.ifc_converter.get_conversion_statistics(ifc_result)
                
                if self.options.debug_mode:
                    print(f"Converted {ifc_result.buildings_converted} buildings to IFC")
                    print(f"Created {ifc_result.elements_created} IFC elements")
                
                # Validate IFC geometry
                geometry_validation = self._validate_ifc_geometry(ifc_result.ifc_file)
                if not geometry_validation["has_geometry"]:
                    result.error_message = f"IFC validation failed: {geometry_validation['message']}"
                    result.total_time = time.time() - start_time
                    return result
                
                if self.options.debug_mode:
                    print(f"IFC validation: {geometry_validation['entities_with_geometry']} entities have geometry")
                
                # Step 3: Convert IFC to STEP
                export_start = time.time()
                step_result = self.step_converter.convert_from_ifc_result(ifc_result, output_file_path)
                result.export_time = time.time() - export_start
                
                if step_result.success:
                    result.success = True
                    result.step_file_path = step_result.step_file_path
                    result.output_file_size = step_result.file_size_bytes
                    result.export_stats = self.step_converter.get_conversion_statistics(step_result)
                else:
                    result.error_message = f"IFC to STEP conversion failed: {step_result.error_message}"
                
            else:
                # Legacy OpenCASCADE pipeline
                solidify_start = time.time()
                solidification_results = self.solidifier.convert_multiple_buildings(filtered_buildings)
                result.solidify_time = time.time() - solidify_start
                
                # Count successful solidifications
                successful_results = [r for r in solidification_results if r.success]
                result.buildings_solidified = len(successful_results)
                result.solids_created = sum(1 for r in successful_results if r.solid is not None)
                result.shells_created = sum(1 for r in successful_results if r.shell is not None)
                result.solidification_stats = self.solidifier.get_conversion_statistics(solidification_results)
                
                if self.options.debug_mode:
                    print(f"Solidified {len(successful_results)}/{len(filtered_buildings)} buildings")
                    print(f"Created {result.solids_created} solids and {result.shells_created} shells")
                
                # Check if we have any usable shapes (solids, shells, or compounds)
                usable_results = [r for r in successful_results if 
                                 r.solid is not None or r.shell is not None or r.compound is not None]
                if not usable_results:
                    result.error_message = "No buildings could be converted to usable shapes (solids, shells, or compounds)"
                    result.total_time = time.time() - start_time
                    return result
                
                # Step 3: Export to STEP
                export_start = time.time()
                export_result = self.exporter.export_solidification_results(
                    usable_results, output_file_path
                )
                result.export_time = time.time() - export_start
                
                if export_result.success:
                    result.success = True
                    result.step_file_path = export_result.file_path
                    result.output_file_size = export_result.file_size_bytes
                else:
                    result.error_message = f"STEP export failed: {export_result.error_message}"
                
                result.export_stats = {
                    "shapes_exported": export_result.shapes_exported,
                    "file_size_bytes": export_result.file_size_bytes
                }
            
            result.export_time = time.time() - export_start
            result.total_time = time.time() - start_time
            
            if self.options.debug_mode:
                print(f"Export completed in {result.export_time:.2f}s")
                print(f"Total processing time: {result.total_time:.2f}s")
            
            return result
            
        except Exception as e:
            result.error_message = f"Processing error: {str(e)}"
            result.total_time = time.time() - start_time
            return result
    
    def process_to_brep(self, content: bytes, output_file_path: str, 
                       input_file_size: Optional[int] = None) -> CityGMLProcessingResult:
        """
        Process CityGML content and convert to BREP format
        
        This method uses the legacy OpenCASCADE pipeline specifically for BREP output,
        as it provides direct access to OpenCASCADE shapes needed for BREP export.
        
        Args:
            content: Raw CityGML file content
            output_file_path: Path for output BREP file
            input_file_size: Size of input file in bytes
            
        Returns:
            CityGMLProcessingResult with BREP processing results
        """
        start_time = time.time()
        result = CityGMLProcessingResult(
            success=False,
            input_file_size=input_file_size or len(content)
        )
        
        try:
            # Step 1: Parse CityGML
            parse_start = time.time()
            parse_success = self.parser.parse_from_bytes(content)
            result.parse_time = time.time() - parse_start
            
            if not parse_success:
                result.error_message = "Failed to parse CityGML file"
                result.total_time = time.time() - start_time
                return result
            
            buildings = self.parser.get_buildings()
            result.buildings_parsed = len(buildings)
            result.parsing_stats = self.parser.get_statistics()
            
            if self.options.debug_mode:
                print(f"Parsed {len(buildings)} buildings from CityGML for BREP export")
            
            # Apply filtering
            filtered_buildings = self._filter_buildings(buildings)
            if self.options.debug_mode and len(filtered_buildings) != len(buildings):
                print(f"Filtered to {len(filtered_buildings)} buildings for BREP export")
            
            if not filtered_buildings:
                result.error_message = "No buildings remain after filtering"
                result.total_time = time.time() - start_time
                return result
            
            # Step 2: Solidify using legacy OpenCASCADE pipeline (required for BREP)
            if not hasattr(self, 'solidifier'):
                # Initialize solidifier if using IFC pipeline by default
                self.solidifier = CityGMLSolidifier(tolerance=self.options.tolerance)
                if self.options.debug_mode:
                    self.solidifier.enable_debug(True)
            
            solidify_start = time.time()
            solidification_results = self.solidifier.convert_multiple_buildings(filtered_buildings)
            result.solidify_time = time.time() - solidify_start
            
            # Count successful solidifications
            successful_results = [r for r in solidification_results if r.success]
            result.buildings_solidified = len(successful_results)
            result.solids_created = sum(1 for r in successful_results if r.solid is not None)
            result.shells_created = sum(1 for r in successful_results if r.shell is not None)
            result.solidification_stats = self.solidifier.get_conversion_statistics(solidification_results)
            
            if self.options.debug_mode:
                print(f"Solidified {len(successful_results)}/{len(filtered_buildings)} buildings for BREP")
                print(f"Created {result.solids_created} solids and {result.shells_created} shells")
            
            # Check if we have any usable shapes (solids, shells, or compounds)
            usable_results = [r for r in successful_results if 
                             r.solid is not None or r.shell is not None or r.compound is not None]
            if not usable_results:
                result.error_message = "No buildings could be converted to usable shapes (solids, shells, or compounds)"
                result.total_time = time.time() - start_time
                return result
            
            # Step 3: Export to BREP
            export_start = time.time()
            if self.options.export_individual_files:
                # Export individual BREP files
                output_directory = os.path.splitext(output_file_path)[0] + "_buildings"
                individual_results = self.brep_exporter.export_individual_buildings(
                    usable_results, output_directory
                )
                
                # Check if any individual exports succeeded
                successful_exports = [r for r in individual_results.values() if r.success]
                if successful_exports:
                    result.success = True
                    result.brep_file_path = output_directory
                    result.output_file_size = sum(r.file_size_bytes or 0 for r in successful_exports)
                    result.export_stats = {
                        "shapes_exported": len(successful_exports),
                        "individual_files": len(individual_results),
                        "total_file_size_bytes": result.output_file_size,
                        "export_directory": output_directory
                    }
                else:
                    result.error_message = "All individual BREP exports failed"
                    
            else:
                # Export combined BREP file
                export_result = self.brep_exporter.export_solidification_results(
                    usable_results, output_file_path
                )
                
                if export_result.success:
                    result.success = True
                    result.brep_file_path = export_result.file_path
                    result.output_file_size = export_result.file_size_bytes
                    result.export_stats = self.brep_exporter.get_export_statistics(export_result)
                else:
                    result.error_message = f"BREP export failed: {export_result.error_message}"
            
            result.export_time = time.time() - export_start
            result.total_time = time.time() - start_time
            
            if self.options.debug_mode:
                print(f"BREP export completed in {result.export_time:.2f}s")
                print(f"Total BREP processing time: {result.total_time:.2f}s")
            
            return result
            
        except Exception as e:
            result.error_message = f"BREP processing error: {str(e)}"
            result.total_time = time.time() - start_time
            return result
    
    def _filter_buildings(self, buildings: List[BuildingGeometry]) -> List[BuildingGeometry]:
        """Apply filtering options to building list"""
        filtered = buildings
        
        # Filter by minimum area
        if self.options.min_building_area is not None and self.options.min_building_area > 0:
            filtered = [b for b in filtered if b.area is None or b.area >= self.options.min_building_area]
        
        # Filter by preferred LoD (prefer buildings with higher or equal LoD)
        if self.options.preferred_lod is not None:
            # Sort by LoD (higher first) and take buildings with acceptable LoD
            filtered = sorted(filtered, key=lambda b: b.lod, reverse=True)
            # Keep buildings with LoD >= preferred_lod, or all if none meet criteria
            high_lod = [b for b in filtered if b.lod >= self.options.preferred_lod]
            if high_lod:
                filtered = high_lod
        
        # Limit number of buildings
        if self.options.max_building_count is not None and self.options.max_building_count > 0:
            filtered = filtered[:self.options.max_building_count]
        
        return filtered
    
    def validate_citygml_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a CityGML file without full processing
        
        Args:
            file_path: Path to CityGML file
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            "is_valid": False,
            "file_exists": False,
            "file_size": 0,
            "error_message": None,
            "building_count": 0,
            "parsing_stats": None
        }
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                validation_result["error_message"] = "File does not exist"
                return validation_result
            
            validation_result["file_exists"] = True
            validation_result["file_size"] = os.path.getsize(file_path)
            
            # Try to parse
            parser = CityGMLParser()
            if parser.parse_from_file(file_path):
                validation_result["is_valid"] = True
                validation_result["building_count"] = parser.get_building_count()
                validation_result["parsing_stats"] = parser.get_statistics()
            else:
                validation_result["error_message"] = "Failed to parse CityGML content"
            
            return validation_result
            
        except Exception as e:
            validation_result["error_message"] = f"Validation error: {str(e)}"
            return validation_result
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported input formats"""
        return ["gml", "xml", "citygml"]
    
    def get_processing_capabilities(self) -> Dict[str, Any]:
        """Get information about processing capabilities"""
        return {
            "opencascade_available": OCCT_AVAILABLE,
            "supported_input_formats": self.get_supported_formats(),
            "supported_output_formats": ["step", "stp"],
            "supported_lod_levels": [0, 1, 2],
            "features": {
                "multi_surface_to_solid": True,
                "shell_closure": True,
                "individual_building_export": True,
                "batch_processing": True,
                "debug_mode": True
            }
        }
    
    def create_temporary_output_path(self, prefix: str = "citygml_to_step") -> str:
        """Create a temporary output file path"""
        temp_dir = tempfile.mkdtemp()
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.step"
        return os.path.join(temp_dir, filename)
    
    def estimate_processing_time(self, building_count: int) -> Dict[str, float]:
        """
        Estimate processing time based on building count
        
        Args:
            building_count: Number of buildings to process
            
        Returns:
            Dictionary with time estimates in seconds
        """
        # Rough estimates based on typical performance
        parse_time_per_building = 0.1  # seconds
        solidify_time_per_building = 2.0  # seconds  
        export_time_base = 1.0  # seconds
        export_time_per_building = 0.5  # seconds
        
        estimates = {
            "parse_time": building_count * parse_time_per_building,
            "solidify_time": building_count * solidify_time_per_building,
            "export_time": export_time_base + (building_count * export_time_per_building),
        }
        
        estimates["total_time"] = sum(estimates.values())
        
        return estimates
    
    def _validate_ifc_geometry(self, ifc_file) -> Dict[str, Any]:
        """
        Validate that IFC file contains proper geometric representations
        
        Returns:
            Dictionary with validation results
        """
        try:
            if not ifc_file:
                return {
                    "has_geometry": False,
                    "message": "No IFC file provided",
                    "entities_with_geometry": 0,
                    "entities_total": 0
                }
            
            # Count entities with geometric representations
            entities_with_geometry = 0
            entities_total = 0
            
            # Check IFC products for geometric representations
            for entity in ifc_file.by_type("IfcProduct"):
                entities_total += 1
                
                if hasattr(entity, 'Representation') and entity.Representation:
                    if entity.Representation.Representations:
                        for representation in entity.Representation.Representations:
                            if (hasattr(representation, 'Items') and 
                                representation.Items and 
                                representation.RepresentationType in ["SurfaceModel", "Brep", "SweptSolid"]):
                                entities_with_geometry += 1
                                break
            
            has_geometry = entities_with_geometry > 0
            
            if not has_geometry:
                message = f"No geometric representations found in {entities_total} IFC entities"
            else:
                message = f"Found geometry in {entities_with_geometry}/{entities_total} entities"
            
            return {
                "has_geometry": has_geometry,
                "message": message,
                "entities_with_geometry": entities_with_geometry,
                "entities_total": entities_total
            }
            
        except Exception as e:
            return {
                "has_geometry": False,
                "message": f"Validation error: {str(e)}",
                "entities_with_geometry": 0,
                "entities_total": 0
            }
    
    def cleanup_temporary_files(self, file_paths: List[str]):
        """Clean up temporary files"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    if self.options.debug_mode:
                        print(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                if self.options.debug_mode:
                    print(f"Warning: Could not clean up {file_path}: {e}")
    
    def get_processing_summary(self, result: CityGMLProcessingResult) -> str:
        """Generate a human-readable processing summary"""
        if not result.success:
            return f"Processing failed: {result.error_message}"
        
        summary_parts = [
            f"Successfully processed CityGML file",
            f"Buildings parsed: {result.buildings_parsed}",
            f"Buildings solidified: {result.buildings_solidified}",
            f"Solids created: {result.solids_created}",
            f"Shells created: {result.shells_created}",
            f"Processing time: {result.total_time:.2f}s",
        ]
        
        if result.output_file_size:
            summary_parts.append(f"Output file size: {result.output_file_size:,} bytes")
        
        return "\n".join(summary_parts)