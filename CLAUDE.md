# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A 3D-to-2D papercraft generation system that converts STEP CAD files into unfolded SVG diagrams. Part of the 2025 Mitou Junior program, using OpenCASCADE Technology for 3D geometry processing.

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

# Test scripts
bash test_face_numbers.sh     # Test face numbering feature
bash test_layout_modes.sh     # Test different layout modes
python test_brep_export.py    # Test BREP export methods
```

## Architecture

**Processing Pipeline:**
1. **File Loading** (`core/file_loaders.py`) - STEP/BREP parsing
2. **Geometry Analysis** (`core/geometry_analyzer.py`) - Face classification
3. **Unfolding** (`core/unfold_engine.py`) - 3D to 2D transformation
4. **Layout** (`core/layout_manager.py`) - Page optimization
5. **Export** (`core/svg_exporter.py`) - SVG generation with face numbering

**Support Modules:**
- `core/brep_exporter.py` - BREP format export functionality
- `core/step_exporter.py` - STEP format export functionality

## API Endpoints

```bash
# STEP to SVG papercraft
POST /api/step/unfold
  Parameters: file, return_face_numbers, output_format, layout_mode, page_format, page_orientation, scale_factor

# System health check
GET /api/health
```

## Key Dependencies

- **OpenCASCADE 7.9.0** (`pythonocc-core`) - CAD kernel
- **FastAPI** - Web framework
- **svgwrite** - SVG generation
- **scipy/numpy** - Scientific computing

## Testing

Test scripts available:
- `test_brep_export.py` - Tests BREP export methods
- `test_face_numbering.py` - Face numbering functionality
- `test_polygon_overlap.py` - Polygon intersection detection

## Debug Mode

Failed operations save debug files to `core/debug_files/`:

```bash
curl -X POST \
  -F "file=@model.step" \
  -F "debug_mode=true" \
  http://localhost:8001/api/step/unfold
```

## Layout Modes

Two layout modes for SVG generation:
1. **Canvas mode** (default): Dynamic canvas size based on content
2. **Paged mode**: Fixed page sizes (A4, A3, Letter) with automatic pagination

## Face Numbering System

Face numbers are generated server-side based on normal vectors and dynamically sized according to face area. Implementation in `core/svg_exporter.py`.