# WebSocket API Documentation

## 概要

unfold-step2svgは、3Dモデルから展開図へのリアルタイムプレビューを実現するWebSocket APIを提供しています。このAPIを使用することで、モデルの読み込みやパラメータの変更を即座にSVG展開図に反映させることができます。

## 主な特徴

- **リアルタイム双方向通信**: WebSocketによる低レイテンシーな通信
- **インクリメンタル更新**: パラメータ変更時に形状データを再計算せずに高速更新
- **キャッシュシステム**: 形状データの自動キャッシュによる処理高速化
- **複数クライアント対応**: 同時に複数のクライアントが独立して動作可能
- **Base64エンコーディング**: バイナリSTEPデータの安全な転送

## 接続方法

### エンドポイント

```
ws://localhost:8001/ws/preview
```

### 接続例 (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/preview');

ws.onopen = (event) => {
    console.log('WebSocket接続が確立されました');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('受信:', data);
};

ws.onerror = (error) => {
    console.error('エラー:', error);
};

ws.onclose = (event) => {
    console.log('接続が切断されました');
};
```

### 接続例 (Python)

```python
import asyncio
import websockets
import json

async def connect():
    uri = "ws://localhost:8001/ws/preview"
    async with websockets.connect(uri) as websocket:
        # 接続状態メッセージを受信
        response = await websocket.recv()
        data = json.loads(response)
        print(f"接続成功: {data}")
```

## メッセージプロトコル

### メッセージ形式

すべてのメッセージはJSON形式で、以下の基本構造を持ちます：

```json
{
    "type": "message_type",
    "data": {
        // メッセージ固有のデータ
    }
}
```

## クライアント → サーバーメッセージ

### 1. モデル更新 (update_model)

新しい3Dモデルをアップロードし、SVG展開図を生成します。

```json
{
    "type": "update_model",
    "data": {
        "model": "base64_encoded_step_data",
        "parameters": {
            "scale_factor": 10.0,
            "layout_mode": "canvas",
            "page_format": "A4",
            "page_orientation": "portrait",
            "units": "mm",
            "tab_width": 5.0,
            "min_face_area": 1.0,
            "max_faces": 20,
            "show_scale": true,
            "show_fold_lines": true,
            "show_cut_lines": true
        }
    }
}
```

#### パラメータ詳細

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|------------|------|
| scale_factor | float | 10.0 | 展開図のスケール倍率 |
| layout_mode | string | "canvas" | レイアウトモード ("canvas" / "paged") |
| page_format | string | "A4" | 用紙サイズ ("A4" / "A3" / "Letter" / "Legal") |
| page_orientation | string | "portrait" | 用紙の向き ("portrait" / "landscape") |
| units | string | "mm" | 単位 ("mm" / "cm" / "inch") |
| tab_width | float | 5.0 | 接続タブの幅 |
| min_face_area | float | 1.0 | 処理する最小面積 |
| max_faces | int | 20 | 処理する最大面数 |
| show_scale | bool | true | スケールインジケーターを表示 |
| show_fold_lines | bool | true | 折り線を表示 |
| show_cut_lines | bool | true | 切り取り線を表示 |

### 2. パラメータ更新 (update_parameters)

既存のモデルに対してパラメータのみを更新します（高速処理）。

```json
{
    "type": "update_parameters",
    "data": {
        "parameters": {
            "scale_factor": 20.0,
            "layout_mode": "paged"
        }
    }
}
```

### 3. Ping (ping)

接続確認用のpingメッセージ。

```json
{
    "type": "ping",
    "data": {}
}
```

## サーバー → クライアントメッセージ

### 1. 接続状態 (connection_status)

接続時に自動送信される初期メッセージ。

```json
{
    "type": "connection_status",
    "data": {
        "status": "connected",
        "client_id": "uuid-string",
        "opencascade_available": true
    }
}
```

### 2. プレビュー更新 (preview_update)

SVG展開図の生成完了時に送信されます。

```json
{
    "type": "preview_update",
    "data": {
        "svg": "<svg>...</svg>",
        "stats": {
            "face_count": 12,
            "processing_time": 0.45,
            "page_count": 1,
            "scale_factor": 10.0
        },
        "status": "success",
        "cached": false
    }
}
```

### 3. ステータス (status)

処理状態の更新通知。

```json
{
    "type": "status",
    "data": {
        "status": "processing",
        "message": "モデルを処理中...",
        "progress": 0.5
    }
}
```

ステータス値：
- `idle`: アイドル状態
- `processing`: 処理中
- `success`: 処理成功
- `error`: エラー発生
- `cached`: キャッシュから取得

### 4. エラー (error)

エラー発生時のメッセージ。

```json
{
    "type": "error",
    "data": {
        "message": "エラーの詳細",
        "status": "error",
        "details": {
            // 追加のエラー情報
        }
    }
}
```

### 5. Pong (pong)

pingに対する応答。

```json
{
    "type": "pong",
    "data": {
        "timestamp": 1234567890
    }
}
```

## 使用例

### 完全な実装例 (JavaScript)

```javascript
class WebSocketClient {
    constructor(url = 'ws://localhost:8001/ws/preview') {
        this.url = url;
        this.ws = null;
        this.clientId = null;
    }

