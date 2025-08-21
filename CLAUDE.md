# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A 3D-to-2D papercraft generation system that converts STEP CAD files into unfolded SVG diagrams. Built for the 2025 Mitou Junior program using OpenCASCADE Technology (OCCT) for industrial-grade 3D geometry processing.

Repository: https://github.com/Soynyuu/unfold-step2svg

## Development Commands

```bash
# Environment setup (Conda required)
conda env create -f environment.yml
conda activate unfold-step2svg

# Run server
python main.py                           # Starts on localhost:8001
PORT=8000 python main.py                 # Custom port

# Testing
python test_citygml_fix.py               # Test CityGML conversion
./test_face_numbers.sh                   # Test face numbering feature

# API testing
curl http://localhost:8001/api/health    # Health check
```

## Architecture

**Core Processing Pipeline:**
1. **File Loading** (`core/file_loaders.py`) - STEP/BREP parsing
2. **Geometry Analysis** (`core/geometry_analyzer.py`) - Face classification, normal vector analysis  
3. **Unfolding** (`core/unfold_engine.py`) - 3D-to-2D transformation with face numbering
4. **Layout** (`core/layout_manager.py`) - Multi-page optimization (A4, A3, Letter)
5. **SVG Export** (`core/svg_exporter.py`) - Print-ready output with fold/cut lines and face numbers

**Dual CityGML Pipeline Architecture:**
- **Modern IFC Pipeline** (default): CityGML → IFC → STEP (bypasses OCCT writer issues)
- **Legacy Pipeline**: CityGML → OCCT Solids → STEP

Pipeline selection in `services/citygml_processor.py` via `use_ifc_pipeline` flag.

## API Endpoints

```bash
POST /api/step/unfold         # STEP to SVG conversion
POST /api/citygml/to-step     # CityGML to STEP conversion  
POST /api/citygml/validate    # CityGML validation
GET /api/health               # System status
```

## Key Features

**Face Numbering System** (NEW):
- Dynamic size adjustment based on face area (`core/svg_exporter.py:_add_face_numbers`)
- Normal vector-based positioning for optimal visibility
- Unique numbering per face for assembly guidance

**Debug System**:
- Failed uploads auto-save to `core/debug_files/`
- Enable with `debug_mode=true` parameter

**Error Handling**:
- OpenCASCADE STEP writer issues handled via IFC pipeline
- BRepGProp import variations with version detection

## Common Tasks

```bash
# Convert STEP to papercraft SVG
curl -X POST \
  -F "file=@model.step" \
  http://localhost:8001/api/step/unfold \
  -o papercraft.svg

# Convert CityGML to STEP with IFC pipeline
curl -X POST \
  -F "file=@city.gml" \
  -F "use_ifc_pipeline=true" \
  -F "debug_mode=true" \
  http://localhost:8001/api/citygml/to-step \
  -o buildings.step

# Debug failed conversions
ls -la core/debug_files/
```

## Recent Changes

- **Face numbering**: Implemented dynamic sizing based on face area (commit d1a43ce)
- **API compatibility**: Fixed SVG file response format (commit 15afc1d)  
- **Backend consolidation**: Unified face number generation server-side (commit 1ce99cf)
- **Normal vectors**: Face numbers positioned using normal vectors (commit 73c1198)

## Dependencies

- **OpenCASCADE 7.9.0** - CAD kernel (`pythonocc-core`)
- **ifcopenshell 0.8.0** - IFC processing for CityGML pipeline
- **FastAPI** - Web framework
- **svgwrite** - SVG generation
- **lxml 5.3.0** - XML parsing for CityGML

## Known Issues

- **OCCT STEP writer**: `TCollection_AsciiString` errors with certain paths → Use IFC pipeline
- **BRepGProp imports**: Version-dependent API → Handled with fallbacks in `core/citygml_solidifier.py`
- **No test framework**: pytest recommended for future implementation

## Processing Options

**CityGML Options** (`services/citygml_processor.py`):
- `use_ifc_pipeline`: Use modern IFC pipeline (default: True)
- `lod_filter`: Level of Detail selection (0, 1, 2)
- `max_buildings`: Limit building count
- `min_building_area`: Filter by area
- `export_individual`: Separate STEP per building
- `debug_mode`: Enable detailed logging