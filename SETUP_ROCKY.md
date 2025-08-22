# Rocky Linux セットアップガイド

## 前提条件

- Rocky Linux 8.x または 9.x
- Podman (コンテナランタイム)
- Git
- インターネット接続

## セットアップ手順

### 1. システムの準備

```bash
# OS確認
cat /etc/rocky-release

# 必要なツールのインストール
sudo dnf update -y
sudo dnf install -y podman git curl

# Podmanバージョン確認
podman --version
```

### 2. プロジェクトの取得

```bash
# リポジトリをクローン
git clone https://github.com/soynyuu/unfold-step2svg
cd unfold-step2svg
```

### 3. コンテナイメージのビルド

```bash
# Containerfileを使用してビルド（プラットフォーム非依存）
podman build -f Containerfile -t unfold-step2svg .

# ビルドの確認
podman images | grep unfold-step2svg
```

### 4. コンテナの実行

```bash
# コンテナをバックグラウンドで起動
podman run -d \
  --name unfold-app \
  -p 8001:8001 \
  --restart unless-stopped \
  unfold-step2svg

# 起動確認
podman ps

# ログの確認
podman logs -f unfold-app
```

### 5. 動作確認

```bash
# ヘルスチェック
curl http://localhost:8001/api/health

# 期待される応答:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "opencascade_available": true,
#   "citygml_support": true,
#   "supported_formats": ["step", "stp", "citygml", "gml"]
# }
```

### 6. APIテスト

```bash
# テスト用STEPファイルがある場合
curl -X POST \
  -F "file=@sample.step" \
  http://localhost:8001/api/step/unfold \
  -o papercraft.svg

# SVGファイルの確認
ls -la papercraft.svg
```

## systemd サービス設定（オプション）

### 自動起動設定

```bash
# systemdユニットファイルの生成
podman generate systemd --name unfold-app \
  --files \
  --new \
  --restart-policy=always

# ユーザーサービスディレクトリに移動
mkdir -p ~/.config/systemd/user/
mv container-unfold-app.service ~/.config/systemd/user/

# サービスの有効化と起動
systemctl --user daemon-reload
systemctl --user enable container-unfold-app.service
systemctl --user start container-unfold-app.service

# ステータス確認
systemctl --user status container-unfold-app.service
```

## HTTPS対応設定

### 方法1: Cloudflareプロキシ（最も簡単）

Cloudflareの無料プランを使用してHTTPS化する方法です。SSL証明書の管理が不要で、最も簡単に実装できます。

#### 1. Cloudflareでの設定

1. Cloudflareにドメインを追加
2. DNSレコードを設定：
   - Type: A
   - Name: backend-diorama（またはサブドメイン）
   - IPv4 address: サーバーのIPアドレス
   - Proxy status: **Proxied（オレンジの雲）**

3. SSL/TLS設定：
   - SSL/TLS → Overview → **Flexible**を選択
   - （サーバー側はHTTPのまま、Cloudflare-ユーザー間はHTTPS）

#### 2. サーバー側のNginx設定（HTTPのみ）

```bash
# シンプルなHTTP設定
sudo tee /etc/nginx/conf.d/unfold-step2svg.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name backend-diorama.soynyuu.com;

    # Cloudflareからのリクエストのみ許可（オプション）
    # set_real_ip_from 173.245.48.0/20;
    # set_real_ip_from 103.21.244.0/22;
    # set_real_ip_from 103.22.200.0/22;
    # set_real_ip_from 103.31.4.0/22;
    # set_real_ip_from 141.101.64.0/18;
    # set_real_ip_from 108.162.192.0/18;
    # set_real_ip_from 190.93.240.0/20;
    # set_real_ip_from 188.114.96.0/20;
    # set_real_ip_from 197.234.240.0/22;
    # set_real_ip_from 198.41.128.0/17;
    # set_real_ip_from 162.158.0.0/15;
    # set_real_ip_from 104.16.0.0/13;
    # set_real_ip_from 104.24.0.0/14;
    # set_real_ip_from 172.64.0.0/13;
    # set_real_ip_from 131.0.72.0/22;
    # real_ip_header CF-Connecting-IP;

    # プロキシ設定
    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
        
        # Cloudflareのヘッダーを転送
        proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
        proxy_set_header CF-IPCountry $http_cf_ipcountry;
        proxy_set_header CF-RAY $http_cf_ray;
        proxy_set_header CF-Visitor $http_cf_visitor;
        
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
        proxy_send_timeout 300s;
        client_max_body_size 100M;
    }
    
    # APIパス専用設定
    location /api/ {
        proxy_pass http://localhost:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
        
        # CORS設定
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range" always;
        
        if ($request_method = 'OPTIONS') {
            add_header Access-Control-Allow-Origin "*";
            add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
            add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range";
            add_header Access-Control-Max-Age 1728000;
            add_header Content-Type 'text/plain; charset=utf-8';
            add_header Content-Length 0;
            return 204;
        }
    }
}
EOF

# Nginxの再起動
sudo nginx -t
sudo systemctl restart nginx
```

