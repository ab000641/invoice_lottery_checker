# Dockerfile
# 使用一個輕量級的 Python 映像
FROM python:3.10-slim-buster

# 設定工作目錄
WORKDIR /app

# 永久設定 PATH，確保 uv 在容器運行時也能被找到
ENV PATH="/root/.local/bin:${PATH}" 

# 安裝 curl 和其他必要的系統套件
# 並清理 APT 快取，減少映像大小
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件 (requirements.txt)
COPY requirements.txt .

# 將 UV 安裝到容器內，並在同一個 RUN 命令中安裝 Python 依賴，使用 --system 參數
# 這裡的 export PATH 是為了確保 uv 在這個 RUN 命令執行時就被找到
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv pip install --system -r requirements.txt

# 複製應用程式程式碼
COPY . .

# 暴露 Flask 應用程式的埠
EXPOSE 5000

# 預設啟動命令 (在 docker-compose.yml 中可能會被覆蓋)
CMD ["uv", "run", "python", "app.py"]