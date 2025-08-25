<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
  xmlns:core="http://www.opengis.net/citygml/2.0" 
  xmlns:bldg="http://www.opengis.net/citygml/building/2.0" 
  xmlns:gml="http://www.opengis.net/gml">
  
  <core:cityObjectMember>
    <bldg:Building gml:id="building_complex">
      <bldg:lod2MultiSurface>
        <gml:MultiSurface>
          <!-- Wall with a hole (window) -->
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    0.0 0.0 0.0
                    10.0 0.0 0.0
                    10.0 0.0 8.0
                    0.0 0.0 8.0
                    0.0 0.0 0.0
                  </gml:posList>
                </gml:LinearRing>
              </gml:exterior>
              <!-- Hole in the wall -->
              <gml:interior>
                <gml:LinearRing>
                  <gml:posList>
                    3.0 0.0 2.0
                    7.0 0.0 2.0
                    7.0 0.0 5.0
                    3.0 0.0 5.0
                    3.0 0.0 2.0
                  </gml:posList>
                </gml:LinearRing>
              </gml:interior>
            </gml:Polygon>
          </gml:surfaceMember>
          
          <!-- Roof with triangular faces -->
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    0.0 0.0 8.0
                    10.0 0.0 8.0
                    5.0 5.0 12.0
                    0.0 0.0 8.0
                  </gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
          
          <!-- Non-planar polygon (will cause issues) -->
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    0.0 10.0 0.0
                    10.0 10.0 0.0
                    10.0 10.0 8.0
                    5.0 10.0 10.0
                    0.0 10.0 8.0
                    0.0 10.0 0.0
                  </gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:MultiSurface>
      </bldg:lod2MultiSurface>
    </bldg:Building>
  </core:cityObjectMember>
</core:CityModel>