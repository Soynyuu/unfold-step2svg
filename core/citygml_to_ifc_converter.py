"""
CityGML to IFC Converter Module

This module converts CityGML building data to IFC (Industry Foundation Classes) format.
It preserves semantic information while converting 3D geometric data for further processing.
"""

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element
import ifcopenshell.util.placement
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from core.citygml_parser import BuildingGeometry


@dataclass
class IFCConversionResult:
    """Result of CityGML to IFC conversion"""
    success: bool
    ifc_file: Optional[ifcopenshell.file] = None
    ifc_file_path: Optional[str] = None
    error_message: Optional[str] = None
    buildings_converted: int = 0
    elements_created: int = 0
    conversion_time: float = 0.0


class CityGMLToIFCConverter:
    """
    Converts CityGML building geometries to IFC format using ifcopenshell.
    Handles semantic mapping from CityGML concepts to IFC entities.
    """
    
    def __init__(self, schema_version: str = "IFC4"):
        """
        Initialize the converter
        
        Args:
            schema_version: IFC schema version (IFC2X3, IFC4, IFC4X3)
        """
        self.schema_version = schema_version
        self.debug_mode = False
        
        # CityGML LoD to IFC representation mapping
        self.lod_mapping = {
            0: "simple_geometry",     # LoD0 -> Simple building blocks
            1: "building_envelope",   # LoD1 -> Building envelope
            2: "detailed_elements",   # LoD2 -> Detailed building elements
            3: "architectural_model"  # LoD3 -> Full architectural model
        }
    
    def enable_debug(self, enabled: bool = True):
        """Enable debug mode for detailed logging"""
        self.debug_mode = enabled
    
    def convert_buildings_to_ifc(self, buildings: List[BuildingGeometry], 
                                output_path: Optional[str] = None) -> IFCConversionResult:
        """
        Convert multiple CityGML buildings to IFC format
        
        Args:
            buildings: List of building geometries from CityGML parser
            output_path: Optional path to save IFC file
            
        Returns:
            IFCConversionResult with conversion status and IFC file
        """
        import time
        start_time = time.time()
        
        try:
            if not buildings:
                return IFCConversionResult(
                    success=False,
                    error_message="No buildings provided for conversion"
                )
            
            if self.debug_mode:
                print(f"Converting {len(buildings)} CityGML buildings to IFC")
            
            # Create new IFC file
            ifc_file = ifcopenshell.file(schema=self.schema_version)
            
            # Set up basic IFC project structure
            self._setup_ifc_project(ifc_file)
            
            # Convert each building
            buildings_converted = 0
            elements_created = 0
            
            for i, building in enumerate(buildings):
                try:
                    if self.debug_mode:
                        print(f"Converting building {i+1}/{len(buildings)}: {building.building_id}")
                    
                    elements_count = self._convert_single_building(ifc_file, building)
                    if elements_count > 0:
                        buildings_converted += 1
                        elements_created += elements_count
                        
                except Exception as building_error:
                    if self.debug_mode:
                        print(f"Failed to convert building {building.building_id}: {building_error}")
                    continue
            
            # Save IFC file if path provided
            ifc_file_path = None
            if output_path:
                ifc_file.write(output_path)
                ifc_file_path = output_path
                if self.debug_mode:
                    print(f"IFC file saved to: {output_path}")
            
            conversion_time = time.time() - start_time
            
            return IFCConversionResult(
                success=buildings_converted > 0,
                ifc_file=ifc_file,
                ifc_file_path=ifc_file_path,
                buildings_converted=buildings_converted,
                elements_created=elements_created,
                conversion_time=conversion_time,
                error_message=None if buildings_converted > 0 else "No buildings could be converted"
            )
            
        except Exception as e:
            return IFCConversionResult(
                success=False,
                error_message=f"IFC conversion failed: {str(e)}",
                conversion_time=time.time() - start_time
            )
    
    def _setup_ifc_project(self, ifc_file):
        """Set up basic IFC project structure"""
        try:
            # Create project using direct IFC entity creation
            project = ifc_file.create_entity("IfcProject")
            project.Name = "CityGML to IFC Conversion"
            project.GlobalId = ifcopenshell.guid.new()
            
            # Create units
            length_unit = ifc_file.create_entity("IfcSIUnit")
            length_unit.UnitType = "LENGTHUNIT"
            length_unit.Name = "METRE"
            
            # Create site
            site = ifc_file.create_entity("IfcSite")
            site.Name = "CityGML Site"
            site.GlobalId = ifcopenshell.guid.new()
            
            # Store references for building assignment
            self.project = project
            self.site = site
            
            if self.debug_mode:
                print("IFC project structure created successfully")
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error setting up IFC project: {e}")
            # Use simplified approach if complex setup fails
            self.project = None
            self.site = None
    
    def _convert_single_building(self, ifc_file, building: BuildingGeometry) -> int:
        """
        Convert a single CityGML building to IFC
        
        Returns:
            Number of IFC elements created
        """
        try:
            # Create IFC building using direct entity creation
            ifc_building = ifc_file.create_entity("IfcBuilding")
            ifc_building.Name = building.building_id or f"Building_{id(building)}"
            ifc_building.GlobalId = ifcopenshell.guid.new()
            
            elements_created = 1  # Count the building itself
            
            # Convert surfaces based on LoD
            if building.lod == 0:
                # LoD0: Create simple building volume
                elements_created += self._create_building_volume(ifc_file, ifc_building, building)
            elif building.lod == 1:
                # LoD1: Create building envelope  
                elements_created += self._create_building_envelope(ifc_file, ifc_building, building)
            elif building.lod >= 2:
                # LoD2+: Create detailed building elements
                elements_created += self._create_building_elements(ifc_file, ifc_building, building)
            
            if self.debug_mode:
                print(f"Created {elements_created} IFC elements for building {building.building_id}")
            
            return elements_created
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error converting building {building.building_id}: {e}")
            return 0
    
    def _create_building_volume(self, ifc_file, ifc_building, building: BuildingGeometry) -> int:
        """Create simple building volume for LoD0"""
        try:
            if not building.surfaces:
                return 0
            
            # Calculate bounding box from surfaces
            all_points = []
            for surface in building.surfaces:
                all_points.extend(surface)
            
            if not all_points:
                return 0
            
            points_array = np.array(all_points)
            min_coords = points_array.min(axis=0)
            max_coords = points_array.max(axis=0)
            
            # Create simple box geometry
            # This is a simplified approach - in practice you'd create proper IFC geometry
            space = ifc_file.create_entity("IfcSpace")
            space.Name = f"BuildingSpace_{building.building_id}"
            space.GlobalId = ifcopenshell.guid.new()
            
            return 1
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error creating building volume: {e}")
            return 0
    
    def _create_building_envelope(self, ifc_file, ifc_building, building: BuildingGeometry) -> int:
        """Create building envelope for LoD1"""
        try:
            elements_created = 0
            
            # Create building storey
            storey = ifc_file.create_entity("IfcBuildingStorey")
            storey.Name = f"Storey_{building.building_id}"
            storey.GlobalId = ifcopenshell.guid.new()
            elements_created += 1
            
            # Create geometric representation context
            context = self._get_or_create_geometric_context(ifc_file)
            if not context:
                if self.debug_mode:
                    print("Failed to create geometric context")
                return elements_created
            
            # Convert surfaces to walls/slabs
            for i, surface in enumerate(building.surfaces[:10]):  # Limit for performance
                if len(surface) < 3:
                    continue
                
                # Determine surface type based on orientation (simplified)
                surface_type = self._classify_surface_type(surface)
                
                if surface_type == "wall":
                    wall = ifc_file.create_entity("IfcWall")
                    wall.Name = f"Wall_{i}"
                    wall.GlobalId = ifcopenshell.guid.new()
                    
                    # Create geometric representation for this surface
                    representation = self._create_surface_geometry(ifc_file, surface, context)
                    if representation:
                        product_shape = ifc_file.create_entity("IfcProductDefinitionShape")
                        product_shape.Representations = [representation]
                        wall.Representation = product_shape
                        if self.debug_mode:
                            print(f"Created wall {i} with geometric representation")
                    else:
                        if self.debug_mode:
                            print(f"Failed to create geometry for wall {i}")
                    
                    elements_created += 1
                
                elif surface_type in ["slab", "roof", "floor"]:
                    element_type = "IfcRoof" if surface_type == "roof" else "IfcSlab"
                    element = ifc_file.create_entity(element_type)
                    element.Name = f"{surface_type.title()}_{i}"
                    element.GlobalId = ifcopenshell.guid.new()
                    
                    # Create geometric representation for this surface
                    representation = self._create_surface_geometry(ifc_file, surface, context)
                    if representation:
                        product_shape = ifc_file.create_entity("IfcProductDefinitionShape")
                        product_shape.Representations = [representation]
                        element.Representation = product_shape
                        if self.debug_mode:
                            print(f"Created {surface_type} {i} with geometric representation")
                    else:
                        if self.debug_mode:
                            print(f"Failed to create geometry for {surface_type} {i}")
                    
                    elements_created += 1
            
            return elements_created
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error creating building envelope: {e}")
                import traceback
                traceback.print_exc()
            return 0
    
    def _create_building_elements(self, ifc_file, ifc_building, building: BuildingGeometry) -> int:
        """Create detailed building elements for LoD2+"""
        try:
            elements_created = 0
            
            # Create building storey
            storey = ifc_file.create_entity("IfcBuildingStorey")
            storey.Name = f"Storey_{building.building_id}"
            storey.GlobalId = ifcopenshell.guid.new()
            elements_created += 1
            
            # Create geometric representation context
            context = self._get_or_create_geometric_context(ifc_file)
            
            # Process surfaces with more detail
            for i, surface in enumerate(building.surfaces):
                if len(surface) < 3:
                    continue
                
                surface_type = self._classify_surface_type(surface)
                
                # Create appropriate IFC element
                if surface_type == "wall":
                    element = ifc_file.create_entity("IfcWall")
                    element.Name = f"Wall_{i}"
                elif surface_type == "roof":
                    element = ifc_file.create_entity("IfcRoof")
                    element.Name = f"Roof_{i}"
                elif surface_type == "floor":
                    element = ifc_file.create_entity("IfcSlab")
                    element.Name = f"Floor_{i}"
                else:
                    element = ifc_file.create_entity("IfcBuildingElementProxy")
                    element.Name = f"Element_{i}"
                
                element.GlobalId = ifcopenshell.guid.new()
                
                # Create geometric representation for this surface
                representation = self._create_surface_geometry(ifc_file, surface, context)
                if representation:
                    # Create product definition shape
                    product_shape = ifc_file.create_entity("IfcProductDefinitionShape")
                    product_shape.Representations = [representation]
                    element.Representation = product_shape
                
                elements_created += 1
            
            return elements_created
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error creating building elements: {e}")
            return 0
    
    def _classify_surface_type(self, surface: List[Tuple[float, float, float]]) -> str:
        """
        Classify surface type based on normal vector orientation
        
        Returns:
            Surface type: "wall", "roof", "floor", or "other"
        """
        try:
            if len(surface) < 3:
                return "other"
            
            # Calculate surface normal using cross product
            p1 = np.array(surface[0])
            p2 = np.array(surface[1])
            p3 = np.array(surface[2])
            
            v1 = p2 - p1
            v2 = p3 - p1
            normal = np.cross(v1, v2)
            normal = normal / np.linalg.norm(normal)
            
            # Classify based on normal direction
            z_component = abs(normal[2])
            
            if z_component > 0.8:  # Nearly horizontal
                if normal[2] > 0:
                    return "roof"
                else:
                    return "floor"
            elif z_component < 0.3:  # Nearly vertical
                return "wall"
            else:
                return "other"
                
        except Exception:
            return "other"
    
    def get_conversion_statistics(self, result: IFCConversionResult) -> Dict[str, Any]:
        """Get statistics from IFC conversion result"""
        stats = {
            "conversion_successful": result.success,
            "buildings_converted": result.buildings_converted,
            "ifc_elements_created": result.elements_created,
            "conversion_time_seconds": result.conversion_time,
            "schema_version": self.schema_version
        }
        
        if result.ifc_file:
            # Count different types of IFC entities
            entity_counts = {}
            for entity in result.ifc_file:
                entity_type = entity.is_a()
                entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
            
            stats["ifc_entity_counts"] = entity_counts
        
        return stats
    
    def _get_or_create_geometric_context(self, ifc_file):
        """Get or create a geometric representation context for the IFC file"""
        try:
            # Try to find existing context
            contexts = ifc_file.by_type("IfcGeometricRepresentationContext")
            if contexts:
                return contexts[0]
            
            # Create new geometric representation context
            context = ifc_file.create_entity("IfcGeometricRepresentationContext")
            context.ContextIdentifier = "Model"
            context.ContextType = "Model"
            context.CoordinateSpaceDimension = 3
            context.Precision = 1e-6
            
            # Create world coordinate system
            origin = ifc_file.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0])
            z_axis = ifc_file.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, 1.0])
            x_axis = ifc_file.create_entity("IfcDirection", DirectionRatios=[1.0, 0.0, 0.0])
            
            axis_placement = ifc_file.create_entity("IfcAxis2Placement3D")
            axis_placement.Location = origin
            axis_placement.Axis = z_axis
            axis_placement.RefDirection = x_axis
            
            context.WorldCoordinateSystem = axis_placement
            
            return context
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error creating geometric context: {e}")
            return None
    
    def _create_surface_geometry(self, ifc_file, surface, context):
        """Create IFC geometric representation from a CityGML surface"""
        try:
            if not surface or len(surface) < 3:
                if self.debug_mode:
                    print(f"Invalid surface: {len(surface) if surface else 0} points")
                return None
            
            if not context:
                if self.debug_mode:
                    print("No geometric context provided")
                return None
            
            if self.debug_mode:
                print(f"Creating geometry for surface with {len(surface)} points")
                print(f"First few points: {surface[:3]}")
            
            # Create coordinate list for the surface points
            surface_points = []
            for i, point in enumerate(surface):
                try:
                    # Ensure we have at least 3 coordinates (x, y, z)
                    if len(point) < 3:
                        if self.debug_mode:
                            print(f"Point {i} has insufficient coordinates: {point}")
                        continue
                    
                    coords = [float(point[0]), float(point[1]), float(point[2])]
                    # Validate coordinates are finite numbers
                    if any(not (isinstance(c, (int, float)) and not (c != c or c == float('inf') or c == float('-inf'))) for c in coords):
                        if self.debug_mode:
                            print(f"Point {i} has invalid coordinates: {coords}")
                        continue
                    
                    ifc_point = ifc_file.create_entity("IfcCartesianPoint", Coordinates=coords)
                    surface_points.append(ifc_point)
                    
                    if self.debug_mode and i == 0:
                        print(f"Created first point: {coords}")
                        
                except (IndexError, ValueError, TypeError) as point_error:
                    if self.debug_mode:
                        print(f"Error processing point {i}: {point}, error: {point_error}")
                    continue
            
            if len(surface_points) < 3:
                if self.debug_mode:
                    print(f"Not enough valid points: {len(surface_points)}")
                return None
            
            # Close the polygon if not already closed (check if first and last points are different)
            if len(surface_points) > 2:
                first_coords = surface_points[0].Coordinates
                last_coords = surface_points[-1].Coordinates
                
                # Check if points are significantly different (not just floating point precision)
                coord_diff = [abs(first_coords[i] - last_coords[i]) for i in range(3)]
                if max(coord_diff) > 1e-10:  # Not closed
                    # Add closing point
                    closing_point = ifc_file.create_entity("IfcCartesianPoint", Coordinates=first_coords)
                    surface_points.append(closing_point)
                    if self.debug_mode:
                        print(f"Added closing point to create closed polygon")
            
            if self.debug_mode:
                print(f"Final surface has {len(surface_points)} points")
            
            # Create polyline for the surface boundary
            polyline = ifc_file.create_entity("IfcPolyline", Points=surface_points)
            
            # Create face outer bound
            outer_bound = ifc_file.create_entity("IfcFaceOuterBound", Bound=polyline, Orientation=True)
            
            # Create face surface
            face = ifc_file.create_entity("IfcFace", Bounds=[outer_bound])
            
            # Create face based surface model
            surface_model = ifc_file.create_entity("IfcFaceBasedSurfaceModel", FbsmFaces=[face])
            
            # Create shape representation
            representation = ifc_file.create_entity("IfcShapeRepresentation")
            representation.ContextOfItems = context
            representation.RepresentationIdentifier = "Body"
            representation.RepresentationType = "SurfaceModel"
            representation.Items = [surface_model]
            
            if self.debug_mode:
                print(f"Successfully created geometry representation with {len(surface_points)} points")
            
            return representation
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error creating surface geometry: {e}")
                import traceback
                traceback.print_exc()
            return None