#### 3. Cloudflareの追加設定（推奨）

Cloudflareダッシュボードで以下を設定：

1. **SSL/TLS設定**：
   - Edge Certificates → Always Use HTTPS: **ON**
   - Edge Certificates → Automatic HTTPS Rewrites: **ON**

2. **セキュリティ設定**：
   - Security → Bot Fight Mode: **ON**
   - Security → Challenge Passage: 30分

3. **パフォーマンス設定**：
   - Speed → Optimization → Auto Minify: すべてOFF（APIレスポンス保護）
   - Caching → Caching Level: Standard

4. **ページルール**（無料プランで3つまで）：
   - `*backend-diorama.soynyuu.com/api/*`
     - Cache Level: Bypass
     - Security Level: Low

#### メリット

- SSL証明書の管理不要
- DDoS保護が自動的に有効
- 世界中のCDNでレスポンス高速化
- 設定が簡単（5分で完了）

#### 注意点

- 最大アップロードサイズ: 100MB（無料プラン）
- WebSocketは制限あり（無料プラン）
- Flexibleモードはサーバー間通信が暗号化されない

### 方法2: Nginxリバースプロキシ（Let's Encrypt）

#### Nginxのインストールと設定

```bash
# Nginxのインストール
sudo dnf install -y nginx certbot python3-certbot-nginx

# Nginx設定ファイルの作成
sudo vi /etc/nginx/conf.d/unfold-step2svg.conf
```

以下の設定を追加：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # ドメイン名に置き換え

    # Let's Encrypt認証用
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # HTTPからHTTPSへリダイレクト
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;  # ドメイン名に置き換え

    # SSL証明書（Let's Encrypt取得後に自動設定）
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL設定（セキュリティ強化）
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # セキュリティヘッダー
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # プロキシ設定
    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket対応（必要な場合）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # タイムアウト設定（大きなファイル処理用）
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
        proxy_send_timeout 300s;
        
        # ボディサイズ制限（大きなSTEPファイル用）
        client_max_body_size 100M;
    }
    
    # APIパス専用設定
    location /api/ {
        proxy_pass http://localhost:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS設定（必要な場合）
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range" always;
        
        # プリフライトリクエスト対応
        if ($request_method = 'OPTIONS') {
            add_header Access-Control-Allow-Origin "*";
            add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
            add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range";
            add_header Access-Control-Max-Age 1728000;
            add_header Content-Type 'text/plain; charset=utf-8';
            add_header Content-Length 0;
            return 204;
        }
    }
}
```

#### Let's EncryptでSSL証明書取得

```bash
# Nginx設定テスト
sudo nginx -t

# Nginxの起動と有効化
sudo systemctl start nginx
sudo systemctl enable nginx

# SSL証明書の取得
sudo certbot --nginx -d your-domain.com

# 自動更新の設定
sudo systemctl enable certbot-renew.timer
sudo systemctl start certbot-renew.timer

# 更新テスト
sudo certbot renew --dry-run
```

### 方法2: Caddyリバースプロキシ（自動HTTPS）

```bash
# Caddyのインストール
sudo dnf install -y 'dnf-command(copr)'
sudo dnf copr enable @caddy/caddy
sudo dnf install -y caddy

# Caddyfile設定
sudo vi /etc/caddy/Caddyfile
```

Caddyfile内容：

```
your-domain.com {
    reverse_proxy localhost:8001
    
    # ファイルサイズ制限
    request_body {
        max_size 100MB
    }
    
    # タイムアウト設定
    timeouts {
        read 5m
        write 5m
        idle 5m
    }
    
    # ログ設定
    log {
        output file /var/log/caddy/access.log
        format json
    }
}
```

```bash
# Caddyの起動と有効化
sudo systemctl start caddy
sudo systemctl enable caddy
```

### 方法3: Podmanで直接HTTPS（自己署名証明書）

```bash
# 自己署名証明書の生成
mkdir -p ~/certs
cd ~/certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout server.key -out server.crt \
  -subj "/C=JP/ST=Tokyo/L=Tokyo/O=MyOrg/CN=localhost"

