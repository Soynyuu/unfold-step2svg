# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a 3D-to-2D papercraft generation system that converts STEP (.step/.stp) CAD files into unfolded SVG diagrams. It's a FastAPI-based web service built for the 2025 Mitou Junior program, using OpenCASCADE Technology (OCCT) for 3D geometry processing.

Repository: https://github.com/Soynyuu/unfold-step2svg

## Development Environment Setup

The project uses Conda for environment management:

```bash
conda env create -f environment.yml
conda activate unfold-step2svg
```

## Running the Application

**Development server:**
```bash
python main.py
```
- Runs on `localhost:8001` by default
- Use the `PORT` environment variable to change the port
- Supports hot reload during development

**Health check:**
```bash
curl http://localhost:8001/api/health
```

## Core Architecture

The system follows a modular pipeline architecture:

**STEP to SVG Pipeline:**
1. **File Loading** (`core/file_loaders.py`) - STEP/BREP file parsing with OpenCASCADE
2. **Geometry Analysis** (`core/geometry_analyzer.py`) - 3D shape analysis and face classification
3. **Unfolding Engine** (`core/unfold_engine.py`) - 3D-to-2D coordinate transformation algorithms
4. **Layout Manager** (`core/layout_manager.py`) - Multi-page layout optimization (A4, A3, Letter)
5. **SVG Export** (`core/svg_exporter.py`) - Print-ready SVG generation with fold/cut lines

**CityGML to STEP Pipeline (Dual Architecture):**

The system supports two conversion pipelines for CityGML processing:

**Modern IFC Pipeline (Default, Recommended):**
1. **CityGML Parser** (`core/citygml_parser.py`) - XML parsing with namespace handling for CityGML/Plateau files
2. **CityGML to IFC Converter** (`core/citygml_to_ifc_converter.py`) - Converts CityGML building geometries to IFC format using ifcopenshell
3. **IFC to STEP Converter** (`core/ifc_to_step_converter.py`) - Extracts geometry from IFC and generates STEP files, bypassing OpenCASCADE STEP writer issues

**Legacy OpenCASCADE Pipeline:**
1. **CityGML Parser** (`core/citygml_parser.py`) - Same XML parsing as modern pipeline
2. **CityGML Solidifier** (`core/citygml_solidifier.py`) - MultiSurface to Solid conversion using direct OpenCASCADE operations
3. **STEP Exporter** (`core/step_exporter.py`) - Export solid geometries to STEP format

The main processing orchestrator is `services/citygml_processor.py`, which selects the pipeline based on the `use_ifc_pipeline` option (defaults to `True`).

## API Endpoints

**STEP to SVG conversion:**
- `POST /api/step/unfold` - Upload STEP file, returns SVG

**CityGML to STEP conversion (NEW):**
- `POST /api/citygml/to-step` - Upload CityGML file, returns STEP file
- `POST /api/citygml/validate` - Validate CityGML file and get building statistics

**System status:**
- `GET /api/health` - System status, OpenCASCADE availability, and CityGML capabilities

See `API_REFERENCE.md` for complete API documentation.

## Key Dependencies

- **OpenCASCADE Technology (OCCT) 7.9.0** - Industrial CAD kernel for 3D geometry processing
- **pythonocc-core 7.9.0** - Python bindings for OCCT  
- **ifcopenshell 0.8.0** - IFC file processing library for the modern CityGML pipeline
- **lxml 5.3.0** - XML parsing for CityGML files
- **FastAPI** - Web framework
- **svgwrite** - SVG generation
- **scipy/numpy** - Scientific computing

## File Organization

- `api/endpoints.py` - FastAPI route definitions
- `config.py` - Application configuration and OCCT availability checking
- `models/request_models.py` - Pydantic models for API validation
- `core/debug_files/` - Automatic debug file storage for troubleshooting

## Development Notes

- **No testing framework** - Tests should be implemented using pytest
- **Debug system** - Failed uploads automatically save debug files to `core/debug_files/`
- **Error handling** - Comprehensive error checking with meaningful messages for OpenCASCADE operations
- **CORS enabled** - Configured for frontend integration
- **CityGML Support** - Supports CityGML 1.0, 2.0, 3.0 and Plateau extensions with intelligent solid conversion

## Code Conventions

- Uses Python 3.10.18
- Follows modular design with clear separation of concerns
- OpenCASCADE operations include proper error handling and resource cleanup
- API responses include performance statistics and processing metadata
- CityGML processing includes namespace auto-detection and LoD filtering

## CityGML Processing Features

- **Dual Pipeline Architecture** - Modern IFC-based pipeline (default) and legacy OpenCASCADE pipeline
- **Smart Solid Conversion** - Converts MultiSurface geometries to proper 3D solids
- **Plateau Support** - Handles Japanese Plateau format extensions and namespaces
- **LoD Filtering** - Supports Level of Detail selection (LoD0, LoD1, LoD2)
- **Building Filtering** - Filter by area, count, and other criteria
- **Individual Export** - Option to export each building as separate STEP file
- **Validation API** - Pre-process validation with building statistics and time estimates
- **Enhanced Error Reporting** - Detailed processing stage identification and performance metrics

## Pipeline Selection and Configuration

**CityGML Processing Options** (`services/citygml_processor.py`):
- `use_ifc_pipeline: bool = True` - Use modern IFC pipeline (recommended for stability)
- `ifc_schema_version: str = "IFC4"` - IFC schema version for intermediate conversion
- `save_intermediate_ifc: bool = False` - Save IFC files for debugging
- `debug_mode: bool = False` - Enable detailed processing logs

**Pipeline Behavior:**
- **IFC Pipeline**: CityGML → IFC (via ifcopenshell) → STEP (custom format generation)
- **Legacy Pipeline**: CityGML → OpenCASCADE Solids → STEP (via OpenCASCADE writer)

The IFC pipeline bypasses known OpenCASCADE STEP writer issues and provides more reliable geometry extraction.

## Common Debugging Commands

**Test CityGML conversion:**
```bash
curl -X POST \
  -F "file=@your_citygml.gml" \
  -F "debug_mode=true" \
  -F "use_ifc_pipeline=true" \
  http://localhost:8001/api/citygml/to-step \
  -o output.step
```

**Check processing capabilities:**
```bash
curl http://localhost:8001/api/health
```

**Validate CityGML before processing:**
```bash
curl -X POST \
  -F "file=@your_citygml.gml" \
  http://localhost:8001/api/citygml/validate
```

## OpenCASCADE Integration Issues

**Known Issues:**
- `TCollection_AsciiString(): NULL pointer passed to constructor` - OpenCASCADE STEP writer fails with certain path encodings
- `BRepGProp.SurfaceProperties` - Requires correct import: use `brepgprop.SurfaceProperties` (modern API) or `brepgprop_SurfaceProperties` (legacy)

**Solutions:**
- IFC pipeline bypasses OpenCASCADE STEP writer entirely
- BRepGProp imports are handled with version detection and fallbacks in `core/citygml_solidifier.py`