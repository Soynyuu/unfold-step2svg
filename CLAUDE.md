# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A 3D-to-2D papercraft generation system that converts STEP CAD files and CityGML urban models into unfolded SVG diagrams. Part of the 2025 Mitou Junior program, using OpenCASCADE Technology for 3D geometry processing.

Repository: https://github.com/Soynyuu/unfold-step2svg

## Development Commands

```bash
# Environment setup
conda env create -f environment.yml
conda activate unfold-step2svg

# Run server
python main.py  # Starts on localhost:8001

# Test endpoints
curl http://localhost:8001/api/health
```

## Architecture

**Processing Pipeline:**
1. **File Loading** (`core/file_loaders.py`) - STEP/BREP parsing
2. **Geometry Analysis** (`core/geometry_analyzer.py`) - Face classification
3. **Unfolding** (`core/unfold_engine.py`) - 3D to 2D transformation
4. **Layout** (`core/layout_manager.py`) - Page optimization
5. **Export** (`core/svg_exporter.py`) - SVG generation with face numbering

**CityGML Dual Pipeline:**
- **Modern (default)**: CityGML → IFC → STEP (bypasses OCCT writer issues)
- **Legacy**: CityGML → OCCT Solids → STEP

Pipeline selection in `services/citygml_processor.py` via `use_ifc_pipeline` parameter.

## API Endpoints

```bash
# STEP to SVG
curl -X POST \
  -F "file=@model.step" \
  http://localhost:8001/api/step/unfold \
  -o papercraft.svg

# CityGML to STEP
curl -X POST \
  -F "file=@city.gml" \
  -F "lod_filter=2" \
  -F "use_ifc_pipeline=true" \
  http://localhost:8001/api/citygml/to-step \
  -o buildings.step

# Validate CityGML
curl -X POST \
  -F "file=@city.gml" \
  http://localhost:8001/api/citygml/validate
```

## Key Dependencies

- **OpenCASCADE 7.9.0** - CAD kernel (`pythonocc-core`)
- **ifcopenshell 0.8.0** - IFC processing for CityGML pipeline
- **FastAPI** - Web framework
- **lxml** - CityGML XML parsing
- **svgwrite** - SVG generation

## Debug Mode

Failed operations save debug files to `core/debug_files/`:

```bash
curl -X POST \
  -F "file=@model.step" \
  -F "debug_mode=true" \
  http://localhost:8001/api/step/unfold
```

## Known Issues

- **OCCT STEP Writer**: Path encoding issues - use IFC pipeline (`use_ifc_pipeline=true`)
- **BRepGProp imports**: Version-dependent, handled with fallbacks in `core/citygml_solidifier.py`

## Testing

No testing framework established. Implement with pytest when needed.

## Face Numbering System

Face numbers are generated server-side based on normal vectors and dynamically sized according to face area. Implementation in `core/svg_exporter.py`.