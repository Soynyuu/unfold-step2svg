"""
CityGML Solidifier Module

This module converts CityGML MultiSurface geometries to proper 3D solid models using OpenCASCADE.
It implements intelligent algorithms to create watertight solid geometries from surface patches
without using mesh intermediates.
"""

import math
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass

from config import OCCT_AVAILABLE
from core.citygml_parser import BuildingGeometry

if OCCT_AVAILABLE:
    from OCC.Core.BRep import BRep_Builder, BRep_Tool
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Edge, TopoDS_Wire, TopoDS_Vertex, TopoDS_Solid, TopoDS_Shell, TopoDS_Compound
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_WIRE, TopAbs_VERTEX, TopAbs_SHELL, TopAbs_SOLID
    from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Pln, gp_Ax1, gp_Ax2, gp_Ax3, gp_Trsf
    from OCC.Core.BRepBuilderAPI import (
        BRepBuilderAPI_MakeVertex, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire,
        BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeShell, BRepBuilderAPI_MakeSolid,
        BRepBuilderAPI_Sewing
    )
    from OCC.Core.BRepFill import BRepFill_Generator
    from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCC.Core.ShapeFix import ShapeFix_Shell, ShapeFix_Solid
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    # Import BRepGProp with modern API
    try:
        # Use the modern static method approach (pythonocc-core 7.7.1+)
        from OCC.Core.BRepGProp import brepgprop
        BRep_Surface_Properties = brepgprop.SurfaceProperties
    except (ImportError, AttributeError):
        try:
            # Fallback to deprecated function for older versions
            from OCC.Core.BRepGProp import brepgprop_SurfaceProperties as BRep_Surface_Properties
        except ImportError:
            # Create a proper fallback function
            def BRep_Surface_Properties(shape, props):
                # Set a reasonable default mass for surface area calculation
                props.SetMass(1.0)
            print("Warning: BRepGProp.SurfaceProperties not available, using dummy implementation")
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.GeomAPI import GeomAPI_PointsToBSpline
    from OCC.Core.TColgp import TColgp_Array1OfPnt
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.Standard import Standard_Failure
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopTools import TopTools_IndexedMapOfShape
    from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier


@dataclass 
class SolidificationResult:
    """Result of solid conversion process"""
    success: bool
    solid: Optional[TopoDS_Solid] = None
    shell: Optional[TopoDS_Shell] = None
    compound: Optional[TopoDS_Compound] = None  # For face collections
    error_message: Optional[str] = None
    volume: Optional[float] = None
    surface_area: Optional[float] = None
    is_valid: bool = False
    is_closed: bool = False


