"""
CityJSON Solidifier Module

This module converts CityJSON building data to OpenCASCADE B-Rep solids.
It handles face orientation, holes, sewing, and solid creation with improved
accuracy and robustness compared to direct CityGML processing.
"""

import math
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from config import OCCT_AVAILABLE
from core.cityjson_converter import CityJSONBuilding

if OCCT_AVAILABLE:
    from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Pln, gp_Ax3
    from OCC.Core.BRepBuilderAPI import (
        BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing, 
        BRepBuilderAPI_MakeSolid
    )
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.ShapeFix import ShapeFix_Shape, ShapeFix_Wire, ShapeFix_Face
    from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
    from OCC.Core.TopoDS import (
        TopoDS_Face, TopoDS_Shell, TopoDS_Solid, 
        TopoDS_Compound, TopoDS_Wire, topods_Shell
    )
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopAbs import TopAbs_IN, TopAbs_OUT, TopAbs_ON


@dataclass
class CityJSONSolidificationResult:
    """Result of CityJSON to B-Rep solidification"""
    success: bool
    building_id: str
    solid: Optional[TopoDS_Solid] = None
    shell: Optional[TopoDS_Shell] = None
    compound: Optional[TopoDS_Compound] = None
    faces: List[TopoDS_Face] = None
    error_message: Optional[str] = None
    face_count: int = 0
    is_closed: bool = False
    is_valid: bool = False
    processing_time: float = 0.0


