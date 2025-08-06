"""
STEP Exporter Module

This module exports OpenCASCADE solid geometries to STEP format files.
It handles both single solids and compound shapes with multiple buildings.
"""

import os
import tempfile
import uuid
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from config import OCCT_AVAILABLE
from core.citygml_solidifier import SolidificationResult

if OCCT_AVAILABLE:
    from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.IFSelect import IFSelect_ReturnStatus
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Solid, TopoDS_Shell, TopoDS_Compound
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TCollection import TCollection_AsciiString
    from OCC.Core.Standard import Standard_Failure


@dataclass
class STEPExportResult:
    """Result of STEP export operation"""
    success: bool
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    shapes_exported: int = 0
    file_size_bytes: Optional[int] = None


class STEPExporter:
    """
    Exports OpenCASCADE shapes to STEP format files.
    Handles both individual solids and compound shapes.
    """
    
    def __init__(self):
        if not OCCT_AVAILABLE:
            raise RuntimeError("OpenCASCADE Technology is required for STEP export")
        
        self.debug_mode = False
        self._setup_step_units()
    
    def enable_debug(self, enabled: bool = True):
        """Enable debug mode for detailed logging"""
        self.debug_mode = enabled
    
    def _setup_step_units(self):
        """Configure STEP export units and precision"""
        try:
            # Set up STEP export parameters
            Interface_Static.SetCVal("xstep.cascade.unit", "MM")  # Millimeters
            Interface_Static.SetCVal("write.step.unit", "MM")
            Interface_Static.SetIVal("write.step.nonmanifold", 1)  # Allow non-manifold shapes
            Interface_Static.SetIVal("write.step.assembly", 1)     # Write assemblies
            Interface_Static.SetRVal("write.precision.val", 0.01)  # Precision in mm
            
            if self.debug_mode:
                print("STEP export units configured: MM with 0.01mm precision")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Warning: Could not configure STEP units: {e}")
    
    def export_single_solid(self, solid: TopoDS_Solid, output_path: str, 
                           building_name: Optional[str] = None) -> STEPExportResult:
        """
        Export a single solid to STEP format
        
        Args:
            solid: OpenCASCADE solid to export
            output_path: Output file path
            building_name: Optional name for the solid
            
        Returns:
            STEPExportResult with export status
        """
        try:
            writer = STEPControl_Writer()
            
            # Add the solid to the writer
            status = writer.Transfer(solid, STEPControl_AsIs)
            if status != IFSelect_ReturnStatus.IFSelect_RetDone:
                return STEPExportResult(
                    success=False,
                    error_message=f"Failed to transfer solid to STEP writer: {status}"
                )
            
            # Write to file
            # Validate output path
            if not output_path or not isinstance(output_path, str):
                return STEPExportResult(
                    success=False,
                    error_message=f"Invalid output path: {output_path}"
                )
            
            # Ensure the directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:  # Only create directory if there's a directory component
                os.makedirs(output_dir, exist_ok=True)
            
            # Convert path to ASCII string safely and write
            try:
                ascii_path = TCollection_AsciiString(str(output_path).encode('ascii', 'replace').decode('ascii'))
                write_status = writer.Write(ascii_path)
            except Exception as occ_error:
                # OpenCASCADE internal error
                return STEPExportResult(
                    success=False,
                    error_message=f"OpenCASCADE STEP write error: {str(occ_error)}"
                )
            if write_status != IFSelect_ReturnStatus.IFSelect_RetDone:
                return STEPExportResult(
                    success=False,
                    error_message=f"Failed to write STEP file: {write_status}"
                )
            
            # Get file size
            file_size = None
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
            
            if self.debug_mode:
                print(f"Successfully exported solid to {output_path} ({file_size} bytes)")
            
            return STEPExportResult(
                success=True,
                file_path=output_path,
                shapes_exported=1,
                file_size_bytes=file_size
            )
            
        except Exception as e:
            return STEPExportResult(
                success=False,
                error_message=f"STEP export failed: {str(e)}"
            )
    
    def export_shell(self, shell: TopoDS_Shell, output_path: str,
                     building_name: Optional[str] = None) -> STEPExportResult:
        """
        Export a shell (open surface) to STEP format
        
        Args:
            shell: OpenCASCADE shell to export
            output_path: Output file path
            building_name: Optional name for the shell
            
        Returns:
            STEPExportResult with export status
        """
        try:
            # Validate shell before export
            if shell is None:
                return STEPExportResult(
                    success=False,
                    error_message="Shell is None"
                )
            
            if self.debug_mode:
                print(f"Exporting shell '{building_name or 'unnamed'}' to {output_path}")
            
            writer = STEPControl_Writer()
            
            # Add the shell to the writer
            status = writer.Transfer(shell, STEPControl_AsIs)
            if status != IFSelect_ReturnStatus.IFSelect_RetDone:
                return STEPExportResult(
                    success=False,
                    error_message=f"Failed to transfer shell to STEP writer: {status}"
                )
            
            # Write to file
            # Validate output path
            if not output_path or not isinstance(output_path, str):
                return STEPExportResult(
                    success=False,
                    error_message=f"Invalid output path: {output_path}"
                )
            
            # Ensure the directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:  # Only create directory if there's a directory component
                os.makedirs(output_dir, exist_ok=True)
            
            # Convert path to ASCII string safely and write
            try:
                ascii_path = TCollection_AsciiString(str(output_path).encode('ascii', 'replace').decode('ascii'))
                write_status = writer.Write(ascii_path)
            except Exception as occ_error:
                # OpenCASCADE internal error
                return STEPExportResult(
                    success=False,
                    error_message=f"OpenCASCADE STEP write error: {str(occ_error)}"
                )
            if write_status != IFSelect_ReturnStatus.IFSelect_RetDone:
                return STEPExportResult(
                    success=False,
                    error_message=f"Failed to write STEP file: {write_status}"
                )
            
            # Get file size
            file_size = None
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
            
            if self.debug_mode:
                print(f"Successfully exported shell to {output_path} ({file_size} bytes)")
            
            return STEPExportResult(
                success=True,
                file_path=output_path,
                shapes_exported=1,
                file_size_bytes=file_size
            )
            
        except Exception as e:
            return STEPExportResult(
                success=False,
                error_message=f"STEP export failed: {str(e)}"
            )
    
    def export_compound(self, compound: TopoDS_Compound, output_path: str) -> STEPExportResult:
        """
        Export a compound shape (multiple buildings) to STEP format
        
        Args:
            compound: OpenCASCADE compound containing multiple shapes
            output_path: Output file path
            
        Returns:
            STEPExportResult with export status
        """
        try:
            # Validate compound before export
            if compound is None:
                return STEPExportResult(
                    success=False,
                    error_message="Compound is None"
                )
            
            # Check if compound has any shapes
            shape_count = self._count_shapes_in_compound(compound)
            if shape_count == 0:
                return STEPExportResult(
                    success=False,
                    error_message="Compound contains no shapes"
                )
            
            if self.debug_mode:
                print(f"Exporting compound with {shape_count} shapes to {output_path}")
            
            writer = STEPControl_Writer()
            
            # Set up the STEP writer more explicitly
            Interface_Static.SetCVal("write.step.units", "MM")
            Interface_Static.SetCVal("write.precision.val", "0.01")
            Interface_Static.SetIVal("write.step.nonmanifold", 1)
            
            # Add the compound to the writer
            status = writer.Transfer(compound, STEPControl_AsIs)
            if status != IFSelect_ReturnStatus.IFSelect_RetDone:
                return STEPExportResult(
                    success=False,
                    error_message=f"Failed to transfer compound to STEP writer: {status}"
                )
            
            # Write to file with fallback methods
            if not output_path or not isinstance(output_path, str):
                return STEPExportResult(
                    success=False,
                    error_message=f"Invalid output path: {output_path}"
                )
            
            # Ensure the directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Try different write methods
            write_status = None
            
            try:
                # Method 1: Simple approach
                ascii_path = TCollection_AsciiString(str(output_path))
                write_status = writer.Write(ascii_path)
                if self.debug_mode:
                    print(f"Write attempt 1 result: {write_status}")
            except Exception as e1:
                if self.debug_mode:
                    print(f"Write method 1 failed: {e1}")
                
                try:
                    # Method 2: Use temp file
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.step', delete=False) as temp_file:
                        temp_path = temp_file.name
                    
                    ascii_path = TCollection_AsciiString(temp_path)
                    write_status = writer.Write(ascii_path)
                    
                    if write_status == IFSelect_ReturnStatus.IFSelect_RetDone:
                        import shutil
                        shutil.move(temp_path, output_path)
                        if self.debug_mode:
                            print(f"Successfully wrote via temp file")
                    
                except Exception as e2:
                    return STEPExportResult(
                        success=False,
                        error_message=f"All write methods failed. Last: {e2}, First: {e1}"
                    )
            
            if write_status != IFSelect_ReturnStatus.IFSelect_RetDone:
                return STEPExportResult(
                    success=False,
                    error_message=f"STEP write failed with status: {write_status}"
                )
            
            # Count shapes in compound
            shape_count = self._count_shapes_in_compound(compound)
            
            # Get file size
            file_size = None
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
            
            if self.debug_mode:
                print(f"Successfully exported compound with {shape_count} shapes to {output_path} ({file_size} bytes)")
            
            return STEPExportResult(
                success=True,
                file_path=output_path,
                shapes_exported=shape_count,
                file_size_bytes=file_size
            )
            
        except Exception as e:
            return STEPExportResult(
                success=False,
                error_message=f"STEP export failed: {str(e)}"
            )
    
    def export_solidification_results(self, results: List[SolidificationResult], 
                                    output_path: str) -> STEPExportResult:
        """
        Export multiple solidification results to a single STEP file
        
        Args:
            results: List of solidification results
            output_path: Output file path
            
        Returns:
            STEPExportResult with export status
        """
        try:
            if not results:
                return STEPExportResult(
                    success=False,
                    error_message="No solidification results to export"
                )
            
            # Filter successful results
            successful_results = [r for r in results if r.success]
            if not successful_results:
                return STEPExportResult(
                    success=False,
                    error_message="No successful solidification results to export"
                )
            
            # If only one result, export directly
            if len(successful_results) == 1:
                result = successful_results[0]
                if result.solid is not None:
                    return self.export_single_solid(result.solid, output_path)
                elif result.shell is not None:
                    return self.export_shell(result.shell, output_path)
                elif result.compound is not None:
                    return self.export_compound(result.compound, output_path)
            
            # Multiple results - create compound
            compound = self._create_compound_from_results(successful_results)
            if compound is None:
                return STEPExportResult(
                    success=False,
                    error_message="Failed to create compound from results"
                )
            
            return self.export_compound(compound, output_path)
            
        except Exception as e:
            return STEPExportResult(
                success=False,
                error_message=f"Export failed: {str(e)}"
            )
    
    def export_individual_buildings(self, results: List[SolidificationResult],
                                  output_directory: str) -> List[STEPExportResult]:
        """
        Export each building to individual STEP files
        
        Args:
            results: List of solidification results
            output_directory: Directory to save individual files
            
        Returns:
            List of STEPExportResult for each building
        """
        export_results = []
        
        # Ensure output directory exists
        os.makedirs(output_directory, exist_ok=True)
        
        for i, result in enumerate(results):
            if not result.success:
                export_results.append(STEPExportResult(
                    success=False,
                    error_message=f"Building {i} solidification failed"
                ))
                continue
            
            # Generate filename
            filename = f"building_{i:03d}.step"
            output_path = os.path.join(output_directory, filename)
            
            # Export based on available geometry
            if result.solid is not None:
                export_result = self.export_single_solid(result.solid, output_path, f"Building_{i}")
            elif result.shell is not None:
                export_result = self.export_shell(result.shell, output_path, f"Building_{i}")
            else:
                export_result = STEPExportResult(
                    success=False,
                    error_message=f"Building {i} has no exportable geometry"
                )
            
            export_results.append(export_result)
        
        return export_results
    
    def _create_compound_from_results(self, results: List[SolidificationResult]) -> Optional[TopoDS_Compound]:
        """Create compound from solidification results"""
        try:
            builder = BRep_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            
            shape_count = 0
            for result in results:
                if result.solid is not None:
                    builder.Add(compound, result.solid)
                    shape_count += 1
                elif result.shell is not None:
                    builder.Add(compound, result.shell)
                    shape_count += 1
                elif result.compound is not None:
                    builder.Add(compound, result.compound)
                    shape_count += 1
            
            if shape_count > 0:
                return compound
            
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error creating compound: {e}")
            return None
    
    def _count_shapes_in_compound(self, compound: TopoDS_Compound) -> int:
        """Count the number of shapes in a compound"""
        try:
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_SHELL
            
            # Count solids
            solid_exp = TopExp_Explorer(compound, TopAbs_SOLID)
            solid_count = 0
            while solid_exp.More():
                solid_count += 1
                solid_exp.Next()
            
            # Count shells (if no solids)
            if solid_count == 0:
                shell_exp = TopExp_Explorer(compound, TopAbs_SHELL)
                shell_count = 0
                while shell_exp.More():
                    shell_count += 1
                    shell_exp.Next()
                return shell_count
            
            return solid_count
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error counting shapes: {e}")
            return 0
    
    def create_temporary_step_file(self, prefix: str = "citygml_export") -> str:
        """Create a temporary STEP file path"""
        temp_dir = tempfile.mkdtemp()
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.step"
        return os.path.join(temp_dir, filename)
    
    def validate_step_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a STEP file and return information about it
        
        Args:
            file_path: Path to STEP file
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            "is_valid": False,
            "file_exists": False,
            "file_size": 0,
            "error_message": None
        }
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                validation_result["error_message"] = "File does not exist"
                return validation_result
            
            validation_result["file_exists"] = True
            validation_result["file_size"] = os.path.getsize(file_path)
            
            # Try to read the STEP file header
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.read(1000)  # Read first 1000 characters
                
                if "ISO-10303" in header and "STEP" in header:
                    validation_result["is_valid"] = True
                else:
                    validation_result["error_message"] = "Invalid STEP file format"
            
            return validation_result
            
        except Exception as e:
            validation_result["error_message"] = f"Validation error: {str(e)}"
            return validation_result
    
    def get_export_statistics(self, results: List[STEPExportResult]) -> Dict[str, Any]:
        """Get statistics from export results"""
        successful = sum(1 for r in results if r.success)
        total_shapes = sum(r.shapes_exported for r in results if r.success)
        total_size = sum(r.file_size_bytes for r in results if r.success and r.file_size_bytes)
        
        stats = {
            "total_exports": len(results),
            "successful_exports": successful,
            "failed_exports": len(results) - successful,
            "success_rate": successful / len(results) if results else 0,
            "total_shapes_exported": total_shapes,
            "total_file_size_bytes": total_size,
            "average_file_size_bytes": total_size / successful if successful > 0 else 0
        }
        
        return stats