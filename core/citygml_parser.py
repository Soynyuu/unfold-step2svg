"""
CityGML Parser Module

This module provides functionality to parse CityGML files and extract building geometry
for conversion to solid models. It handles various CityGML versions and Plateau extensions.
"""

import os
import tempfile
from typing import List, Dict, Any, Optional, Tuple, Union
from lxml import etree
import numpy as np
from dataclasses import dataclass


@dataclass
class BuildingGeometry:
    """Container for building geometry data extracted from CityGML"""
    building_id: str
    building_name: Optional[str]
    surfaces: List[List[Tuple[float, float, float]]]  # List of surface polygons
    semantic_type: str  # Wall, Roof, Ground, etc.
    lod: int  # Level of Detail
    height: Optional[float]
    area: Optional[float]


class CityGMLParser:
    """
    CityGML Parser for extracting building geometry and converting to solid models.
    Supports CityGML 1.0, 2.0, and 3.0 as well as Plateau extensions.
    """
    
    # Common CityGML namespaces
    NAMESPACES = {
        'gml': 'http://www.opengis.net/gml',
        'gml32': 'http://www.opengis.net/gml/3.2',
        'citygml': 'http://www.opengis.net/citygml/1.0',
        'citygml2': 'http://www.opengis.net/citygml/2.0',
        'citygml3': 'http://www.opengis.net/citygml/3.0',
        'bldg': 'http://www.opengis.net/citygml/building/1.0',
        'bldg2': 'http://www.opengis.net/citygml/building/2.0',
        'bldg3': 'http://www.opengis.net/citygml/building/3.0',
        'app': 'http://www.opengis.net/citygml/appearance/1.0',
        'app2': 'http://www.opengis.net/citygml/appearance/2.0',
        'gen': 'http://www.opengis.net/citygml/generics/1.0',
        'gen2': 'http://www.opengis.net/citygml/generics/2.0',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xlink': 'http://www.w3.org/1999/xlink',
        # Plateau-specific namespaces
        'uro': 'https://www.geospatial.jp/iur/uro/2.0',
        'urf': 'https://www.geospatial.jp/iur/urf/2.0',
        'plateau': 'https://www.geospatial.jp/iur/plateau/2.0'
    }
    
    def __init__(self):
        self.buildings: List[BuildingGeometry] = []
        self.root = None
        self.detected_namespaces = {}
        
    def parse_from_file(self, file_path: str) -> bool:
        """
        Parse CityGML from file path
        
        Args:
            file_path: Path to CityGML file
            
        Returns:
            bool: True if parsing successful, False otherwise
        """
        try:
            with open(file_path, 'rb') as f:
                return self.parse_from_bytes(f.read())
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return False
    
    def parse_from_bytes(self, content: bytes) -> bool:
        """
        Parse CityGML from bytes content
        
        Args:
            content: Raw CityGML file content
            
        Returns:
            bool: True if parsing successful, False otherwise
        """
        try:
            # Parse XML with lxml
            parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False)
            self.root = etree.fromstring(content, parser)
            
            # Auto-detect namespaces from document
            self._detect_namespaces()
            
            # Extract building geometries
            self.buildings = self._extract_buildings()
            
            return len(self.buildings) > 0
            
        except etree.XMLSyntaxError as e:
            print(f"XML parsing error: {e}")
            return False
        except Exception as e:
            print(f"CityGML parsing error: {e}")
            return False
    
    def _detect_namespaces(self):
        """Auto-detect namespaces used in the document"""
        self.detected_namespaces = dict(self.root.nsmap)
        
        # Update our namespace map with detected ones
        for prefix, uri in self.detected_namespaces.items():
            if prefix is not None:  # Skip default namespace
                if uri.endswith('/building/1.0') or uri.endswith('/building/2.0') or uri.endswith('/building/3.0'):
                    self.NAMESPACES['bldg'] = uri
                elif uri.endswith('/gml') or uri.endswith('/gml/3.2'):
                    self.NAMESPACES['gml'] = uri
                elif 'citygml' in uri:
                    self.NAMESPACES['citygml'] = uri
    
    def _extract_buildings(self) -> List[BuildingGeometry]:
        """Extract all buildings from the CityGML document"""
        buildings = []
        
        # Try different building element patterns
        building_patterns = [
            './/bldg:Building',
            './/bldg2:Building', 
            './/bldg3:Building',
            './/*[local-name()="Building"]'  # Fallback for any namespace
        ]
        
        for pattern in building_patterns:
            building_elements = self.root.xpath(pattern, namespaces=self.NAMESPACES)
            for building_elem in building_elements:
                building_geom = self._extract_building_geometry(building_elem)
                if building_geom:
                    buildings.append(building_geom)
            
            if buildings:  # If we found buildings with this pattern, use them
                break
        
        return buildings
    
    def _extract_building_geometry(self, building_elem) -> Optional[BuildingGeometry]:
        """Extract geometry from a single building element"""
        try:
            # Get building ID
            building_id = building_elem.get('{http://www.opengis.net/gml}id', f"building_{len(self.buildings)}")
            
            # Get building name if available
            building_name = None
            name_elem = building_elem.find('.//gml:name', namespaces=self.NAMESPACES)
            if name_elem is not None:
                building_name = name_elem.text
            
            # Extract surfaces from different LoD representations
            surfaces = []
            lod = 1  # Default LoD
            
            # Try LoD2 first (most detailed), then LoD1, then LoD0
            for lod_level in [2, 1, 0]:
                lod_surfaces = self._extract_lod_surfaces(building_elem, lod_level)
                if lod_surfaces:
                    surfaces = lod_surfaces
                    lod = lod_level
                    break
            
            if not surfaces:
                return None
            
            # Calculate basic properties
            height = self._calculate_building_height(surfaces)
            area = self._calculate_building_area(surfaces)
            
            return BuildingGeometry(
                building_id=building_id,
                building_name=building_name,
                surfaces=surfaces,
                semantic_type="Building",
                lod=lod,
                height=height,
                area=area
            )
            
        except Exception as e:
            print(f"Error extracting building geometry: {e}")
            return None
    
    def _extract_lod_surfaces(self, building_elem, lod_level: int) -> List[List[Tuple[float, float, float]]]:
        """Extract surfaces for a specific LoD level"""
        surfaces = []
        
        # LoD-specific XPath patterns
        lod_patterns = {
            0: [f'.//bldg:lod{lod_level}Solid', f'.//*[local-name()="lod{lod_level}Solid"]'],
            1: [f'.//bldg:lod{lod_level}Solid', f'.//*[local-name()="lod{lod_level}Solid"]'],
            2: [f'.//bldg:lod{lod_level}MultiSurface', f'.//bldg:lod{lod_level}Solid', 
                f'.//*[local-name()="lod{lod_level}MultiSurface"]', f'.//*[local-name()="lod{lod_level}Solid"]']
        }
        
        patterns = lod_patterns.get(lod_level, lod_patterns[1])
        
        for pattern in patterns:
            geom_elements = building_elem.xpath(pattern, namespaces=self.NAMESPACES)
            for geom_elem in geom_elements:
                surface_list = self._extract_surfaces_from_geometry(geom_elem)
                surfaces.extend(surface_list)
            
            if surfaces:  # If we found surfaces, use them
                break
        
        return surfaces
    
    def _extract_surfaces_from_geometry(self, geom_elem) -> List[List[Tuple[float, float, float]]]:
        """Extract coordinate surfaces from geometry element"""
        surfaces = []
        
        # Look for polygon surfaces
        polygon_patterns = [
            './/gml:Polygon',
            './/gml32:Polygon',
            './/*[local-name()="Polygon"]'
        ]
        
        for pattern in polygon_patterns:
            polygons = geom_elem.xpath(pattern, namespaces=self.NAMESPACES)
            for polygon in polygons:
                coords = self._extract_polygon_coordinates(polygon)
                if coords:
                    surfaces.append(coords)
        
        return surfaces
    
    def _extract_polygon_coordinates(self, polygon_elem) -> List[Tuple[float, float, float]]:
        """Extract coordinates from a polygon element"""
        coords = []
        
        # Look for coordinate lists in different formats
        coord_patterns = [
            './/gml:posList',
            './/gml32:posList',
            './/gml:coordinates',
            './/gml32:coordinates',
            './/*[local-name()="posList"]',
            './/*[local-name()="coordinates"]'
        ]
        
        for pattern in coord_patterns:
            coord_elems = polygon_elem.xpath(pattern, namespaces=self.NAMESPACES)
            for coord_elem in coord_elems:
                if coord_elem.text:
                    coords = self._parse_coordinate_string(coord_elem.text)
                    if coords:
                        break
            if coords:
                break
        
        return coords
    
    def _parse_coordinate_string(self, coord_text: str) -> List[Tuple[float, float, float]]:
        """Parse coordinate string into list of 3D points"""
        try:
            # Clean and split coordinate string
            coord_text = coord_text.strip()
            values = coord_text.replace(',', ' ').split()
            
            # Convert to float values
            float_values = [float(v) for v in values]
            
            # Group into 3D coordinates
            coords = []
            for i in range(0, len(float_values), 3):
                if i + 2 < len(float_values):
                    coords.append((float_values[i], float_values[i+1], float_values[i+2]))
                elif i + 1 < len(float_values):
                    # 2D coordinates, add z=0
                    coords.append((float_values[i], float_values[i+1], 0.0))
            
            return coords
            
        except (ValueError, IndexError) as e:
            print(f"Error parsing coordinates: {e}")
            return []
    
    def _calculate_building_height(self, surfaces: List[List[Tuple[float, float, float]]]) -> Optional[float]:
        """Calculate building height from surfaces"""
        if not surfaces:
            return None
        
        z_coords = []
        for surface in surfaces:
            for point in surface:
                z_coords.append(point[2])
        
        if z_coords:
            return max(z_coords) - min(z_coords)
        return None
    
    def _calculate_building_area(self, surfaces: List[List[Tuple[float, float, float]]]) -> Optional[float]:
        """Calculate approximate building footprint area"""
        if not surfaces:
            return None
        
        # Find the surface with minimum z (ground floor)
        ground_surfaces = []
        min_z = float('inf')
        
        for surface in surfaces:
            avg_z = sum(point[2] for point in surface) / len(surface)
            if avg_z < min_z:
                min_z = avg_z
                ground_surfaces = [surface]
            elif abs(avg_z - min_z) < 0.1:  # Similar height
                ground_surfaces.append(surface)
        
        # Calculate area of ground surfaces
        total_area = 0
        for surface in ground_surfaces:
            if len(surface) >= 3:
                # Simple polygon area calculation using shoelace formula
                area = 0
                n = len(surface)
                for i in range(n):
                    j = (i + 1) % n
                    area += surface[i][0] * surface[j][1]
                    area -= surface[j][0] * surface[i][1]
                total_area += abs(area) / 2
        
        return total_area if total_area > 0 else None
    
    def get_buildings(self) -> List[BuildingGeometry]:
        """Get list of extracted building geometries"""
        return self.buildings
    
    def get_building_count(self) -> int:
        """Get number of buildings found"""
        return len(self.buildings)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get parsing statistics"""
        if not self.buildings:
            return {"building_count": 0}
        
        lod_counts = {}
        total_surfaces = 0
        heights = []
        areas = []
        
        for building in self.buildings:
            lod_counts[building.lod] = lod_counts.get(building.lod, 0) + 1
            total_surfaces += len(building.surfaces)
            if building.height:
                heights.append(building.height)
            if building.area:
                areas.append(building.area)
        
        stats = {
            "building_count": len(self.buildings),
            "total_surfaces": total_surfaces,
            "lod_distribution": lod_counts,
            "avg_surfaces_per_building": total_surfaces / len(self.buildings) if self.buildings else 0
        }
        
        if heights:
            stats["height_stats"] = {
                "min": min(heights),
                "max": max(heights),
                "avg": sum(heights) / len(heights)
            }
        
        if areas:
            stats["area_stats"] = {
                "min": min(areas),
                "max": max(areas),
                "avg": sum(areas) / len(areas)
            }
        
        return stats