    connect() {
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('接続完了');
            };

            this.ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
                
                if (message.type === 'connection_status') {
                    this.clientId = message.data.client_id;
                    resolve(this.clientId);
                }
            };

            this.ws.onerror = (error) => {
                reject(error);
            };
        });
    }

    handleMessage(message) {
        switch (message.type) {
            case 'connection_status':
                console.log('接続ID:', message.data.client_id);
                break;
            
            case 'preview_update':
                this.onPreviewUpdate(message.data);
                break;
            
            case 'status':
                console.log('ステータス:', message.data.status, message.data.message);
                break;
            
            case 'error':
                console.error('エラー:', message.data.message);
                break;
        }
    }

    async uploadModel(file, parameters = {}) {
        const arrayBuffer = await file.arrayBuffer();
        const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
        
        this.send('update_model', {
            model: base64,
            parameters: parameters
        });
    }

    updateParameters(parameters) {
        this.send('update_parameters', {
            parameters: parameters
        });
    }

    send(type, data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: type,
                data: data
            }));
        }
    }

    onPreviewUpdate(data) {
        // SVGを表示
        document.getElementById('svg-container').innerHTML = data.svg;
        console.log('統計情報:', data.stats);
        
        if (data.cached) {
            console.log('キャッシュから取得');
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// 使用例
const client = new WebSocketClient();

async function main() {
    // 接続
    await client.connect();
    
    // ファイル選択時
    document.getElementById('file-input').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            await client.uploadModel(file, {
                scale_factor: 10.0,
                layout_mode: 'canvas',
                max_faces: 20
            });
        }
    });
    
    // パラメータ変更時
    document.getElementById('scale-slider').addEventListener('input', (e) => {
        client.updateParameters({
            scale_factor: parseFloat(e.target.value)
        });
    });
}

main();
```

### 完全な実装例 (Python)

```python
import asyncio
import websockets
import json
import base64
from pathlib import Path

class WebSocketClient:
    def __init__(self, url='ws://localhost:8001/ws/preview'):
        self.url = url
        self.websocket = None
        self.client_id = None
    
    async def connect(self):
        """WebSocket接続を確立"""
        self.websocket = await websockets.connect(self.url)
        
        # 接続状態メッセージを待つ
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data['type'] == 'connection_status':
            self.client_id = data['data']['client_id']
            print(f"接続成功: Client ID = {self.client_id}")
            return True
        return False
    
    async def upload_model(self, file_path, parameters=None):
        """STEPファイルをアップロード"""
        with open(file_path, 'rb') as f:
            model_data = f.read()
            encoded_data = base64.b64encode(model_data).decode('utf-8')
        
        message = {
            "type": "update_model",
            "data": {
                "model": encoded_data,
                "parameters": parameters or {
                    "scale_factor": 10.0,
                    "layout_mode": "canvas",
                    "max_faces": 20
                }
            }
        }
        
        await self.websocket.send(json.dumps(message))
        
        # レスポンスを待つ
        while True:
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if data['type'] == 'preview_update':
                return data['data']
            elif data['type'] == 'error':
                raise Exception(data['data']['message'])
    
    async def update_parameters(self, parameters):
        """パラメータのみを更新"""
        message = {
            "type": "update_parameters",
            "data": {
                "parameters": parameters
            }
        }
        
        await self.websocket.send(json.dumps(message))
        
        # レスポンスを待つ
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data['type'] == 'preview_update':
            return data['data']
        elif data['type'] == 'error':
            raise Exception(data['data']['message'])
    
    async def ping(self):
        """接続確認"""
        message = {
            "type": "ping",
            "data": {}
        }
        
        await self.websocket.send(json.dumps(message))
        
        response = await self.websocket.recv()
        data = json.loads(response)
        
        return data['type'] == 'pong'
    
    async def disconnect(self):
        """接続を切断"""
        if self.websocket:
            await self.websocket.close()

