# unfold-step2svg

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10.18-blue.svg)](https://www.python.org/)
[![OpenCASCADE](https://img.shields.io/badge/OpenCASCADE-7.9.0-green.svg)](https://www.opencascade.com/)
[![Mitou Junior](https://img.shields.io/badge/Mitou%20Junior-2025-orange.svg)](https://jr.mitou.org/)

3D STEP CAD files to papercraft SVG unfold diagrams converter / 3D STEPファイルから展開図SVGを生成するペーパークラフト変換システム

## 🎯 Overview / 概要

**unfold-step2svg** is a web service that converts 3D CAD models (STEP format) into 2D papercraft patterns (SVG format). Built with OpenCASCADE Technology, it analyzes 3D geometry and generates print-ready unfold diagrams for paper model creation.

このプロジェクトは、3D CADモデル（STEP形式）を2Dペーパークラフトパターン（SVG形式）に変換するWebサービスです。OpenCASCADE Technologyを使用して3Dジオメトリを解析し、紙工作用の印刷可能な展開図を生成します。

**2025年度 一般社団法人未踏 未踏ジュニアプロジェクト成果物**

## ✨ Features / 機能

- 📐 **3D to 2D Conversion** - Automatically unfolds 3D STEP models into 2D patterns
- 🏢 **CityGML Support** - Convert urban 3D models (CityGML/Plateau) to STEP format
- 📄 **Multi-page Layout** - Smart layout optimization for A4, A3, and Letter formats
- 🎨 **Print-ready SVG** - Generate SVGs with fold lines, cut lines, and assembly tabs
- 🔧 **Industrial CAD Kernel** - Powered by OpenCASCADE Technology 7.9.0
- 🚀 **Fast API Service** - RESTful API with comprehensive error handling

## 🏗️ Architecture / アーキテクチャ

```
┌─────────────────┐     ┌─────────────────┐
│   STEP File     │     │  CityGML File   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  File Loader    │     │ CityGML Parser  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│Geometry Analyzer│     │  IFC Converter  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ Unfold Engine   │     │  STEP Exporter  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       │
┌─────────────────┐              │
│ Layout Manager  │              │
└────────┬────────┘              │
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  SVG Exporter   │     │   STEP File     │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│   SVG Output    │
└─────────────────┘
```

## 🚀 Quick Start / クイックスタート

### Prerequisites / 前提条件

- Conda (Anaconda or Miniconda)
- Git
- Python 3.10.18

### Installation / インストール

```bash
# Clone the repository / リポジトリをクローン
git clone https://github.com/soynyuu/unfold-step2svg
cd unfold-step2svg

# Create and activate Conda environment / Conda環境を作成・有効化
conda env create -f environment.yml
conda activate unfold-step2svg

# Start the server / サーバーを起動
python main.py
```

The server will start at `http://localhost:8001`

### Health Check / ヘルスチェック

```bash
curl http://localhost:8001/api/health
```

## 📚 API Documentation / API ドキュメント

### Core Endpoints / 主要エンドポイント

#### 1. STEP to SVG Conversion / STEP→SVG変換

```bash
POST /api/step/unfold
```

Convert STEP files to papercraft SVG patterns.

**Request:**
- Form data: `file` (STEP file, .step or .stp)

**Response:**
- Success: SVG file (image/svg+xml)
- Error: JSON error message

**Example:**
```bash
curl -X POST \
  -F "file=@your_model.step" \
  http://localhost:8001/api/step/unfold \
  -o papercraft.svg
```

#### 2. CityGML to STEP Conversion / CityGML→STEP変換

```bash
POST /api/citygml/to-step
```

Convert CityGML urban models to STEP format.

**Request:**
- Form data: `file` (CityGML file)
- Optional: `lod_filter`, `min_building_area`, `max_buildings`, `use_ifc_pipeline`

**Response:**
- Success: STEP file or ZIP (for multiple buildings)
- Error: JSON error message

**Example:**
```bash
curl -X POST \
  -F "file=@city_model.gml" \
  -F "lod_filter=2" \
  -F "max_buildings=10" \
  http://localhost:8001/api/citygml/to-step \
  -o buildings.step
```

#### 3. CityGML Validation / CityGML検証

```bash
POST /api/citygml/validate
```

Validate CityGML files and get building statistics.

**Example:**
```bash
curl -X POST \
  -F "file=@city_model.gml" \
  http://localhost:8001/api/citygml/validate
```

#### 4. System Health / システム状態

```bash
GET /api/health
```

Check system status and capabilities.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "opencascade_available": true,
  "citygml_support": true,
  "supported_formats": ["step", "stp", "citygml", "gml"]
}
```

## 🛠️ Development / 開発

### Project Structure / プロジェクト構造

```
unfold-step2svg/
├── api/                    # API endpoints
│   └── endpoints.py        # FastAPI routes
├── core/                   # Core processing modules
│   ├── file_loaders.py     # STEP/BREP file loading
│   ├── geometry_analyzer.py # 3D geometry analysis
│   ├── unfold_engine.py    # 3D to 2D unfolding
│   ├── layout_manager.py   # Page layout optimization
│   ├── svg_exporter.py     # SVG generation
│   ├── citygml_parser.py   # CityGML XML parsing
│   ├── citygml_to_ifc_converter.py # CityGML to IFC
│   └── ifc_to_step_converter.py    # IFC to STEP
├── models/                 # Data models
│   └── request_models.py   # Pydantic models
├── services/               # Business logic
│   └── citygml_processor.py # CityGML processing
├── config.py               # Configuration
├── main.py                 # Application entry point
└── environment.yml         # Conda environment
```

### Core Technologies / 使用技術

- **OpenCASCADE Technology 7.9.0** - Industrial-grade CAD kernel
- **pythonocc-core 7.9.0** - Python bindings for OpenCASCADE
- **FastAPI** - Modern web framework
- **ifcopenshell 0.8.0** - IFC/BIM file processing
- **lxml 5.3.0** - XML parsing for CityGML
- **svgwrite** - SVG generation
- **scipy/numpy** - Scientific computing

### Debug Mode / デバッグモード

Failed processing automatically saves debug files to `core/debug_files/` for troubleshooting.

```bash
# Enable debug mode for detailed logs
curl -X POST \
  -F "file=@model.step" \
  -F "debug_mode=true" \
  http://localhost:8001/api/step/unfold
```

## 📝 Examples / 使用例

### Basic STEP Unfolding / 基本的な展開図生成

```python
import requests

# Upload and convert STEP file
with open('model.step', 'rb') as f:
    response = requests.post(
        'http://localhost:8001/api/step/unfold',
        files={'file': f}
    )

# Save the SVG output
with open('papercraft.svg', 'wb') as f:
    f.write(response.content)
```

### CityGML Processing / CityGML処理

```python
import requests

# Convert CityGML to STEP with filtering
with open('tokyo_plateau.gml', 'rb') as f:
    response = requests.post(
        'http://localhost:8001/api/citygml/to-step',
        files={'file': f},
        data={
            'lod_filter': 2,
            'min_building_area': 100,
            'max_buildings': 50,
            'export_individual': True
        }
    )

# Save the STEP file(s)
with open('buildings.zip', 'wb') as f:
    f.write(response.content)
```

## 🤝 Contributing / 貢献

Contributions are welcome! Please feel free to submit issues and pull requests.

貢献を歓迎します！イシューやプルリクエストをお気軽にお送りください。

## 📄 License / ライセンス

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments / 謝辞

- **Mitou Junior 2025** - For supporting this project
- **OpenCASCADE Technology** - For the powerful CAD kernel
- **pythonocc Community** - For Python bindings and support

## 📧 Contact / 連絡先

- **GitHub:** [https://github.com/soynyuu/unfold-step2svg](https://github.com/soynyuu/unfold-step2svg)
- **Issues:** [Report bugs or request features](https://github.com/soynyuu/unfold-step2svg/issues)

---

Made with ❤️ for the Mitou Junior 2025 Program