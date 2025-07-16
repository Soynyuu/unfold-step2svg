# unfold-step2svg
## What is this?
このプログラムは3Dモデルを展開図化することができるソフトウェアで、Conda上で動作します。

2025年度一般社団法人未踏 未踏ジュニアの成果物です。

3Dソリッド形式として広く知られるSTEP(Standard for the Exchange of Product model data,ISO 10303)形式の3Dモデルを読み込み、ジオメトリ・点情報・面情報を元にして展開図を作成してSVGにプロットすることが可能です。

## How to Use,make devel env?
reqements
- conda
- git

~~~ bash
git clone https://github.com/soynyuu/unfold-step2svg
cd unfold-step2svg
~~~

~~~ bash
conda env create -f environment.yml
conda activate unfold-step2svg
~~~

~~~
python
~~~

## APIリファレンス（backend/brep_papercraft_api.py 全エンドポイント）


## 1. STEP展開図SVG生成

### `POST /api/step/unfold`
- **概要**: STEPファイル（.step/.stp）をアップロードし、展開図（SVG）を返すAPI
- **リクエスト**:
    - フォームデータ: `file`（STEPファイル, 必須）
- **レスポンス**:
    - 成功: SVGファイル（Content-Type: image/svg+xml, Content-Disposition: attachment）
    - 失敗: エラーメッセージ（JSON）
- **注意**: .step/.stp以外は受け付けません

#### curl例
```sh
curl -X POST \
  -F "file=@your_model.step" \
  http://localhost:8001/api/step/unfold \
  -o unfolded.svg
```

---

## 2. BREP展開図生成（旧API, 非推奨）

### `POST /api/brep/generate`
- **概要**: BREPファイルをアップロードし、展開図（SVG）を返すAPI
- **リクエスト**:
    - フォームデータ: `file`（BREPファイル, 必須）
    - その他パラメータ: scale_factor, units, max_faces, curvature_tolerance, tab_width, min_face_area, unfold_method, show_scale, show_fold_lines, show_cut_lines
- **レスポンス**:
    - 成功: SVGファイル（Content-Type: image/svg+xml, Content-Disposition: attachment, 各種統計ヘッダ付き）
    - 失敗: エラーメッセージ（JSON）
- **注意**: STEP専用化により今後廃止予定

---

## 3. BREP解析情報取得

### `POST /api/brep/analyze`
- **概要**: BREPファイルをアップロードし、展開図生成前の詳細情報（面・エッジ・推奨パラメータ等）を返すAPI
- **リクエスト**:
    - フォームデータ: `file`（BREPファイル, 必須）
- **レスポンス**:
    - 成功: 解析情報（JSON）
    - 失敗: エラーメッセージ（JSON）

---

## 4. ヘルスチェック

### `GET /api/brep/health`
- **概要**: サーバー・OpenCASCADEの稼働状況・対応フォーマットを返すAPI
- **レスポンス**:
    - status: "healthy" or "degraded"
    - version: サーバーバージョン
    - opencascade_available: bool
    - supported_formats: ["brep", "step", "iges"]

---

## 5. サーバー起動

- **main()**: `python brep_papercraft_api.py` で直接起動可能
- デフォルトポート: 8001

---

## 備考
- STEP専用化により、今後は `/api/step/unfold` の利用を推奨
- BREP/IGES等の旧APIは将来的に廃止予定