# unfold-step2svg

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10.18-blue.svg)](https://www.python.org/)
[![OpenCASCADE](https://img.shields.io/badge/OpenCASCADE-7.9.0-green.svg)](https://www.opencascade.com/)
[![Mitou Junior](https://img.shields.io/badge/未踏ジュニア-2025-orange.svg)](https://jr.mitou.org/)

3D STEPファイルから展開図SVGを生成するペーパークラフト変換システム

## 🎯 概要

**unfold-step2svg**は、3D CADモデル（STEP形式）を2Dペーパークラフトパターン（SVG形式）に変換するWebサービスです。OpenCASCADE Technologyを使用して3Dジオメトリを解析し、紙工作用の印刷可能な展開図を生成します。

**2025年度 一般社団法人未踏 未踏ジュニアプロジェクト成果物**

### English
*A web service that converts 3D CAD models (STEP format) into 2D papercraft patterns (SVG format). Built with OpenCASCADE Technology for analyzing 3D geometry and generating print-ready unfold diagrams.*

## ✨ 機能

- 📐 **3Dから2Dへの変換** - 3D STEPモデルを自動的に2Dパターンに展開
- 🏢 **CityGMLサポート** - 都市3Dモデル（CityGML/Plateau）をSTEP形式に変換
- 📄 **マルチページレイアウト** - A4、A3、レター形式に最適化されたレイアウト
- 🎨 **印刷対応SVG** - 折り線、切り取り線、組み立てタブ付きのSVG生成
- 🔧 **産業用CADカーネル** - OpenCASCADE Technology 7.9.0を搭載
- 🚀 **高速APIサービス** - 包括的なエラーハンドリングを備えたRESTful API

## 🏗️ アーキテクチャ

```
┌─────────────────┐     ┌─────────────────┐
│   STEPファイル   │     │  CityGMLファイル │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  ファイルローダー  │     │ CityGMLパーサー  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ ジオメトリ解析   │     │  IFCコンバーター │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  展開エンジン    │     │ STEPエクスポーター│
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       │
┌─────────────────┐              │
│ レイアウト管理   │              │
└────────┬────────┘              │
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  SVGエクスポーター│     │   STEPファイル   │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│   SVG出力       │
└─────────────────┘
```

## 🚀 クイックスタート

### 前提条件

- Conda (Anaconda または Miniconda)
- Git
- Python 3.10.18

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/soynyuu/unfold-step2svg
cd unfold-step2svg

# Conda環境を作成・有効化
conda env create -f environment.yml
conda activate unfold-step2svg

# サーバーを起動
python main.py
```

サーバーは `http://localhost:8001` で起動します

### ヘルスチェック

```bash
curl http://localhost:8001/api/health
```

## 📚 API ドキュメント

### 主要エンドポイント

#### 1. STEP→SVG変換

```bash
POST /api/step/unfold
```

STEPファイルをペーパークラフトSVGパターンに変換します。

**リクエスト:**
- フォームデータ: `file` (STEPファイル, .step または .stp)

**レスポンス:**
- 成功: SVGファイル (image/svg+xml)
- エラー: JSONエラーメッセージ

**例:**
```bash
curl -X POST \
  -F "file=@your_model.step" \
  http://localhost:8001/api/step/unfold \
  -o papercraft.svg
```

#### 2. CityGML→STEP変換

```bash
POST /api/citygml/to-step
```

CityGML都市モデルをSTEP形式に変換します。

**リクエスト:**
- フォームデータ: `file` (CityGMLファイル)
- オプション: `lod_filter`, `min_building_area`, `max_buildings`, `use_ifc_pipeline`

**レスポンス:**
- 成功: STEPファイルまたはZIP（複数建物の場合）
- エラー: JSONエラーメッセージ

**例:**
```bash
curl -X POST \
  -F "file=@city_model.gml" \
  -F "lod_filter=2" \
  -F "max_buildings=10" \
  http://localhost:8001/api/citygml/to-step \
  -o buildings.step
```

#### 3. CityGML検証

```bash
POST /api/citygml/validate
```

CityGMLファイルを検証し、建物統計を取得します。

**例:**
```bash
curl -X POST \
  -F "file=@city_model.gml" \
  http://localhost:8001/api/citygml/validate
```

#### 4. システム状態

```bash
GET /api/health
```

システムステータスと機能を確認します。

**レスポンス:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "opencascade_available": true,
  "citygml_support": true,
  "supported_formats": ["step", "stp", "citygml", "gml"]
}
```

## 🛠️ 開発

### プロジェクト構造

```
unfold-step2svg/
├── api/                    # APIエンドポイント
│   └── endpoints.py        # FastAPIルート
├── core/                   # コア処理モジュール
│   ├── file_loaders.py     # STEP/BREPファイル読み込み
│   ├── geometry_analyzer.py # 3Dジオメトリ解析
│   ├── unfold_engine.py    # 3Dから2Dへの展開
│   ├── layout_manager.py   # ページレイアウト最適化
│   ├── svg_exporter.py     # SVG生成
│   ├── citygml_parser.py   # CityGML XMLパース
│   ├── citygml_to_ifc_converter.py # CityGMLからIFCへ
│   └── ifc_to_step_converter.py    # IFCからSTEPへ
├── models/                 # データモデル
│   └── request_models.py   # Pydanticモデル
├── services/               # ビジネスロジック
│   └── citygml_processor.py # CityGML処理
├── config.py               # 設定
├── main.py                 # アプリケーションエントリーポイント
└── environment.yml         # Conda環境
```

### 使用技術

- **OpenCASCADE Technology 7.9.0** - 産業グレードのCADカーネル
- **pythonocc-core 7.9.0** - OpenCASCADEのPythonバインディング
- **FastAPI** - モダンなWebフレームワーク
- **ifcopenshell 0.8.0** - IFC/BIMファイル処理
- **lxml 5.3.0** - CityGML用のXMLパース
- **svgwrite** - SVG生成
- **scipy/numpy** - 科学計算

### デバッグモード

処理に失敗した場合、トラブルシューティング用のデバッグファイルが自動的に `core/debug_files/` に保存されます。

```bash
# 詳細ログのためのデバッグモード有効化
curl -X POST \
  -F "file=@model.step" \
  -F "debug_mode=true" \
  http://localhost:8001/api/step/unfold
```

## 📝 使用例

### 基本的な展開図生成

```python
import requests

# STEPファイルをアップロードして変換
with open('model.step', 'rb') as f:
    response = requests.post(
        'http://localhost:8001/api/step/unfold',
        files={'file': f}
    )

# SVG出力を保存
with open('papercraft.svg', 'wb') as f:
    f.write(response.content)
```

### CityGML処理

```python
import requests

# フィルタリング付きでCityGMLをSTEPに変換
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

# STEPファイルを保存
with open('buildings.zip', 'wb') as f:
    f.write(response.content)
```

## 🤝 貢献

貢献を歓迎します！イシューやプルリクエストをお気軽にお送りください。

## 📄 ライセンス

このプロジェクトはMITライセンスの下でライセンスされています - 詳細は[LICENSE](LICENSE)ファイルをご覧ください。

## 🙏 謝辞

- **未踏ジュニア 2025** - プロジェクトのサポート
- **OpenCASCADE Technology** - 強力なCADカーネル
- **pythonocc コミュニティ** - Pythonバインディングとサポート

## 📧 連絡先

- **GitHub:** [https://github.com/soynyuu/unfold-step2svg](https://github.com/soynyuu/unfold-step2svg)
- **Issues:** [バグ報告や機能リクエスト](https://github.com/soynyuu/unfold-step2svg/issues)

---

Made with ❤️ for the Mitou Junior 2025 Program