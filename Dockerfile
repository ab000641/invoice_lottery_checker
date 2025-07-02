# 使用一個輕量級的 Python 映像
FROM python:3.10-slim-buster

# 設定工作目錄
WORKDIR /app

# 安裝 curl 和其他必要的系統套件
# 並清理 APT 快取，減少映像大小
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 複製依賴文件 (requirements.txt)
COPY requirements.txt .

# 將 uv 的安裝、PATH 設定和所有 Python 依賴的安裝合併到單一的 RUN 命令中
# 這樣可以確保 uv 及其安裝的路徑在整個安裝過程中都有效
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    export PATH="/root/.local/bin:$PATH" && \
    uv pip install --system -r requirements.txt

# 複製應用程式程式碼
COPY . .

# 暴露 Flask 應用程式的埠
EXPOSE 5000

# 預設啟動命令 (這個 CMD 會被 docker-compose.yml 中的 'command' 覆蓋)
CMD ["uv", "run", "python", "app.py"]