class CityJSONSolidifier:
    """
    Converts CityJSON building data to OpenCASCADE B-Rep solids.
    Implements improved face orientation, hole handling, and sewing.
    """
    
    def __init__(self, tolerance: float = 1e-5):
        """
        Initialize solidifier with geometric tolerance
        
        Args:
            tolerance: Geometric tolerance for sewing and validation (default: 1e-5m for building scale)
        """
        if not OCCT_AVAILABLE:
            raise RuntimeError("OpenCASCADE Technology is required for solidification")
        
        self.tolerance = tolerance
        self.debug_mode = False
        self.fix_orientation = True  # Auto-fix face orientations
        self.enable_healing = True    # Enable shape healing
        
    def enable_debug(self, enabled: bool = True):
        """Enable debug mode for detailed logging"""
        self.debug_mode = enabled
    
    def solidify_building(self, building: CityJSONBuilding, 
                         surfaces: List[List[List[Tuple[float, float, float]]]]) -> CityJSONSolidificationResult:
        """
        Convert a CityJSON building to B-Rep solid
        
        Args:
            building: CityJSONBuilding object
            surfaces: List of surfaces, each surface has rings (outer + holes)
                     Format: [[[outer_ring], [hole1], [hole2], ...], ...]
            
        Returns:
            CityJSONSolidificationResult with B-Rep solid or shell
        """
        start_time = time.time()
        
        try:
            if self.debug_mode:
                print(f"Solidifying building {building.building_id}")
                print(f"Number of surfaces: {len(surfaces)}")
            
            # Create faces from surfaces
            faces = []
            for i, surface_rings in enumerate(surfaces):
                try:
                    face = self._create_face_from_rings(surface_rings)
                    if face:
                        faces.append(face)
                        if self.debug_mode:
                            print(f"Created face {i+1}/{len(surfaces)}")
                except Exception as e:
                    if self.debug_mode:
                        print(f"Failed to create face {i+1}: {e}")
                    continue
            
            if not faces:
                return CityJSONSolidificationResult(
                    success=False,
                    building_id=building.building_id,
                    error_message="No valid faces could be created",
                    processing_time=time.time() - start_time
                )
            
            if self.debug_mode:
                print(f"Created {len(faces)} faces from {len(surfaces)} surfaces")
            
            # Sew faces together
            sewing = BRepBuilderAPI_Sewing(self.tolerance)
            for face in faces:
                sewing.Add(face)
            
            sewing.Perform()
            sewed_shape = sewing.SewedShape()
            
            # Try to create shell and solid
            shell = None
            solid = None
            
            try:
                shell = topods_Shell(sewed_shape)
                
                # Check if shell is closed
                analyzer = BRepCheck_Analyzer(shell)
                is_closed = analyzer.IsValid()
                
                if is_closed:
                    # Try to create solid from closed shell
                    try:
                        solid_maker = BRepBuilderAPI_MakeSolid(shell)
                        if solid_maker.IsDone():
                            solid = solid_maker.Solid()
                            
                            # Apply healing if enabled
                            if self.enable_healing:
                                solid = self._heal_shape(solid)
                            
                            # Validate solid
                            is_valid = self._validate_solid(solid)
                            
                            if self.debug_mode:
                                print(f"Created solid for building {building.building_id}")
                                print(f"Solid is valid: {is_valid}")
                            
                            return CityJSONSolidificationResult(
                                success=True,
                                building_id=building.building_id,
                                solid=solid,
                                shell=shell,
                                faces=faces,
                                face_count=len(faces),
                                is_closed=True,
                                is_valid=is_valid,
                                processing_time=time.time() - start_time
                            )
                    except Exception as e:
                        if self.debug_mode:
                            print(f"Could not create solid: {e}")
                
                # Return shell if solid creation failed
                if self.debug_mode:
                    print(f"Returning shell for building {building.building_id}")
                
                return CityJSONSolidificationResult(
                    success=True,
                    building_id=building.building_id,
                    shell=shell,
                    faces=faces,
                    face_count=len(faces),
                    is_closed=is_closed,
                    is_valid=analyzer.IsValid(),
                    processing_time=time.time() - start_time
                )
                
            except Exception as e:
                # If shell creation failed, create compound from faces
                if self.debug_mode:
                    print(f"Could not create shell, creating compound: {e}")
                
                builder = BRep_Builder()
                compound = TopoDS_Compound()
                builder.MakeCompound(compound)
                
                for face in faces:
                    builder.Add(compound, face)
                
                return CityJSONSolidificationResult(
                    success=True,
                    building_id=building.building_id,
                    compound=compound,
                    faces=faces,
                    face_count=len(faces),
                    is_closed=False,
                    is_valid=False,
                    processing_time=time.time() - start_time
                )
                
        except Exception as e:
            if self.debug_mode:
                print(f"Solidification failed for {building.building_id}: {e}")
            
            return CityJSONSolidificationResult(
                success=False,
                building_id=building.building_id,
                error_message=str(e),
                processing_time=time.time() - start_time
            )
    
    def _create_face_from_rings(self, rings: List[List[Tuple[float, float, float]]]) -> Optional[TopoDS_Face]:
        """
        Create a face from rings (outer boundary + holes)
        
        Args:
            rings: List of rings, first is outer boundary, rest are holes
                  Each ring is a list of (x, y, z) tuples
        
        Returns:
            TopoDS_Face or None if creation failed
        """
        if not rings or not rings[0]:
            return None
        
        outer_ring = rings[0]
        
        # Check and fix ring orientation if needed
        if self.fix_orientation:
            outer_ring = self._ensure_correct_orientation(outer_ring)
        
        # Create outer wire
        outer_wire = self._create_wire_from_ring(outer_ring)
        if not outer_wire:
            return None
        
        # Fix wire if needed
        if self.enable_healing:
            wire_fix = ShapeFix_Wire(outer_wire, TopoDS_Face(), self.tolerance)
            wire_fix.Perform()
            outer_wire = wire_fix.Wire()
        
        # Create face from outer wire
        try:
            face_maker = BRepBuilderAPI_MakeFace(outer_wire)
            if not face_maker.IsDone():
                # Try with planar approximation
                face_maker = self._create_face_with_plane(outer_ring)
                if not face_maker or not face_maker.IsDone():
                    return None
            
            face = face_maker.Face()
            
            # Add holes if present
            if len(rings) > 1:
                for hole_ring in rings[1:]:
                    # Holes should have opposite orientation
                    hole_ring_reversed = list(reversed(hole_ring))
                    hole_wire = self._create_wire_from_ring(hole_ring_reversed)
                    if hole_wire:
                        face_maker.Add(hole_wire)
                
                face = face_maker.Face()
            
            # Fix face if needed
            if self.enable_healing:
                face_fix = ShapeFix_Face(face)
                face_fix.Perform()
                face = face_fix.Face()
            
            return face
            
        except Exception as e:
            if self.debug_mode:
                print(f"Face creation failed: {e}")
            return None
    
    def _create_wire_from_ring(self, ring: List[Tuple[float, float, float]]) -> Optional[TopoDS_Wire]:
        """
        Create a wire from a ring of vertices
        
        Args:
            ring: List of (x, y, z) tuples forming a closed ring
            
        Returns:
            TopoDS_Wire or None if creation failed
        """
        if len(ring) < 3:
            return None
        
        try:
            wire_maker = BRepBuilderAPI_MakeWire()
            
            # Create edges between consecutive vertices
            points = [gp_Pnt(x, y, z) for x, y, z in ring]
            
            # Ensure ring is closed
            if ring[0] != ring[-1]:
                points.append(points[0])
            
            for i in range(len(points) - 1):
                edge = BRepBuilderAPI_MakeEdge(points[i], points[i + 1]).Edge()
                wire_maker.Add(edge)
            
            if wire_maker.IsDone():
                return wire_maker.Wire()
            
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Wire creation failed: {e}")
            return None
    
    def _ensure_correct_orientation(self, ring: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """
        Ensure ring has correct orientation (CCW when viewed from outside)
        
        Args:
            ring: List of vertices forming a ring
            
        Returns:
            Correctly oriented ring
        """
        if len(ring) < 3:
            return ring
        
        # Calculate normal using first 3 non-collinear points
        normal = self._calculate_polygon_normal(ring)
        
        # Calculate signed area
        signed_area = self._calculate_signed_area(ring, normal)
        
        # If area is negative, reverse the ring
        if signed_area < 0:
            return list(reversed(ring))
        
        return ring
    
    def _calculate_polygon_normal(self, ring: List[Tuple[float, float, float]]) -> np.ndarray:
        """
        Calculate polygon normal vector
        
        Args:
            ring: List of vertices
            
        Returns:
            Normal vector as numpy array
        """
        if len(ring) < 3:
            return np.array([0, 0, 1])
        
        # Use Newell's method for robust normal calculation
        normal = np.array([0.0, 0.0, 0.0])
        
        for i in range(len(ring)):
            v1 = np.array(ring[i])
            v2 = np.array(ring[(i + 1) % len(ring)])
            
            normal[0] += (v1[1] - v2[1]) * (v1[2] + v2[2])
            normal[1] += (v1[2] - v2[2]) * (v1[0] + v2[0])
            normal[2] += (v1[0] - v2[0]) * (v1[1] + v2[1])
        
        # Normalize
        length = np.linalg.norm(normal)
        if length > 0:
            normal = normal / length
        else:
            # Default to Z+ if calculation fails
            normal = np.array([0, 0, 1])
        
        return normal
    
    def _calculate_signed_area(self, ring: List[Tuple[float, float, float]], normal: np.ndarray) -> float:
        """
        Calculate signed area of polygon
        
        Args:
            ring: List of vertices
            normal: Normal vector
            
        Returns:
            Signed area (positive if CCW, negative if CW)
        """
        if len(ring) < 3:
            return 0.0
        
        # Project to 2D plane perpendicular to normal
        # Choose projection plane based on dominant normal component
        abs_normal = np.abs(normal)
        if abs_normal[2] >= abs_normal[0] and abs_normal[2] >= abs_normal[1]:
            # Project to XY plane
            proj_indices = (0, 1)
        elif abs_normal[1] >= abs_normal[0]:
            # Project to XZ plane
            proj_indices = (0, 2)
        else:
            # Project to YZ plane
            proj_indices = (1, 2)
        
        # Calculate 2D signed area
        area = 0.0
        for i in range(len(ring)):
            v1 = ring[i]
            v2 = ring[(i + 1) % len(ring)]
            area += (v2[proj_indices[0]] - v1[proj_indices[0]]) * (v2[proj_indices[1]] + v1[proj_indices[1]])
        
        return area * 0.5
    
    def _create_face_with_plane(self, ring: List[Tuple[float, float, float]]) -> Optional[BRepBuilderAPI_MakeFace]:
        """
        Create face using planar approximation
        
        Args:
            ring: List of vertices
            
        Returns:
            Face maker or None
        """
        try:
            # Calculate best-fit plane
            points = np.array(ring)
            centroid = np.mean(points, axis=0)
            
            # Use SVD to find best-fit plane
            centered = points - centroid
            _, _, vh = np.linalg.svd(centered.T)
            normal = vh[2]
            
            # Create plane
            origin = gp_Pnt(centroid[0], centroid[1], centroid[2])
            direction = gp_Dir(normal[0], normal[1], normal[2])
            plane = gp_Pln(origin, direction)
            
            # Create wire
            wire = self._create_wire_from_ring(ring)
            if not wire:
                return None
            
            # Create face on plane
            face_maker = BRepBuilderAPI_MakeFace(plane, wire)
            return face_maker if face_maker.IsDone() else None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Planar face creation failed: {e}")
            return None
    
    def _heal_shape(self, shape):
        """
        Apply shape healing to improve quality
        
        Args:
            shape: Input shape (solid, shell, or face)
            
        Returns:
            Healed shape
        """
        try:
            fixer = ShapeFix_Shape(shape)
            fixer.SetPrecision(self.tolerance)
            fixer.SetMaxTolerance(self.tolerance * 10)
            fixer.Perform()
            return fixer.Shape()
        except Exception as e:
            if self.debug_mode:
                print(f"Shape healing failed: {e}")
            return shape
    
    def _validate_solid(self, solid: TopoDS_Solid) -> bool:
        """
        Validate solid using OpenCASCADE checks
        
        Args:
            solid: Solid to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check structural validity
            analyzer = BRepCheck_Analyzer(solid)
            if not analyzer.IsValid():
                return False
            
            # Check if solid is closed
            classifier = BRepClass3d_SolidClassifier(solid)
            classifier.PerformInfinitePoint(self.tolerance)
            state = classifier.State()
            
            # Solid should classify infinite point as outside
            return state == TopAbs_OUT
            
        except Exception as e:
            if self.debug_mode:
                print(f"Solid validation failed: {e}")
            return False
    
    def convert_multiple_buildings(self, buildings_data: List[Tuple[CityJSONBuilding, List[List[List[Tuple[float, float, float]]]]]]) -> List[CityJSONSolidificationResult]:
        """
        Convert multiple CityJSON buildings to B-Rep solids
        
        Args:
            buildings_data: List of (building, surfaces) tuples
            
        Returns:
            List of solidification results
        """
        results = []
        
        for i, (building, surfaces) in enumerate(buildings_data):
            if self.debug_mode:
                print(f"Processing building {i+1}/{len(buildings_data)}: {building.building_id}")
            
            result = self.solidify_building(building, surfaces)
            results.append(result)
            
            if self.debug_mode:
                if result.success:
                    shape_type = "solid" if result.solid else ("shell" if result.shell else "compound")
                    print(f"Successfully created {shape_type} with {result.face_count} faces")
                else:
                    print(f"Failed: {result.error_message}")
        
        return results
    
    def get_conversion_statistics(self, results: List[CityJSONSolidificationResult]) -> Dict[str, Any]:
        """
        Get statistics from conversion results
        
        Args:
            results: List of solidification results
            
        Returns:
            Dictionary with conversion statistics
        """
        stats = {
            "total_buildings": len(results),
            "successful_conversions": sum(1 for r in results if r.success),
            "solids_created": sum(1 for r in results if r.solid is not None),
            "shells_created": sum(1 for r in results if r.shell is not None),
            "compounds_created": sum(1 for r in results if r.compound is not None),
            "total_faces": sum(r.face_count for r in results),
            "closed_shells": sum(1 for r in results if r.is_closed),
            "valid_solids": sum(1 for r in results if r.is_valid),
            "average_processing_time": np.mean([r.processing_time for r in results]) if results else 0
        }
        
        # Error analysis
        errors = [r.error_message for r in results if not r.success and r.error_message]
        if errors:
            stats["common_errors"] = list(set(errors))[:5]  # Top 5 unique errors
        
        return stats