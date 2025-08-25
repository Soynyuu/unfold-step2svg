<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
  xmlns:core="http://www.opengis.net/citygml/2.0" 
  xmlns:bldg="http://www.opengis.net/citygml/building/2.0" 
  xmlns:gml="http://www.opengis.net/gml">
  
  <core:cityObjectMember>
    <bldg:Building gml:id="building1">
      <bldg:lod2MultiSurface>
        <gml:MultiSurface>
          <!-- Bottom face -->
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    0.0 0.0 0.0
                    10.0 0.0 0.0
                    10.0 10.0 0.0
                    0.0 10.0 0.0
                    0.0 0.0 0.0
                  </gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
          
          <!-- Top face -->
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    0.0 0.0 5.0
                    0.0 10.0 5.0
                    10.0 10.0 5.0
                    10.0 0.0 5.0
                    0.0 0.0 5.0
                  </gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
          
          <!-- Front face -->
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    0.0 0.0 0.0
                    0.0 0.0 5.0
                    10.0 0.0 5.0
                    10.0 0.0 0.0
                    0.0 0.0 0.0
                  </gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
          
          <!-- Back face -->
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    10.0 10.0 0.0
                    10.0 10.0 5.0
                    0.0 10.0 5.0
                    0.0 10.0 0.0
                    10.0 10.0 0.0
                  </gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
          
          <!-- Left face -->
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    0.0 10.0 0.0
                    0.0 10.0 5.0
                    0.0 0.0 5.0
                    0.0 0.0 0.0
                    0.0 10.0 0.0
                  </gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
          
          <!-- Right face -->
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>
                    10.0 0.0 0.0
                    10.0 0.0 5.0
                    10.0 10.0 5.0
                    10.0 10.0 0.0
                    10.0 0.0 0.0
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