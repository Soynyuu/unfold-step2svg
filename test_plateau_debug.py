#!/usr/bin/env python
"""
Debug script for PLATEAU CityGML conversion issues
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.cityjson_converter import CityJSONConverter
from core.cityjson_solidifier import CityJSONSolidifier
from core.cityjson_validator import CityJSONValidator

def test_plateau_conversion(citygml_path: str):
    """Test PLATEAU model conversion with detailed debugging"""
    
    print(f"Testing PLATEAU model: {citygml_path}")
    print("=" * 60)
    
    # Read CityGML file
    with open(citygml_path, 'rb') as f:
        citygml_content = f.read()
    
    print(f"File size: {len(citygml_content)} bytes")
    
    # Step 1: Convert to CityJSON
    print("\n1. Converting CityGML to CityJSON...")
    converter = CityJSONConverter()
    converter.enable_debug(True)
    
    cityjson_data = converter.convert_citygml_to_cityjson(citygml_content)
    
    if not cityjson_data:
        print("ERROR: Failed to convert to CityJSON")
        return
    
    print(f"CityJSON version: {cityjson_data.get('version')}")
    print(f"City objects: {len(cityjson_data.get('CityObjects', {}))}")
    print(f"Vertices: {len(cityjson_data.get('vertices', []))}")
    
    # Save intermediate CityJSON for inspection
    debug_json_path = "debug_cityjson.json"
    with open(debug_json_path, 'w') as f:
        json.dump(cityjson_data, f, indent=2)
    print(f"Saved intermediate CityJSON to {debug_json_path}")
    
    # Step 2: Load and parse CityJSON
    print("\n2. Loading CityJSON data...")
    if not converter.load_cityjson(cityjson_data):
        print("ERROR: Failed to load CityJSON data")
        return
    
    buildings = converter.get_buildings()
    print(f"Parsed {len(buildings)} buildings")
    
    # Step 3: Try to solidify each building
    print("\n3. Attempting solidification...")
    solidifier = CityJSONSolidifier()
    solidifier.enable_debug(True)
    
    for i, building in enumerate(buildings[:3]):  # Test first 3 buildings
        print(f"\nBuilding {i+1}/{min(3, len(buildings))}: {building.building_id}")
        print(f"  Type: {building.building_type}")
        print(f"  LoD: {building.lod}")
        print(f"  Geometry count: {len(building.geometry)}")
        
        # Get surfaces
        surfaces = converter.get_building_surfaces(building)
        print(f"  Surfaces: {len(surfaces)}")
        
        if surfaces:
            # Check surface details
            for j, surface in enumerate(surfaces[:5]):  # First 5 surfaces
                print(f"    Surface {j+1}: {len(surface)} vertices")
                if surface:
                    # Check if surface is planar
                    if len(surface) >= 3:
                        # Simple planarity check
                        v1 = surface[0]
                        v2 = surface[1] 
                        v3 = surface[2]
                        print(f"      First 3 vertices: {v1}, {v2}, {v3}")
        
        # Convert surfaces to the correct format for solidification
        # get_building_surfaces returns List[List[Tuple]] (simple surfaces)
        # We need to convert to List[List[List[Tuple]]] (surfaces with rings)
        surfaces_with_rings = []
        for surface in surfaces:
            # Each surface becomes a list with one ring (the exterior)
            surfaces_with_rings.append([surface])
        
        print(f"  Surfaces structure for solidification: {len(surfaces_with_rings)} surfaces")
        
        # Try solidification
        try:
            result = solidifier.solidify_building(building, surfaces_with_rings)
            print(f"  Solidification result: {'SUCCESS' if result.success else 'FAILED'}")
            if not result.success:
                print(f"    Error: {result.error_message}")
            else:
                print(f"    Face count: {result.face_count}")
                print(f"    Is closed: {result.is_closed}")
                print(f"    Is valid: {result.is_valid}")
        except Exception as e:
            print(f"  Solidification exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_plateau_debug.py <citygml_file>")
        sys.exit(1)
    
    test_plateau_conversion(sys.argv[1])