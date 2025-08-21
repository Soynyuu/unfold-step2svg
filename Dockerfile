# Miniconda3ベースイメージを使用
FROM continuumio/miniconda3:24.11.1-0

# 作業ディレクトリの設定
WORKDIR /app

# システムパッケージの更新とタイムゾーン設定
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libglu1-mesa \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/share/zoneinfo/Asia/Tokyo /etc/localtime

# Conda環境ファイルをコピー
COPY environment.yml .

# Conda環境の作成
RUN conda env create -f environment.yml && \
    conda clean -afy

# アプリケーションコードをコピー
COPY . .

# ポート8001を公開
EXPOSE 8001

# Conda環境をアクティベートしてアプリケーションを起動
SHELL ["conda", "run", "-n", "unfold-step2svg", "/bin/bash", "-c"]

# ヘルスチェック設定
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD conda run -n unfold-step2svg python -c "import requests; requests.get('http://localhost:8001/api/health')" || exit 1

# アプリケーション起動
CMD ["conda", "run", "--no-capture-output", "-n", "unfold-step2svg", "python", "main.py"]