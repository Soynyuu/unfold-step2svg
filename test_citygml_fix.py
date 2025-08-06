#!/usr/bin/env python3
"""
Test script to verify CityGML to STEP conversion fixes
"""

import requests
import time
import os

def test_citygml_conversion():
    """Test the CityGML to STEP conversion with a simple CityGML file"""
    
    # Simple test CityGML content
    test_citygml = """<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
                xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
                xmlns:gml="http://www.opengis.net/gml">
  <core:cityObjectMember>
    <bldg:Building gml:id="test_building_1">
      <bldg:lod2Solid>
        <gml:Solid>
          <gml:exterior>
            <gml:CompositeSurface>
              <gml:surfaceMember>
                <gml:Polygon>
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList>0 0 0 10 0 0 10 10 0 0 10 0 0 0 0</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
              <gml:surfaceMember>
                <gml:Polygon>
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList>0 0 0 0 10 0 0 10 5 0 0 5 0 0 0</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:CompositeSurface>
          </gml:exterior>
        </gml:Solid>
      </bldg:lod2Solid>
    </bldg:Building>
  </core:cityObjectMember>
</core:CityModel>
"""
    
    url = "http://localhost:8001/api/citygml/to-step"
    
    # Create temporary file
    with open("/tmp/test_citygml.gml", "w") as f:
        f.write(test_citygml)
    
    # Test the API
    try:
        with open("/tmp/test_citygml.gml", "rb") as f:
            files = {"file": ("test.gml", f, "application/xml")}
            data = {
                "debug_mode": True,
                "tolerance": 1e-3
            }
            
            print("Testing CityGML to STEP conversion...")
            print("Sending request to:", url)
            
            response = requests.post(url, files=files, data=data, timeout=60)
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Success! CityGML conversion worked.")
                
                # Save the result
                with open("/tmp/test_output.step", "wb") as out_f:
                    out_f.write(response.content)
                
                file_size = len(response.content)
                print(f"Generated STEP file size: {file_size} bytes")
                
                if file_size > 0:
                    print("✅ STEP file generated successfully!")
                    return True
                else:
                    print("❌ STEP file is empty!")
                    return False
                    
            else:
                print(f"❌ Error: {response.status_code}")
                print("Response:", response.text)
                return False
                
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return False
    
    finally:
        # Cleanup
        try:
            os.remove("/tmp/test_citygml.gml")
        except:
            pass

if __name__ == "__main__":
    success = test_citygml_conversion()
    if success:
        print("\n🎉 All tests passed! The CityGML conversion fix is working.")
    else:
        print("\n💥 Tests failed. Check the server logs for details.")