# HTTPSプロキシコンテナの作成（nginx-proxy.conf）
cat > nginx-proxy.conf << 'EOF'
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/certs/server.crt;
    ssl_certificate_key /etc/nginx/certs/server.key;
    
    location / {
        proxy_pass http://unfold-app:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Nginxプロキシコンテナの実行
podman run -d \
  --name nginx-proxy \
  -p 443:443 \
  -v ~/certs:/etc/nginx/certs:ro \
  -v $(pwd)/nginx-proxy.conf:/etc/nginx/conf.d/default.conf:ro \
  --network container:unfold-app \
  nginx:alpine
```

## ファイアウォール設定

```bash
# HTTP/HTTPSポートを開放（firewalldを使用している場合）
sudo firewall-cmd --add-service=http --permanent
sudo firewall-cmd --add-service=https --permanent
sudo firewall-cmd --reload

# または特定ポートを開放
sudo firewall-cmd --add-port=80/tcp --permanent
sudo firewall-cmd --add-port=443/tcp --permanent
sudo firewall-cmd --add-port=8001/tcp --permanent  # 開発用
sudo firewall-cmd --reload

# 設定確認
sudo firewall-cmd --list-all
```

## SELinux設定（必要な場合）

```bash
# SELinuxが有効か確認
getenforce

# Enforcingの場合、ポートコンテキストを追加
sudo semanage port -a -t http_port_t -p tcp 8001

# または一時的に許可モードに変更（テスト用）
sudo setenforce 0
```

## トラブルシューティング

### コンテナが起動しない場合

```bash
# 詳細なエラーログを確認
podman logs unfold-app 2>&1

# インタラクティブモードで起動してデバッグ
podman run -it --rm -p 8001:8001 unfold-step2svg /bin/bash
```

### メモリ不足エラー

```bash
# リソース制限付きで実行
podman run -d \
  --name unfold-app \
  --memory="4g" \
  --cpus="2" \
  -p 8001:8001 \
  unfold-step2svg
```

### ネットワーク接続の問題

```bash
# ポートバインディングの確認
ss -tlnp | grep 8001

# コンテナのネットワーク確認
podman port unfold-app

# ホストネットワークモードで実行（最終手段）
podman run -d \
  --name unfold-app \
  --network host \
  unfold-step2svg
```

### パッケージインストールエラー

environment-docker.ymlを使用していることを確認：

```bash
# Containerfileの内容確認
cat Containerfile | grep environment-docker.yml
```

## コンテナの管理

```bash
# コンテナの停止
podman stop unfold-app

# コンテナの削除
podman rm unfold-app

# イメージの削除
podman rmi unfold-step2svg

# すべてクリーンアップ
podman system prune -a
```

## Podman-Composeの使用（オプション）

```bash
# podman-composeのインストール
sudo dnf install -y python3-pip
pip3 install --user podman-compose

# docker-compose.ymlがある場合
podman-compose up -d

# ログ確認
podman-compose logs -f
```

## パフォーマンス最適化

```bash
# CPUとメモリの使用状況確認
podman stats unfold-app

# リソース制限の調整
podman update --memory="8g" --cpus="4" unfold-app
```

## セキュリティ設定

```bash
# rootlessコンテナとして実行（推奨）
podman run -d \
  --name unfold-app \
  --user 1000:1000 \
  -p 8001:8001 \
  --read-only \
  --tmpfs /tmp \
  unfold-step2svg
```

## ログローテーション設定

```bash
# ログサイズ制限付きで実行
podman run -d \
  --name unfold-app \
  -p 8001:8001 \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  unfold-step2svg
```

## 問題が解決しない場合

1. GitHub Issuesで報告: https://github.com/soynyuu/unfold-step2svg/issues
2. デバッグファイルの確認: `core/debug_files/`
3. Podmanのバージョンアップグレード検討

---

  1. コンテナイメージの再ビルド

  cd ~/unfold-step2svg

  # 最新のコードを取得（Gitを使用している場合）
  git pull origin main

  # 既存のコンテナを停止・削除
  podman stop unfold-app
  podman rm unfold-app

  # イメージを再ビルド
  podman build -f Containerfile -t unfold-step2svg .

  # 新しいコンテナを起動
  podman run -d \
    --name unfold-app \
    -p 8001:8001 \
    --restart unless-stopped \
    unfold-step2svg

  # 起動確認
  podman ps
  podman logs -f unfold-app

  2. ホットリロード対応（開発環境）

  開発中に頻繁に変更する場合は、ボリュームマウントを使用：

  # コードをマウントして起動（変更が即座に反映）
  podman run -d \
    --name unfold-app-dev \
    -p 8001:8001 \
    -v $(pwd):/app:Z \
    --restart unless-stopped \
    unfold-step2svg

  3. 簡単な再起動スクリプト

  ~/unfold-step2svg/restart.shを作成：

  #!/bin/bash
  echo "Stopping container..."
  podman stop unfold-app
  podman rm unfold-app

  echo "Rebuilding image..."
  podman build -f Containerfile -t unfold-step2svg .

  echo "Starting new container..."
  podman run -d \
    --name unfold-app \
    -p 8001:8001 \
    --restart unless-stopped \
    unfold-step2svg

  echo "Checking status..."
  podman ps
  curl http://localhost:8001/api/health

  実行権限を付与：
  chmod +x restart.sh
  ./restart.sh

  4. 変更の確認

  # ヘルスチェック
  curl http://localhost:8001/api/health

  # ログ確認
  podman logs -f unfold-app

  # Cloudflare経由でテスト
  curl https://backend-diorama.soynyuu.com/api/health

  これで、コード変更後も簡単にデプロイできます