async def main():
    client = WebSocketClient()
    
    try:
        # 接続
        await client.connect()
        
        # モデルをアップロード
        result = await client.upload_model(
            'model.step',
            {
                "scale_factor": 10.0,
                "layout_mode": "canvas"
            }
        )
        
        # SVGを保存
        with open('output.svg', 'w') as f:
            f.write(result['svg'])
        
        print(f"処理完了: {result['stats']}")
        
        # パラメータを更新
        result = await client.update_parameters({
            "scale_factor": 20.0
        })
        
        print(f"更新完了 (キャッシュ使用: {result['cached']})")
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## テストツール

### Pythonテストクライアント

プロジェクトには包括的なテストクライアントが含まれています：

```bash
# テストクライアントを実行
python test_websocket_client.py model.step

# デフォルトのテストファイルで実行
python test_websocket_client.py
```

### HTMLデモクライアント

ブラウザベースの完全なデモクライアント：

```bash
# サーバーを起動
python main.py

# ブラウザで開く
open examples/websocket_client.html
```

## パフォーマンス最適化

### キャッシュシステム

WebSocket APIは自動的に以下の最適化を行います：

1. **形状データのキャッシュ**
   - モデルのMD5ハッシュをキーとしてキャッシュ
   - TTL: 1時間（デフォルト）
   - 最大キャッシュサイズ: 100エントリ
   - LRU（Least Recently Used）方式でエビクション

2. **インクリメンタル更新**
   - パラメータ変更時は形状の再計算をスキップ
   - `update_parameters`を使用すると高速処理
   - レスポンスの`cached`フィールドで確認可能

### ベストプラクティス

1. **初回ロード時**
   ```javascript
   // モデルとパラメータを同時に送信
   client.uploadModel(file, {
       scale_factor: 10.0,
       layout_mode: 'canvas',
       max_faces: 20
   });
   ```

2. **パラメータ調整時**
   ```javascript
   // update_parametersを使用（高速）
   client.updateParameters({
       scale_factor: newValue
   });
   ```

3. **デバウンス処理**
   ```javascript
   let debounceTimer;
   
   function updateWithDebounce(params) {
       clearTimeout(debounceTimer);
       debounceTimer = setTimeout(() => {
           client.updateParameters(params);
       }, 500); // 500ms待機
   }
   ```

## エラーハンドリング

### 一般的なエラーと対処法

1. **接続エラー**
   ```javascript
   ws.onerror = (error) => {
       console.error('WebSocket エラー:', error);
       // 再接続を試みる
       setTimeout(() => reconnect(), 5000);
   };
   ```

2. **モデル処理エラー**
   ```javascript
   if (message.type === 'error') {
       switch (message.data.message) {
           case 'Failed to load STEP file':
               alert('STEPファイルの読み込みに失敗しました');
               break;
           case 'No model loaded for this client':
               // モデルの再アップロードが必要
               break;
       }
   }
   ```

3. **接続切断時の自動再接続**
   ```javascript
   ws.onclose = async (event) => {
       console.log('接続が切断されました');
       if (!event.wasClean) {
           // 異常終了の場合は再接続
           await reconnect();
       }
   };
   ```

## セキュリティ考慮事項

1. **ファイルサイズ制限**
   - 大きなファイルはチャンク分割を検討
   - サーバー側でサイズ制限を実装

2. **認証・認可**
   - 本番環境ではトークンベース認証を実装
   - WebSocketハンドシェイク時に認証

3. **Rate Limiting**
   - クライアントごとのメッセージ頻度を制限
   - DoS攻撃の防止

## トラブルシューティング

### 接続できない

```bash
# サーバーが起動しているか確認
curl http://localhost:8001/api/health

# WebSocketエンドポイントを直接テスト
python test_websocket_client.py
```

### SVGが生成されない

1. モデルファイルが正しいSTEP形式か確認
2. `max_faces`パラメータを増やす
3. `min_face_area`パラメータを小さくする
4. サーバーログでエラーを確認

### パフォーマンスが遅い

1. `update_model`の代わりに`update_parameters`を使用
2. `max_faces`を適切な値に調整
3. キャッシュが有効か確認（`cached: true`）

## 今後の拡張予定

- プログレスバーのサポート
- バイナリフレームによる高速転送
- 複数モデルの同時処理
- WebRTCによるP2P通信オプション