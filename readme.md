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
- 📄 **マルチページレイアウト** - A4、A3、レター形式に最適化されたレイアウト
- 🎨 **印刷対応SVG** - 折り線、切り取り線、組み立てタブ付きのSVG生成
- 🔧 **産業用CADカーネル** - OpenCASCADE Technology 7.9.0を搭載
- 🚀 **高速APIサービス** - 包括的なエラーハンドリングを備えたRESTful API
- 🔌 **WebSocketリアルタイムプレビュー** - 3Dモデルから展開図へのリアルタイム変換とパラメータ調整

## 🏗️ アーキテクチャ

```
┌─────────────────┐
│   STEPファイル   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ファイルローダー  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ジオメトリ解析   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  展開エンジン    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ レイアウト管理   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SVGエクスポーター│
└────────┬────────┘
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

#### 2. システム状態

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
  "websocket_support": true,
  "supported_formats": ["step", "stp", "brep", "brp"]
}
```

## 🔌 WebSocket リアルタイムプレビュー

unfold-step2svgは、WebSocketを使用したリアルタイムプレビュー機能を提供しています。3Dモデルのアップロードやパラメータ変更を即座にSVG展開図に反映できます。

### 基本的な使用方法

```javascript
// WebSocket接続
const ws = new WebSocket('ws://localhost:8001/ws/preview');

// STEPファイルのアップロード
ws.send(JSON.stringify({
    type: 'update_model',
    data: {
        model: base64EncodedStepData,
        parameters: {
            scale_factor: 10.0,
            layout_mode: 'canvas',
            max_faces: 20
        }
    }
}));

// パラメータのみの更新（高速）
ws.send(JSON.stringify({
    type: 'update_parameters',
    data: {
        parameters: {
            scale_factor: 20.0
        }
    }
}));
```

### テストツール

#### Pythonクライアント
```bash
python test_websocket_client.py model.step
```

#### HTMLデモ
```bash
# ブラウザで開く
open examples/websocket_client.html
```

詳細なドキュメントは[docs/WEBSOCKET.md](docs/WEBSOCKET.md)をご覧ください。

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
│   └── cache_manager.py    # リアルタイム処理用キャッシュ
├── models/                 # データモデル
│   ├── request_models.py   # Pydanticモデル
│   └── websocket_models.py # WebSocketメッセージモデル
├── services/               # ビジネスロジック
│   ├── step_processor.py   # STEP処理
│   └── realtime_processor.py # WebSocketリアルタイム処理
├── config.py               # 設定
├── main.py                 # アプリケーションエントリーポイント
└── environment.yml         # Conda環境
```

### 使用技術

- **OpenCASCADE Technology 7.9.0** - 産業グレードのCADカーネル
- **pythonocc-core 7.9.0** - OpenCASCADEのPythonバインディング
- **FastAPI** - モダンなWebフレームワーク
- **websockets 13.1** - WebSocketサポート
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

### WebSocketリアルタイムプレビュー

```python
import asyncio
import websockets
import json
import base64

async def realtime_preview():
    uri = "ws://localhost:8001/ws/preview"
    async with websockets.connect(uri) as websocket:
        # STEPファイルをアップロード
        with open('model.step', 'rb') as f:
            model_data = base64.b64encode(f.read()).decode('utf-8')
        
        await websocket.send(json.dumps({
            "type": "update_model",
            "data": {
                "model": model_data,
                "parameters": {"scale_factor": 10.0}
            }
        }))
        
        # SVGプレビューを受信
        response = await websocket.recv()
        data = json.loads(response)
        
        if data['type'] == 'preview_update':
            with open('preview.svg', 'w') as f:
                f.write(data['data']['svg'])

asyncio.run(realtime_preview())
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