# unfold-step2svg API Reference

STEPソリッドモデル（.step/.stp）を高精度展開図（SVG）に変換するAPI

## Base URL

```
http://localhost:8001
```

## Authentication

このAPIは認証不要です。

## Endpoints

### 1. STEP展開API

STEPファイルを受け取り、展開図（SVG）を生成します。

```
POST /api/step/unfold
```

#### Request

**Content-Type**: `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | STEPファイル（.step/.stp） |

#### Response

**Success (200)**
- **Content-Type**: `image/svg+xml`
- **Body**: SVGファイル

**Error Responses**

| Status Code | Description |
|-------------|-------------|
| 400 | 不正なファイル形式またはファイル読み込みエラー |
| 500 | サーバー内部エラー |
| 503 | OpenCASCADE Technology が利用できない |

#### Example

```bash
curl -X POST \
  http://localhost:8001/api/step/unfold \
  -H "Content-Type: multipart/form-data" \
  -F "file=@example.step" \
  -o output.svg
```

### 2. ヘルスチェック

APIの状態を確認します。

```
GET /api/health
```

#### Response

**Success (200)**

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "opencascade_available": true,
  "supported_formats": ["step"]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | APIの状態 (`healthy` または `degraded`) |
| `version` | string | APIのバージョン |
| `opencascade_available` | boolean | OpenCASCADE Technologyの利用可否 |
| `supported_formats` | array | サポートされているファイル形式 |

## Request Models

### BrepPapercraftRequest

STEP展開処理のパラメータ（現在は内部的にデフォルト値を使用）

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scale_factor` | float | 10.0 | スケールファクター |
| `units` | string | "mm" | 単位 |
| `max_faces` | integer | 20 | 最大面数 |
| `curvature_tolerance` | float | 0.1 | 曲率許容値 |
| `tab_width` | float | 5.0 | タブ幅 |
| `min_face_area` | float | 1.0 | 最小面積 |
| `unfold_method` | string | "planar" | 展開アルゴリズム |
| `show_scale` | boolean | true | スケール表示 |
| `show_fold_lines` | boolean | true | 折り線表示 |
| `show_cut_lines` | boolean | true | 切り線表示 |

## Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 400 | "STEPファイル（.step/.stp）のみ対応です。" | 対応していないファイル形式 |
| 400 | "STEPファイルの読み込みに失敗しました。" | ファイル解析エラー |
| 503 | "OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。" | 依存関係エラー |

## Examples

### JavaScript (Fetch API)

```javascript
const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch('http://localhost:8001/api/step/unfold', {
    method: 'POST',
    body: formData
  });
  
  if (response.ok) {
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    return url;
  } else {
    throw new Error('Upload failed');
  }
};
```

### Python (requests)

```python
import requests

def upload_step_file(file_path):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(
            'http://localhost:8001/api/step/unfold',
            files=files
        )
    
    if response.status_code == 200:
        with open('output.svg', 'wb') as out:
            out.write(response.content)
        return 'output.svg'
    else:
        raise Exception(f'Error: {response.status_code}')
```

## Notes

- 現在サポートされているファイル形式：STEP（.step/.stp）のみ
- 出力形式：SVG
- OpenCASCADE Technologyが必要
- 一時ファイルは自動的に管理されます
- 大きなファイルの処理には時間がかかる場合があります