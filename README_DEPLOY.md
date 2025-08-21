# Unfold-STEP2SVG デプロイガイド (Rocky Linux VPS)

このガイドではRocky Linux VPS環境へのPodmanを使用したデプロイ手順を説明します。

## 目次
- [システム要件](#システム要件)
- [クイックスタート](#クイックスタート)
- [詳細セットアップ](#詳細セットアップ)
- [SSL証明書設定](#ssl証明書設定)
- [メンテナンス](#メンテナンス)
- [トラブルシューティング](#トラブルシューティング)

## システム要件

### 最小要件
- **OS**: Rocky Linux 8.x または 9.x
- **CPU**: 2コア以上
- **メモリ**: 4GB以上（OpenCASCADE処理用）
- **ストレージ**: 10GB以上の空き容量
- **ネットワーク**: ポート80, 443（HTTPS用）

### 推奨要件
- **CPU**: 4コア以上
- **メモリ**: 8GB以上
- **ストレージ**: 20GB以上（デバッグファイル保存用）

## クイックスタート

```bash
# 1. リポジトリのクローン
git clone https://github.com/Soynyuu/unfold-step2svg.git
cd unfold-step2svg

# 2. Podmanのインストール
sudo dnf install -y podman podman-compose

# 3. デプロイスクリプトの実行
./podman-deploy.sh build-run

# 4. ヘルスチェック
curl http://localhost:8001/api/health
```

## 詳細セットアップ

### 1. システムの準備

```bash
# システムアップデート
sudo dnf update -y

# 必要なパッケージのインストール
sudo dnf install -y \
    podman \
    podman-compose \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    firewalld

# Firewall設定
sudo systemctl start firewalld
sudo systemctl enable firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 2. アプリケーションのセットアップ

```bash
# ユーザーの作成（推奨）
sudo useradd -m -s /bin/bash unfold
sudo usermod -aG wheel unfold

# ユーザーに切り替え
sudo su - unfold

# リポジトリのクローン
git clone https://github.com/Soynyuu/unfold-step2svg.git
cd unfold-step2svg

# デバッグファイル用ディレクトリの作成
mkdir -p core/debug_files
```

### 3. Podmanコンテナのビルドと起動

#### 方法1: デプロイスクリプト使用（推奨）

```bash
# 実行権限の付与
chmod +x podman-deploy.sh

# ビルドと起動
./podman-deploy.sh build-run

# ステータス確認
./podman-deploy.sh status
```

#### 方法2: 手動実行

```bash
# イメージのビルド
podman build -t unfold-step2svg:latest .

# コンテナの起動
podman run -d \
    --name unfold-step2svg \
    --restart always \
    -p 8001:8001 \
    -v ./core/debug_files:/app/core/debug_files:Z \
    unfold-step2svg:latest

# ログの確認
podman logs -f unfold-step2svg
```

### 4. Systemdサービスの設定

#### Rootlessサービス（推奨）

```bash
# ユーザーのlinger有効化（ログアウト後も実行継続）
loginctl enable-linger unfold

# systemdディレクトリの作成
mkdir -p ~/.config/systemd/user

# サービスファイルの生成
podman generate systemd \
    --name unfold-step2svg \
    --files \
    --new \
    > ~/.config/systemd/user/unfold-step2svg.service

# サービスの有効化と起動
systemctl --user daemon-reload
systemctl --user enable unfold-step2svg.service
systemctl --user start unfold-step2svg.service

# ステータス確認
systemctl --user status unfold-step2svg.service
```

#### システムサービス（root権限）

```bash
# サービスファイルのコピー
sudo cp unfold-step2svg.service /etc/systemd/system/

# サービスの有効化と起動
sudo systemctl daemon-reload
sudo systemctl enable unfold-step2svg.service
sudo systemctl start unfold-step2svg.service
```

### 5. Nginxリバースプロキシの設定

```bash
# Nginx設定ファイルのコピー
sudo cp nginx/unfold-step2svg.conf /etc/nginx/conf.d/

# ドメイン名の設定
sudo sed -i 's/your-domain.com/YOUR_ACTUAL_DOMAIN/g' /etc/nginx/conf.d/unfold-step2svg.conf

# 設定の検証
sudo nginx -t

# Nginxの起動
sudo systemctl enable nginx
sudo systemctl restart nginx
```

## SSL証明書設定

### Let's Encryptを使用したSSL設定

```bash
# 証明書の取得
sudo certbot --nginx -d your-domain.com

# 自動更新の設定
sudo systemctl enable certbot-renew.timer
sudo systemctl start certbot-renew.timer

# 自動更新のテスト
sudo certbot renew --dry-run
```

## メンテナンス

### ログの確認

```bash
# アプリケーションログ
podman logs -f unfold-step2svg

# Nginxログ
sudo tail -f /var/log/nginx/unfold-step2svg.access.log
sudo tail -f /var/log/nginx/unfold-step2svg.error.log
```

### アップデート手順

```bash
# コードの更新
cd ~/unfold-step2svg
git pull origin main

# 再ビルドと再起動
./podman-deploy.sh build-run

# または手動で
podman stop unfold-step2svg
podman rm unfold-step2svg
podman build --no-cache -t unfold-step2svg:latest .
podman run -d --name unfold-step2svg --restart always -p 8001:8001 unfold-step2svg:latest
```

### バックアップ

```bash
# デバッグファイルのバックアップ
tar -czf debug_files_backup_$(date +%Y%m%d).tar.gz core/debug_files/

# コンテナイメージのエクスポート
podman save unfold-step2svg:latest | gzip > unfold-step2svg_image_$(date +%Y%m%d).tar.gz
```

## トラブルシューティング

### コンテナが起動しない

```bash
# 詳細ログの確認
podman logs unfold-step2svg

# イメージの再ビルド（キャッシュクリア）
podman rmi unfold-step2svg:latest
./podman-deploy.sh build
```

### メモリ不足エラー

```bash
# メモリ使用状況の確認
free -h
podman stats unfold-step2svg

# スワップの追加（必要に応じて）
sudo dd if=/dev/zero of=/swapfile bs=1G count=4
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### ポート競合

```bash
# ポート使用状況の確認
sudo ss -tlnp | grep 8001

# 別ポートでの起動
PORT=8002 ./podman-deploy.sh run
```

### Conda環境の問題

```bash
# コンテナ内でのデバッグ
podman exec -it unfold-step2svg /bin/bash
conda activate unfold-step2svg
python -c "import OCC; print(OCC.__version__)"
```

### SELinuxの問題（Rocky Linux特有）

```bash
# SELinuxステータス確認
getenforce

# 一時的に無効化（テスト用）
sudo setenforce 0

# ボリュームマウントのラベル付け
podman run -v ./core/debug_files:/app/core/debug_files:Z ...
```

## パフォーマンスチューニング

### Podman設定

```bash
# ユーザーnamespace設定
echo "unfold:100000:65536" | sudo tee /etc/subuid
echo "unfold:100000:65536" | sudo tee /etc/subgid

# リソース制限の設定（必要に応じて）
podman run --memory="4g" --cpus="2" ...
```

### Nginx最適化

```nginx
# /etc/nginx/nginx.conf
worker_processes auto;
worker_connections 1024;
keepalive_timeout 65;
keepalive_requests 100;
```

## セキュリティ推奨事項

1. **定期的なアップデート**
   ```bash
   sudo dnf update -y
   podman pull continuumio/miniconda3:latest
   ```

2. **ファイアウォール設定**
   - 必要なポートのみ開放
   - IP制限の検討

3. **Rootlessコンテナの使用**
   - 非root権限での実行を推奨

4. **監視の設定**
   - Prometheus + Grafanaでの監視
   - ログの定期的な確認

## サポート

問題が発生した場合：
1. [GitHub Issues](https://github.com/Soynyuu/unfold-step2svg/issues)で報告
2. デバッグログを添付（`core/debug_files/`）
3. システム情報の提供（Rocky Linuxバージョン、Podmanバージョン等）