# unfold-step2svg

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-teal.svg)](https://fastapi.tiangolo.com/)
[![OpenCASCADE](https://img.shields.io/badge/OpenCASCADE-7.9.0-green.svg)](https://www.opencascade.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](https://www.docker.com/)
[![Mitou Junior](https://img.shields.io/badge/未踏ジュニア-2025-orange.svg)](https://jr.mitou.org/)

> 3D STEP を高精度な 2D ペーパークラフト SVG に。シンプルな API、実用的なレイアウト、印刷まで一気通貫。

English: A tiny FastAPI service that unfolds STEP into print‑ready SVG papercraft. Powered by OpenCASCADE.

## 特長

- 📐 STEP→SVG: 3D（.step/.stp）から2D展開図を自動生成
- 🧩 折/切/タブ: 折り線・切り線・組み立てタブを描画
- 🖨️ レイアウト: `canvas`/`paged`（A4/A3/Letter、縦横）
- 🔢 面番号: 面番号データの返却に対応（オプション）
- 🔄 スケール: `scale_factor` で簡単スケーリング
- 🧰 API/CLI 友好: SVGまたはJSONで取得しワークフローに組み込みやすい

## クイックスタート

前提: Conda もしくは Python 3.10 が利用可能

```bash
# 1) Clone
git clone https://github.com/soynyuu/unfold-step2svg
cd unfold-step2svg

# 2) Create env (Conda 推奨)
conda env create -f environment.yml && conda activate unfold-step2svg

# 3) Run API (dev)
python main.py  # http://localhost:8001

# 4) Health check
curl http://localhost:8001/api/health
```

STEP を送って SVG を受け取る（cURL）

```bash
curl -X POST \
  -F "file=@example.step" \
  "http://localhost:8001/api/step/unfold" \
  -o output.svg
```

JSON で受け取る（SVG文字列や面番号を含めたい場合）

```bash
curl -X POST \
  -F "file=@example.step" \
  -F "output_format=json" \
  -F "return_face_numbers=true" \
  "http://localhost:8001/api/step/unfold" | jq .stats
```

## Docker/Podman

```bash
# Build & run (Docker)
docker build -t unfold-step2svg .
docker compose up -d
curl http://localhost:8001/api/health

# Podman helper
bash podman-deploy.sh build-run
```

## プロジェクト構成

```
core/            # 展開パイプライン（I/O・解析・展開・レイアウト・エクスポート）
  file_loaders.py
  geometry_analyzer.py
  unfold_engine.py
  layout_manager.py
  svg_exporter.py
  step_exporter.py
api/             # FastAPI ルーター/設定
  endpoints.py
  config.py
services/        # STEP 処理ヘルパ
  step_processor.py
models/, utils/  # 共有型/ユーティリティ
tests & examples # test_*.py, test_*.sh, sample outputs
```

## 設定（環境変数）

- `PORT`: API のポート（デフォルト: 8001）
- `FRONTEND_URL`: CORS 許可オリジン（例: `http://localhost:3001`）
- `CORS_ALLOW_ALL`: すべて許可（`true`/`false`、開発向け）

`.env.development` / `.env.production` を用意すると自動で読み込まれます。

## API ドキュメント

- OpenAPI UI: `http://localhost:8001/docs`（Swagger UI）/ `http://localhost:8001/redoc`
- 詳細は `API_REFERENCE.md` を参照

主要エンドポイント（抜粋）

- `POST /api/step/unfold` STEP→SVG/JSON 変換
  - フォーム: `file` (必須), `layout_mode`, `page_format`, `page_orientation`, `scale_factor`, `output_format`, `return_face_numbers`
- `GET /api/health` ヘルスチェック

## 開発

スタイル: Python 3.10 / PEP 8, 4-space indent, type hints。I/O は `file_loaders`、ジオメトリは `geometry_analyzer`、レイアウトは `layout_manager`、エクスポートは `svg_exporter` / `step_exporter` に分離。

```bash
# Run (dev)
python main.py

# Tests / Examples
python test_polygon_overlap.py
bash test_layout_modes.sh
python test_brep_export.py
```

OpenCASCADE (OCCT) が未インストールでも API は起動します（機能は制限されます）。

## よくある質問

- サポート拡張子は？ → `.step`/`.stp`
- 出力は？ → SVG（ファイル返却）/ JSON（文字列返却）
- レイアウトは？ → `canvas`（単一キャンバス）/ `paged`（A4/A3/Letter、縦横）

## ロードマップ

- Nesting 最適化（面配置の自動最密化）
- タブ生成の詳細制御（角丸/実寸幅）
- 大規模モデル向けの分割/ストリーミング
- 追加フォーマット入出力（BRepなど）

## 貢献方法

Issue/PR 歓迎です。変更点・背景・再現手順（必要なら SVG のスクショ）を添えてください。コミットは「fix: ...」「feat: ...」のように短く明確に。

## ライセンス

MIT License

## 謝辞

- OpenCASCADE Technology
- 一般社団法人未踏 未踏ジュニア（2025）

— Made with ❤️ by the unfold-step2svg team

