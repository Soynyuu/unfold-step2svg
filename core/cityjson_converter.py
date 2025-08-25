"""
CityJSON Converter Module

This module provides functionality to convert CityGML to CityJSON format
and process CityJSON data for B-Rep generation. It leverages the simpler
CityJSON format for more reliable geometry processing.
"""

import os
import json
import tempfile
import subprocess
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import numpy as np


@dataclass
class CityJSONBuilding:
    """Container for building data extracted from CityJSON"""
    building_id: str
    building_type: str
    geometry: List[Dict[str, Any]]  # CityJSON geometry objects
    attributes: Dict[str, Any]
    vertices: List[List[float]]  # Referenced vertices
    lod: int


@dataclass
class CityJSONData:
    """Container for parsed CityJSON data"""
    version: str
    city_objects: Dict[str, Any]
    vertices: List[List[float]]
    transform: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    buildings: List[CityJSONBuilding]


class CityJSONConverter:
    """
    Converter for CityGML to CityJSON and CityJSON processing.
    Uses citygml-tools for conversion and processes CityJSON for B-Rep generation.
    """
    
    def __init__(self):
        self.cityjson_data: Optional[CityJSONData] = None
        self.debug_mode = False
        
    def enable_debug(self, enabled: bool = True):
        """Enable debug mode for detailed logging"""
        self.debug_mode = enabled
        
    def convert_citygml_to_cityjson(self, citygml_content: bytes) -> Optional[Dict[str, Any]]:
        """
        Convert CityGML content to CityJSON using citygml-tools CLI
        
        Args:
            citygml_content: Raw CityGML file content
            
        Returns:
            CityJSON dictionary or None if conversion failed
        """
        temp_gml = None
        temp_json = None
        
        try:
            # Save CityGML to temporary file
            with tempfile.NamedTemporaryFile(suffix='.gml', delete=False) as temp_gml_file:
                temp_gml_file.write(citygml_content)
                temp_gml = temp_gml_file.name
            
            # Create temporary output file path
            temp_json = tempfile.mktemp(suffix='.city.json')
            
            # Try to use citygml-tools if available
            result = subprocess.run(
                ['citygml-tools', 'to-cityjson', temp_gml, temp_json],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                if self.debug_mode:
                    print(f"citygml-tools conversion failed: {result.stderr}")
                # Fall back to built-in converter
                return self._convert_citygml_builtin(citygml_content)
            
            # Read converted CityJSON
            with open(temp_json, 'r', encoding='utf-8') as f:
                cityjson = json.load(f)
            
            if self.debug_mode:
                print(f"Successfully converted CityGML to CityJSON")
                print(f"CityJSON version: {cityjson.get('version', 'unknown')}")
                print(f"Number of city objects: {len(cityjson.get('CityObjects', {}))}")
            
            return cityjson
            
        except FileNotFoundError:
            if self.debug_mode:
                print("citygml-tools not found, using built-in converter")
            return self._convert_citygml_builtin(citygml_content)
            
        except subprocess.TimeoutExpired:
            if self.debug_mode:
                print("citygml-tools conversion timed out")
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error during CityGML to CityJSON conversion: {e}")
            return None
            
        finally:
            # Clean up temporary files
            if temp_gml and os.path.exists(temp_gml):
                os.unlink(temp_gml)
            if temp_json and os.path.exists(temp_json):
                os.unlink(temp_json)
    
    def _convert_citygml_builtin(self, citygml_content: bytes) -> Optional[Dict[str, Any]]:
        """
        Built-in CityGML to CityJSON converter (simplified)
        This is a fallback when citygml-tools is not available
        """
        try:
            from lxml import etree
            
            # Parse CityGML XML
            parser = etree.XMLParser(remove_blank_text=True)
            root = etree.fromstring(citygml_content, parser)
            
            # Create basic CityJSON structure
            cityjson = {
                "type": "CityJSON",
                "version": "1.1",
                "CityObjects": {},
                "vertices": []
            }
            
            # Extract namespaces
            namespaces = {
                'gml': 'http://www.opengis.net/gml',
                'bldg': 'http://www.opengis.net/citygml/building/2.0',
                'bldg1': 'http://www.opengis.net/citygml/building/1.0'
            }
            
            # Find all buildings
            buildings = root.xpath('//bldg:Building | //bldg1:Building', namespaces=namespaces)
            
            vertex_map = {}
            vertex_index = 0
            
            for building in buildings:
                building_id = building.get('{http://www.opengis.net/gml}id', f'building_{len(cityjson["CityObjects"])}')
                
                # Create CityObject
                city_obj = {
                    "type": "Building",
                    "geometry": []
                }
                
                # Extract LoD2 MultiSurface
                multi_surfaces = building.xpath('.//bldg:lod2MultiSurface//gml:Polygon | .//bldg1:lod2MultiSurface//gml:Polygon', 
                                               namespaces=namespaces)
                
                if multi_surfaces:
                    boundaries = []
                    
                    for polygon in multi_surfaces:
                        # Extract exterior ring
                        pos_list = polygon.xpath('.//gml:exterior//gml:posList', namespaces=namespaces)
                        if pos_list:
                            coords_text = pos_list[0].text.strip()
                            coords = [float(x) for x in coords_text.split()]
                            
                            # Group into vertices (x, y, z)
                            vertices = []
                            for i in range(0, len(coords), 3):
                                vertex = [coords[i], coords[i+1], coords[i+2]]
                                vertex_key = tuple(vertex)
                                
                                if vertex_key not in vertex_map:
                                    vertex_map[vertex_key] = vertex_index
                                    cityjson["vertices"].append(vertex)
                                    vertex_index += 1
                                
                                vertices.append(vertex_map[vertex_key])
                            
                            # Add surface
                            boundaries.append([vertices])
                    
                    if boundaries:
                        city_obj["geometry"].append({
                            "type": "MultiSurface",
                            "lod": 2,
                            "boundaries": boundaries
                        })
                
                cityjson["CityObjects"][building_id] = city_obj
            
            if self.debug_mode:
                print(f"Built-in converter: extracted {len(cityjson['CityObjects'])} buildings")
                print(f"Total vertices: {len(cityjson['vertices'])}")
            
            return cityjson if cityjson["CityObjects"] else None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Built-in CityGML conversion failed: {e}")
            return None
    
    def load_cityjson(self, cityjson_dict: Dict[str, Any]) -> bool:
        """
        Load and parse CityJSON data
        
        Args:
            cityjson_dict: CityJSON dictionary
            
        Returns:
            True if loading successful, False otherwise
        """
        try:
            # Extract basic information
            version = cityjson_dict.get("version", "1.0")
            city_objects = cityjson_dict.get("CityObjects", {})
            vertices = cityjson_dict.get("vertices", [])
            transform = cityjson_dict.get("transform")
            metadata = cityjson_dict.get("metadata")
            
            # Apply transformation if present
            if transform:
                vertices = self._apply_transform(vertices, transform)
            
            # Extract buildings
            buildings = []
            for obj_id, obj_data in city_objects.items():
                if obj_data.get("type") in ["Building", "BuildingPart"]:
                    building = CityJSONBuilding(
                        building_id=obj_id,
                        building_type=obj_data.get("type"),
                        geometry=obj_data.get("geometry", []),
                        attributes=obj_data.get("attributes", {}),
                        vertices=vertices,  # Reference to shared vertices
                        lod=self._get_max_lod(obj_data.get("geometry", []))
                    )
                    buildings.append(building)
            
            self.cityjson_data = CityJSONData(
                version=version,
                city_objects=city_objects,
                vertices=vertices,
                transform=transform,
                metadata=metadata,
                buildings=buildings
            )
            
            if self.debug_mode:
                print(f"Loaded CityJSON with {len(buildings)} buildings")
                print(f"Total vertices: {len(vertices)}")
                if transform:
                    print(f"Applied transformation with scale: {transform.get('scale', [1,1,1])}")
            
            return len(buildings) > 0
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error loading CityJSON: {e}")
            return False
    
    def _apply_transform(self, vertices: List[List[float]], transform: Dict[str, Any]) -> List[List[float]]:
        """
        Apply CityJSON transformation to vertices
        
        CityJSON can store vertices as integers with a transform for compression
        """
        scale = transform.get("scale", [1.0, 1.0, 1.0])
        translate = transform.get("translate", [0.0, 0.0, 0.0])
        
        transformed = []
        for vertex in vertices:
            transformed.append([
                vertex[0] * scale[0] + translate[0],
                vertex[1] * scale[1] + translate[1],
                vertex[2] * scale[2] + translate[2]
            ])
        
        return transformed
    
    def _get_max_lod(self, geometry: List[Dict[str, Any]]) -> int:
        """Get maximum LoD from geometry list"""
        max_lod = 0
        for geom in geometry:
            lod = geom.get("lod", 0)
            if isinstance(lod, str):
                lod = int(float(lod))
            max_lod = max(max_lod, lod)
        return max_lod
    
    def get_building_surfaces(self, building: CityJSONBuilding) -> List[List[Tuple[float, float, float]]]:
        """
        Extract surface polygons from a CityJSON building
        
        Args:
            building: CityJSONBuilding object
            
        Returns:
            List of surface polygons (each polygon is a list of vertices)
        """
        surfaces = []
        
        for geom in building.geometry:
            geom_type = geom.get("type")
            
            if geom_type == "Solid":
                # Solid: boundaries[shell][surface][ring][vertex_indices]
                for shell in geom.get("boundaries", []):
                    for surface in shell:
                        # Get outer ring (first ring)
                        if surface and surface[0]:
                            vertices = self._get_vertices_from_indices(surface[0], building.vertices)
                            if vertices:
                                surfaces.append(vertices)
                                
            elif geom_type == "MultiSurface":
                # MultiSurface: boundaries[surface][ring][vertex_indices]
                for surface in geom.get("boundaries", []):
                    # Get outer ring (first ring)
                    if surface and surface[0]:
                        vertices = self._get_vertices_from_indices(surface[0], building.vertices)
                        if vertices:
                            surfaces.append(vertices)
                            
            elif geom_type == "CompositeSurface":
                # CompositeSurface: similar to MultiSurface
                for surface in geom.get("boundaries", []):
                    if surface and surface[0]:
                        vertices = self._get_vertices_from_indices(surface[0], building.vertices)
                        if vertices:
                            surfaces.append(vertices)
        
        return surfaces
    
    def _get_vertices_from_indices(self, indices: List[int], vertices: List[List[float]]) -> List[Tuple[float, float, float]]:
        """
        Convert vertex indices to actual coordinates
        
        Args:
            indices: List of vertex indices
            vertices: Shared vertex array
            
        Returns:
            List of vertex coordinates as tuples
        """
        coords = []
        for idx in indices:
            if 0 <= idx < len(vertices):
                v = vertices[idx]
                coords.append((v[0], v[1], v[2]))
        return coords
    
    def get_buildings(self) -> List[CityJSONBuilding]:
        """Get all parsed buildings"""
        if self.cityjson_data:
            return self.cityjson_data.buildings
        return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the loaded CityJSON data"""
        if not self.cityjson_data:
            return {}
        
        stats = {
            "version": self.cityjson_data.version,
            "building_count": len(self.cityjson_data.buildings),
            "vertex_count": len(self.cityjson_data.vertices),
            "has_transform": self.cityjson_data.transform is not None,
            "has_metadata": self.cityjson_data.metadata is not None
        }
        
        # Count geometry types
        geom_types = {}
        total_surfaces = 0
        
        for building in self.cityjson_data.buildings:
            for geom in building.geometry:
                geom_type = geom.get("type")
                geom_types[geom_type] = geom_types.get(geom_type, 0) + 1
                
                if geom_type == "Solid":
                    for shell in geom.get("boundaries", []):
                        total_surfaces += len(shell)
                elif geom_type in ["MultiSurface", "CompositeSurface"]:
                    total_surfaces += len(geom.get("boundaries", []))
        
        stats["geometry_types"] = geom_types
        stats["total_surfaces"] = total_surfaces
        
        # LoD distribution
        lod_counts = {}
        for building in self.cityjson_data.buildings:
            lod = building.lod
            lod_counts[f"lod{lod}"] = lod_counts.get(f"lod{lod}", 0) + 1
        stats["lod_distribution"] = lod_counts
        
        return stats
    
    def apply_cjio_operations(self, cityjson_dict: Dict[str, Any], operations: List[str]) -> Optional[Dict[str, Any]]:
        """
        Apply cjio operations to CityJSON data
        
        Args:
            cityjson_dict: Input CityJSON dictionary
            operations: List of cjio operations (e.g., ["triangulate", "clean"])
            
        Returns:
            Processed CityJSON dictionary or None if failed
        """
        temp_input = None
        temp_output = None
        
        try:
            # Save CityJSON to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.city.json', delete=False) as temp_file:
                json.dump(cityjson_dict, temp_file)
                temp_input = temp_file.name
            
            temp_output = tempfile.mktemp(suffix='.city.json')
            
            # Build cjio command
            cmd = ['cjio', temp_input]
            cmd.extend(operations)
            cmd.extend(['save', temp_output])
            
            # Execute cjio
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                if self.debug_mode:
                    print(f"cjio operation failed: {result.stderr}")
                return None
            
            # Read processed CityJSON
            with open(temp_output, 'r', encoding='utf-8') as f:
                processed = json.load(f)
            
            if self.debug_mode:
                print(f"Applied cjio operations: {', '.join(operations)}")
            
            return processed
            
        except FileNotFoundError:
            if self.debug_mode:
                print("cjio not found")
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error applying cjio operations: {e}")
            return None
            
        finally:
            # Clean up
            if temp_input and os.path.exists(temp_input):
                os.unlink(temp_input)
            if temp_output and os.path.exists(temp_output):
                os.unlink(temp_output)