# 統一發票自動對獎系統

---

## 簡介

---

您是否曾為手動對獎統一發票感到繁瑣？

「統一發票自動對獎系統」是一個基於 Flask 開發的應用程式，旨在簡化您的發票對獎流程。它能夠自動從財政部電子發票平台抓取最新的開獎號碼，並提供一個直觀的網頁介面，讓您輕鬆輸入發票資訊進行即時對獎。

<div align="center">
  輕鬆管理發票，智慧對獎，讓中獎不再錯過！<br><br>
  <img src="demo_image.png" alt="Demo 圖片" width="600"/><br>
  </div>

## 功能介紹

---

- **智慧對獎功能**
  根據您輸入的發票號碼和開立日期，自動比對財政部公布的中獎號碼，判斷是否中獎並顯示您所中的最高獎項。

- **自動化開獎號碼抓取**
  內建網頁爬蟲，定期從財政部電子發票整合服務平台的網站上自動獲取最新的統一發票開獎號碼，並儲存至資料庫。

- **背景排程任務**
  利用 Flask-APScheduler 實現定時任務，確保開獎號碼資料庫始終保持最新狀態，無需手動更新。

- **資料庫儲存**
  使用 SQLAlchemy 將您的發票記錄和所有歷史開獎號碼持久化儲存，方便查詢和管理。

- **簡易前端介面**
  提供一個使用者友善的網頁介面，讓您可以快速輸入發票號碼和日期進行對獎。

## 使用技術

---

- **後端框架**：Python 3, Flask
- **資料庫**：PostgreSQL
- **ORM**：Flask-SQLAlchemy
- **網頁爬蟲**：Requests, BeautifulSoup4
- **排程任務**：Flask-APScheduler
- **環境管理**：python-dotenv
- **容器化**：Docker, Docker Compose
- **前端**：HTML, CSS, JavaScript (Vanilla JS)

## 版本及套件

---

- `Python` 版本：3.9 以上
- `PostgreSQL` 版本：16.x (或 `16-alpine` 兼容版本)

## Setup

---

請依照以下步驟設定並運行您的應用程式：

1.  **克隆專案儲存庫**：
    ```bash
    # 克隆專案到您的本地機器
    git clone [https://github.com/ab000641/invoice_lottery_checker.git](https://github.com/ab000641/invoice_lottery_checker.git)

    # 進入專案資料夾
    cd invoice_lottery_checker
    ```

2.  **建立 `.env` 環境變數檔案**：
    在專案的根目錄下建立一個名為 `.env` 的檔案，並填入資料庫連線所需的環境變數。這些變數將被 `docker-compose.yml` 和 `app.py` 使用。
    ```env
    # .env 檔案內容範例
    DB_NAME=mydatabase
    DB_USER=myuser
    DB_PASSWORD=mypassword
    # DATABASE_URL 會由 docker-compose.yml 自動組裝
    ```
    * 請將 `mydatabase`、`myuser` 和 `mypassword` 替換為您希望設定的資料庫名稱、使用者名稱和密碼。這些值將用於 Docker Compose 啟動的 PostgreSQL 容器。

3.  **使用 Docker Compose 啟動服務**：
    在終端機中，執行以下命令來建置 Docker 映像檔並啟動所有服務。`--build` 選項會確保您的程式碼修改被包含在映像檔中。
    ```bash
    docker compose up --build -d
    ```
    這將會啟動 Flask 應用程式、PostgreSQL 資料庫和排程器服務。

4.  **初始化資料庫 (如果資料庫是空的)**：
    您的 `docker-compose.yml` 已經設定在 `web` 服務啟動時自動執行 `init_db()` 函數，這會在資料庫是空的時自動創建表格。因此，通常您無需手動執行額外的資料庫初始化步驟。
    **重要提示**：在生產環境中，通常建議使用資料庫遷移工具（如 Alembic）來管理資料庫結構的變更。

5.  **手動觸發首次開獎號碼抓取 (可選)**：
    應用程式會自動排程每 12 小時抓取一次開獎號碼，但您也可以手動觸發立即抓取：
    ```bash
    curl -X POST http://localhost:5000/fetch_awards
    ```