"""
BREP Exporter Module

This module exports OpenCASCADE solid models to BREP format files.
It supports exporting individual buildings or combined models from CityGML solidification results.
"""

import os
import tempfile
import uuid
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from config import OCCT_AVAILABLE
from core.citygml_solidifier import SolidificationResult

if OCCT_AVAILABLE:
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Solid, TopoDS_Shell, TopoDS_Compound
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core import BRepTools


@dataclass
class BREPExportResult:
    """Result of BREP export operation"""
    success: bool
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    shapes_exported: int = 0
    file_size_bytes: Optional[int] = None
    export_time: float = 0.0


class BREPExporter:
    """
    Exports OpenCASCADE solid models to BREP format files.
    Optimized for Plateau building models with proper error handling.
    """
    
    def __init__(self):
        if not OCCT_AVAILABLE:
            raise RuntimeError("OpenCASCADE Technology is required for BREP export")
        
        self.debug_mode = False
    
    def enable_debug(self, enabled: bool = True):
        """Enable debug mode for detailed logging"""
        self.debug_mode = enabled
    
    def export_solidification_results(self, solidification_results: List[SolidificationResult], 
                                    output_path: str) -> BREPExportResult:
        """
        Export solidification results to a single BREP file
        
        Args:
            solidification_results: List of SolidificationResult objects
            output_path: Path for output BREP file
            
        Returns:
            BREPExportResult with export status
        """
        start_time = time.time()
        
        try:
            if not solidification_results:
                return BREPExportResult(
                    success=False,
                    error_message="No solidification results provided",
                    export_time=time.time() - start_time
                )
            
            if self.debug_mode:
                print(f"Exporting {len(solidification_results)} solidification results to BREP")
            
            # Create compound to hold all shapes
            builder = BRep_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            
            shapes_added = 0
            
            for i, result in enumerate(solidification_results):
                try:
                    if not result.success:
                        continue
                    
                    # Add solid, shell, or compound to the main compound
                    shape_added = False
                    if result.solid is not None:
                        builder.Add(compound, result.solid)
                        shape_added = True
                        if self.debug_mode:
                            print(f"Added solid {i+1}")
                    elif result.shell is not None:
                        builder.Add(compound, result.shell)
                        shape_added = True
                        if self.debug_mode:
                            print(f"Added shell {i+1}")
                    elif result.compound is not None:
                        builder.Add(compound, result.compound)
                        shape_added = True
                        if self.debug_mode:
                            print(f"Added compound {i+1}")
                    
                    if shape_added:
                        shapes_added += 1
                
                except Exception as shape_error:
                    if self.debug_mode:
                        print(f"Error adding shape {i+1}: {shape_error}")
                    continue
            
            if shapes_added == 0:
                return BREPExportResult(
                    success=False,
                    error_message="No valid shapes found to export",
                    export_time=time.time() - start_time
                )
            
            # Write BREP file
            success = self._write_brep_file(compound, output_path)
            
            if success:
                file_size = os.path.getsize(output_path) if os.path.exists(output_path) else None
                
                if self.debug_mode:
                    print(f"Successfully exported {shapes_added} shapes to BREP file: {file_size} bytes")
                
                return BREPExportResult(
                    success=True,
                    file_path=output_path,
                    shapes_exported=shapes_added,
                    file_size_bytes=file_size,
                    export_time=time.time() - start_time
                )
            else:
                return BREPExportResult(
                    success=False,
                    error_message="Failed to write BREP file",
                    export_time=time.time() - start_time
                )
        
        except Exception as e:
            return BREPExportResult(
                success=False,
                error_message=f"BREP export error: {str(e)}",
                export_time=time.time() - start_time
            )
    
    def export_individual_buildings(self, solidification_results: List[SolidificationResult],
                                   output_directory: str) -> Dict[str, BREPExportResult]:
        """
        Export each building as a separate BREP file
        
        Args:
            solidification_results: List of SolidificationResult objects
            output_directory: Directory for output BREP files
            
        Returns:
            Dictionary mapping building IDs to BREPExportResult objects
        """
        start_time = time.time()
        results = {}
        
        try:
            if not os.path.exists(output_directory):
                os.makedirs(output_directory)
            
            if self.debug_mode:
                print(f"Exporting {len(solidification_results)} buildings individually to {output_directory}")
            
            for i, result in enumerate(solidification_results):
                building_id = f"building_{i+1:04d}"
                
                try:
                    if not result.success:
                        results[building_id] = BREPExportResult(
                            success=False,
                            error_message="Solidification failed for this building",
                            export_time=0.0
                        )
                        continue
                    
                    # Get the primary shape to export
                    shape_to_export = None
                    if result.solid is not None:
                        shape_to_export = result.solid
                    elif result.shell is not None:
                        shape_to_export = result.shell
                    elif result.compound is not None:
                        shape_to_export = result.compound
                    
                    if shape_to_export is None:
                        results[building_id] = BREPExportResult(
                            success=False,
                            error_message="No valid geometry found",
                            export_time=0.0
                        )
                        continue
                    
                    # Generate output file path
                    output_file = os.path.join(output_directory, f"{building_id}.brep")
                    
                    # Write individual BREP file
                    individual_start = time.time()
                    success = self._write_brep_file(shape_to_export, output_file)
                    individual_time = time.time() - individual_start
                    
                    if success:
                        file_size = os.path.getsize(output_file) if os.path.exists(output_file) else None
                        
                        results[building_id] = BREPExportResult(
                            success=True,
                            file_path=output_file,
                            shapes_exported=1,
                            file_size_bytes=file_size,
                            export_time=individual_time
                        )
                        
                        if self.debug_mode:
                            print(f"Exported {building_id}: {file_size} bytes")
                    else:
                        results[building_id] = BREPExportResult(
                            success=False,
                            error_message="Failed to write BREP file",
                            export_time=individual_time
                        )
                
                except Exception as building_error:
                    results[building_id] = BREPExportResult(
                        success=False,
                        error_message=f"Export error: {str(building_error)}",
                        export_time=0.0
                    )
                    
                    if self.debug_mode:
                        print(f"Error exporting {building_id}: {building_error}")
            
            return results
        
        except Exception as e:
            # Return error result for all buildings
            error_result = BREPExportResult(
                success=False,
                error_message=f"Individual export error: {str(e)}",
                export_time=time.time() - start_time
            )
            return {f"building_{i+1:04d}": error_result for i in range(len(solidification_results))}
    
    def _write_brep_file(self, shape: TopoDS_Shape, output_path: str) -> bool:
        """
        Write a TopoDS_Shape to BREP file using OpenCASCADE
        
        Args:
            shape: OpenCASCADE shape to write
            output_path: Output file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if shape.IsNull():
                if self.debug_mode:
                    print("Cannot write null shape to BREP file")
                return False
            
            # Use BRepTools to write the BREP file
            # pythonocc-core 7.7.1+ API
            success = BRepTools.breptools.Write(shape, output_path)
            
            if not success:
                if self.debug_mode:
                    print(f"BRepTools.Write returned False for {output_path}")
                return False
            
            # Verify file was created and has content
            if not os.path.exists(output_path):
                if self.debug_mode:
                    print(f"BREP file was not created: {output_path}")
                return False
            
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                if self.debug_mode:
                    print(f"BREP file is empty: {output_path}")
                return False
            
            return True
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error writing BREP file {output_path}: {e}")
            return False
    
    def create_temporary_output_path(self, prefix: str = "citygml_to_brep") -> str:
        """Create a temporary output file path for BREP files"""
        temp_dir = tempfile.mkdtemp()
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.brep"
        return os.path.join(temp_dir, filename)
    
    def get_export_statistics(self, result: BREPExportResult) -> Dict[str, Any]:
        """Get statistics from BREP export result"""
        return {
            "export_successful": result.success,
            "brep_file_path": result.file_path,
            "shapes_exported": result.shapes_exported,
            "file_size_bytes": result.file_size_bytes,
            "export_time_seconds": result.export_time,
            "file_exists": os.path.exists(result.file_path) if result.file_path else False
        }