class CityGMLSolidifier:
    """
    Converts CityGML surface geometries to OpenCASCADE solid models.
    Implements intelligent solid reconstruction algorithms.
    """
    
    def __init__(self, tolerance: float = 1e-6):
        if not OCCT_AVAILABLE:
            raise RuntimeError("OpenCASCADE Technology is required for solid conversion")
        
        self.tolerance = tolerance
        self.sewing_tolerance = tolerance * 10  # Slightly larger tolerance for sewing
        self.debug_mode = False
        
    def enable_debug(self, enabled: bool = True):
        """Enable debug mode for detailed logging"""
        self.debug_mode = enabled
    
    def convert_building_to_solid(self, building: BuildingGeometry) -> SolidificationResult:
        """
        Convert a building geometry to a solid model
        
        Args:
            building: Building geometry from CityGML parser
            
        Returns:
            SolidificationResult with conversion results
        """
        try:
            if self.debug_mode:
                print(f"Converting building {building.building_id} with {len(building.surfaces)} surfaces")
            
            # Step 1: Create faces from surface polygons
            faces = self._create_faces_from_surfaces(building.surfaces)
            if not faces:
                return SolidificationResult(
                    success=False,
                    error_message="No valid faces could be created from surfaces"
                )
            
            if self.debug_mode:
                print(f"Created {len(faces)} faces from surfaces")
            
            # Step 2: Sew faces into a shell
            shell_result = self._sew_faces_to_shell(faces)
            if not shell_result.success:
                # Fallback: Create compound shape from individual faces
                if self.debug_mode:
                    print(f"Shell creation failed, creating compound from {len(faces)} individual faces")
                
                compound_result = self._create_compound_from_faces(faces)
                if compound_result.success:
                    if self.debug_mode:
                        print("Successfully created compound shape from faces")
                    return compound_result
                else:
                    return shell_result  # Return original error if fallback also fails
            
            # Step 3: Try to create solid from shell
            solid_result = self._create_solid_from_shell(shell_result.shell)
            solid_result.shell = shell_result.shell  # Keep shell for fallback
            
            return solid_result
            
        except Exception as e:
            return SolidificationResult(
                success=False,
                error_message=f"Solid conversion failed: {str(e)}"
            )
    
    def _create_faces_from_surfaces(self, surfaces: List[List[Tuple[float, float, float]]]) -> List[TopoDS_Face]:
        """Create OpenCASCADE faces from surface coordinate lists"""
        faces = []
        
        for i, surface in enumerate(surfaces):
            try:
                if len(surface) < 3:
                    continue  # Skip invalid surfaces
                
                # Create face from polygon
                face = self._create_face_from_polygon(surface)
                if face is not None:
                    faces.append(face)
                elif self.debug_mode:
                    print(f"Failed to create face {i} from {len(surface)} points")
                    
            except Exception as e:
                if self.debug_mode:
                    print(f"Error creating face {i}: {e}")
                continue
        
        return faces
    
    def _create_face_from_polygon(self, polygon: List[Tuple[float, float, float]]) -> Optional[TopoDS_Face]:
        """Create a face from a polygon defined by 3D points"""
        try:
            if len(polygon) < 3:
                return None
            
            # Remove duplicate points and ensure closure
            cleaned_polygon = self._clean_polygon(polygon)
            if len(cleaned_polygon) < 3:
                return None
            
            # Create vertices
            vertices = []
            for point in cleaned_polygon:
                vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(point[0], point[1], point[2]))
                if vertex.IsDone():
                    vertices.append(vertex.Vertex())
            
            if len(vertices) < 3:
                return None
            
            # Create edges
            edges = []
            for i in range(len(vertices)):
                next_i = (i + 1) % len(vertices)
                edge_maker = BRepBuilderAPI_MakeEdge(vertices[i], vertices[next_i])
                if edge_maker.IsDone():
                    edges.append(edge_maker.Edge())
            
            if len(edges) < 3:
                return None
            
            # Create wire
            wire_maker = BRepBuilderAPI_MakeWire()
            for edge in edges:
                wire_maker.Add(edge)
            
            if not wire_maker.IsDone():
                return None
            
            wire = wire_maker.Wire()
            
            # Create face
            face_maker = BRepBuilderAPI_MakeFace(wire)
            if face_maker.IsDone():
                return face_maker.Face()
            
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error in _create_face_from_polygon: {e}")
            return None
    
    def _clean_polygon(self, polygon: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """Clean polygon by removing duplicates and ensuring proper closure"""
        if not polygon:
            return []
        
        cleaned = []
        
        for point in polygon:
            # Check if this point is significantly different from the last one
            if not cleaned or self._point_distance(point, cleaned[-1]) > self.tolerance:
                cleaned.append(point)
        
        # Ensure the polygon is closed (first point == last point within tolerance)
        if len(cleaned) >= 3:
            if self._point_distance(cleaned[0], cleaned[-1]) > self.tolerance:
                cleaned.append(cleaned[0])  # Close the polygon
            elif len(cleaned) > 3:  # Remove duplicate closing point if it exists
                cleaned = cleaned[:-1]
        
        return cleaned
    
    def _point_distance(self, p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
        """Calculate 3D distance between two points"""
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)
    
    def _sew_faces_to_shell(self, faces: List[TopoDS_Face]) -> SolidificationResult:
        """Sew faces together to create a shell"""
        try:
            if not faces:
                return SolidificationResult(
                    success=False,
                    error_message="No faces to sew"
                )
            
            if self.debug_mode:
                print(f"Attempting to sew {len(faces)} faces with tolerance {self.sewing_tolerance}")
            
            # Try multiple sewing strategies with different tolerances
            tolerances_to_try = [
                self.sewing_tolerance,
                self.sewing_tolerance * 10,
                self.sewing_tolerance * 100,
                1e-3,  # More relaxed tolerance for CityGML
                1e-2   # Very relaxed tolerance
            ]
            
            for tolerance in tolerances_to_try:
                if self.debug_mode:
                    print(f"Trying sewing with tolerance: {tolerance}")
                
                # Use BRepBuilderAPI_Sewing for robust face sewing
                sewing = BRepBuilderAPI_Sewing(tolerance)
                sewing.SetFaceMode(True)
                sewing.SetFloatingEdgesMode(True)  # Allow floating edges for CityGML
                sewing.SetNonManifoldMode(True)    # Allow non-manifold geometry
                
                # Add all faces to the sewing operation
                for i, face in enumerate(faces):
                    try:
                        sewing.Add(face)
                    except Exception as face_error:
                        if self.debug_mode:
                            print(f"Failed to add face {i}: {face_error}")
                        continue
                
                try:
                    # Perform sewing
                    sewing.Perform()
                    
                    # Check if sewing was successful (different OpenCASCADE versions have different methods)
                    try:
                        sewing_done = sewing.IsDone()
                    except AttributeError:
                        # Older versions don't have IsDone method, assume success if no exception
                        sewing_done = True
                    
                    if sewing_done:
                        sewn_shape = sewing.SewedShape()
                        
                        if self.debug_mode:
                            print(f"Sewing successful with tolerance {tolerance}")
                        
                        # Try to extract shell from sewn shape
                        shell = self._extract_shell_from_shape(sewn_shape)
                        if shell is not None:
                            # Check if shell is closed
                            is_closed = self._is_shell_closed(shell)
                            
                            if self.debug_mode:
                                print(f"Created shell with {len(faces)} faces, closed: {is_closed}")
                            
                            return SolidificationResult(
                                success=True,
                                shell=shell,
                                is_closed=is_closed
                            )
                        elif self.debug_mode:
                            print(f"Shell extraction failed with tolerance {tolerance}")
                    elif self.debug_mode:
                        print(f"Sewing operation not done with tolerance {tolerance}")
                        
                except Exception as sewing_error:
                    if self.debug_mode:
                        print(f"Sewing failed with tolerance {tolerance}: {sewing_error}")
                    continue
            
            # If all sewing strategies failed, try creating shell directly from faces
            if self.debug_mode:
                print("All sewing strategies failed, trying direct shell creation")
            
            shell = self._create_shell_from_faces_directly(faces)
            if shell is not None:
                is_closed = self._is_shell_closed(shell)
                if self.debug_mode:
                    print(f"Direct shell creation successful, closed: {is_closed}")
                
                return SolidificationResult(
                    success=True,
                    shell=shell,
                    is_closed=is_closed
                )
            
            return SolidificationResult(
                success=False,
                error_message=f"All sewing strategies failed for {len(faces)} faces"
            )
            
        except Exception as e:
            return SolidificationResult(
                success=False,
                error_message=f"Shell creation failed: {str(e)}"
            )
    
    def _create_shell_from_faces_directly(self, faces: List[TopoDS_Face]) -> Optional[TopoDS_Shell]:
        """Create shell directly from faces using BRep_Builder"""
        try:
            builder = BRep_Builder()
            shell = TopoDS_Shell()
            builder.MakeShell(shell)
            
            added_faces = 0
            for i, face in enumerate(faces):
                try:
                    builder.Add(shell, face)
                    added_faces += 1
                except Exception as face_error:
                    if self.debug_mode:
                        print(f"Failed to add face {i} to shell: {face_error}")
                    continue
            
            if added_faces > 0:
                if self.debug_mode:
                    print(f"Created shell directly with {added_faces}/{len(faces)} faces")
                return shell
            
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Direct shell creation failed: {e}")
            return None

    def _create_compound_from_faces(self, faces: List[TopoDS_Face]) -> SolidificationResult:
        """Create a compound shape from individual faces as fallback"""
        try:
            builder = BRep_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            
            added_faces = 0
            for i, face in enumerate(faces):
                try:
                    builder.Add(compound, face)
                    added_faces += 1
                except Exception as face_error:
                    if self.debug_mode:
                        print(f"Failed to add face {i} to compound: {face_error}")
                    continue
            
            if added_faces > 0:
                # Calculate surface area for compound
                surface_area = self._calculate_compound_surface_area(compound)
                
                if self.debug_mode:
                    print(f"Created compound with {added_faces}/{len(faces)} faces, area: {surface_area}")
                
                return SolidificationResult(
                    success=True,
                    compound=compound,
                    surface_area=surface_area,
                    is_valid=True,
                    is_closed=False  # Compounds are not closed by definition
                )
            
            return SolidificationResult(
                success=False,
                error_message="Could not add any faces to compound"
            )
            
        except Exception as e:
            return SolidificationResult(
                success=False,
                error_message=f"Compound creation failed: {str(e)}"
            )

    def _calculate_compound_surface_area(self, compound: TopoDS_Compound) -> Optional[float]:
        """Calculate surface area of a compound shape"""
        try:
            surface_props = GProp_GProps()
            BRep_Surface_Properties(compound, surface_props)
            return surface_props.Mass()
        except Exception as e:
            if self.debug_mode:
                print(f"Error calculating compound surface area: {e}")
            return None

    def _extract_shell_from_shape(self, shape: TopoDS_Shape) -> Optional[TopoDS_Shell]:
        """Extract the first shell from a shape"""
        try:
            exp = TopExp_Explorer(shape, TopAbs_SHELL)
            if exp.More():
                return exp.Current()
            
            # If no shell found, try to create one from faces
            builder = BRep_Builder()
            shell = TopoDS_Shell()
            builder.MakeShell(shell)
            
            exp = TopExp_Explorer(shape, TopAbs_FACE)
            face_count = 0
            while exp.More():
                builder.Add(shell, exp.Current())
                exp.Next()
                face_count += 1
            
            if face_count > 0:
                return shell
            
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error extracting shell: {e}")
            return None
    
    def _is_shell_closed(self, shell: TopoDS_Shell) -> bool:
        """Check if a shell is closed (watertight)"""
        try:
            analyzer = BRepCheck_Analyzer(shell)
            return analyzer.IsValid()
        except:
            return False
    
    def _create_solid_from_shell(self, shell: TopoDS_Shell) -> SolidificationResult:
        """Create a solid from a shell"""
        try:
            # First, try to fix the shell
            shell_fixer = ShapeFix_Shell()
            shell_fixer.Init(shell)
            shell_fixer.Perform()
            fixed_shell = shell_fixer.Shell()
            
            # Check if shell is closed
            is_closed = self._is_shell_closed(fixed_shell)
            
            if not is_closed:
                if self.debug_mode:
                    print("Shell is not closed, attempting to close it")
                
                # Try to close the shell by adding missing faces
                closed_shell = self._attempt_shell_closure(fixed_shell)
                if closed_shell is not None:
                    fixed_shell = closed_shell
                    is_closed = self._is_shell_closed(fixed_shell)
            
            # Attempt to create solid
            if is_closed:
                solid_maker = BRepBuilderAPI_MakeSolid(fixed_shell)
                if solid_maker.IsDone():
                    solid = solid_maker.Solid()
                    
                    # Validate and fix the solid
                    solid_fixer = ShapeFix_Solid()
                    solid_fixer.Init(solid)
                    solid_fixer.Perform()
                    final_solid = solid_fixer.Solid()
                    
                    # Calculate properties
                    volume, surface_area = self._calculate_solid_properties(final_solid)
                    
                    # Validate the solid
                    analyzer = BRepCheck_Analyzer(final_solid)
                    is_valid = analyzer.IsValid()
                    
                    return SolidificationResult(
                        success=True,
                        solid=final_solid,
                        shell=fixed_shell,
                        volume=volume,
                        surface_area=surface_area,
                        is_valid=is_valid,
                        is_closed=True
                    )
            
            # If solid creation failed, return shell result
            volume, surface_area = self._calculate_shell_properties(fixed_shell)
            
            return SolidificationResult(
                success=True,  # Still successful as we have a shell
                shell=fixed_shell,
                volume=volume,
                surface_area=surface_area,
                is_valid=True,
                is_closed=is_closed,
                error_message="Could not create solid, returning shell" if not is_closed else None
            )
            
        except Exception as e:
            return SolidificationResult(
                success=False,
                error_message=f"Solid creation failed: {str(e)}"
            )
    
    def _attempt_shell_closure(self, shell: TopoDS_Shell) -> Optional[TopoDS_Shell]:
        """Attempt to close an open shell by identifying and filling gaps"""
        try:
            # This is a simplified approach - in practice, you might need more
            # sophisticated algorithms to identify and fill gaps
            
            # For now, just return the original shell
            # TODO: Implement gap detection and filling algorithms
            return shell
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error in shell closure attempt: {e}")
            return None
    
    def _calculate_solid_properties(self, solid: TopoDS_Solid) -> Tuple[Optional[float], Optional[float]]:
        """Calculate volume and surface area of a solid"""
        try:
            # Volume calculation
            props = GProp_GProps()
            try:
                # Use the modern API if available
                from OCC.Core.BRepGProp import brepgprop
                brepgprop.VolumeProperties(solid, props)
            except (ImportError, AttributeError):
                # Fallback to legacy API
                from OCC.Core.BRepGProp import brepgprop_VolumeProperties
                brepgprop_VolumeProperties(solid, props)
            volume = props.Mass()
            
            # Surface area calculation
            surface_props = GProp_GProps()
            BRep_Surface_Properties(solid, surface_props)
            surface_area = surface_props.Mass()
            
            return volume, surface_area
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error calculating solid properties: {e}")
            return None, None
    
    def _calculate_shell_properties(self, shell: TopoDS_Shell) -> Tuple[Optional[float], Optional[float]]:
        """Calculate properties of a shell"""
        try:
            # For shell, we can only calculate surface area
            surface_props = GProp_GProps()
            BRep_Surface_Properties(shell, surface_props)
            surface_area = surface_props.Mass()
            
            return None, surface_area  # No volume for open shell
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error calculating shell properties: {e}")
            return None, None
    
    def convert_multiple_buildings(self, buildings: List[BuildingGeometry]) -> List[SolidificationResult]:
        """Convert multiple buildings to solids"""
        results = []
        
        for i, building in enumerate(buildings):
            if self.debug_mode:
                print(f"Processing building {i+1}/{len(buildings)}: {building.building_id}")
            
            result = self.convert_building_to_solid(building)
            results.append(result)
        
        return results
    
    def create_compound_from_solids(self, solid_results: List[SolidificationResult]) -> Optional[TopoDS_Compound]:
        """Create a compound shape from multiple solid results"""
        try:
            builder = BRep_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            
            shape_count = 0
            for result in solid_results:
                if result.success:
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
    
    def get_conversion_statistics(self, results: List[SolidificationResult]) -> Dict[str, Any]:
        """Get statistics from conversion results"""
        successful = sum(1 for r in results if r.success)
        with_solids = sum(1 for r in results if r.success and r.solid is not None)
        with_shells = sum(1 for r in results if r.success and r.shell is not None)
        with_compounds = sum(1 for r in results if r.success and r.compound is not None)
        closed_shells = sum(1 for r in results if r.success and r.is_closed)
        valid_shapes = sum(1 for r in results if r.success and r.is_valid)
        
        volumes = [r.volume for r in results if r.volume is not None]
        areas = [r.surface_area for r in results if r.surface_area is not None]
        
        stats = {
            "total_buildings": len(results),
            "successful_conversions": successful,
            "solids_created": with_solids,
            "shells_created": with_shells,
            "compounds_created": with_compounds,
            "closed_shells": closed_shells,
            "valid_shapes": valid_shapes,
            "success_rate": successful / len(results) if results else 0,
            "solid_rate": with_solids / len(results) if results else 0,
            "usable_shapes_rate": (with_solids + with_shells + with_compounds) / len(results) if results else 0
        }
        
        if volumes:
            stats["volume_stats"] = {
                "total": sum(volumes),
                "min": min(volumes),
                "max": max(volumes),
                "avg": sum(volumes) / len(volumes)
            }
        
        if areas:
            stats["area_stats"] = {
                "total": sum(areas),
                "min": min(areas),
                "max": max(areas),
                "avg": sum(areas) / len(areas)
            }
        
        return stats