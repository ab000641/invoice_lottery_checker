統一發票自動對獎系統
這是一個基於 Flask 開發的應用程式，旨在幫助使用者自動檢查個人發票是否中獎。它能夠從財政部電子發票整合服務平台的網站上自動抓取最新的統一發票開獎號碼，並提供一個簡單的前端介面供使用者輸入發票資訊進行即時對獎。

功能特色

智慧對獎功能：根據發票號碼和開立日期，自動比對財政部公布的中獎號碼，判斷是否中獎並顯示最高獎項。

自動化開獎號碼抓取：透過網頁爬蟲定期從財政部電子發票平台獲取最新的開獎號碼並儲存至資料庫。

背景排程任務：使用 Flask-APScheduler 實現定時任務，自動更新開獎號碼。

資料庫儲存：使用 SQLAlchemy 將發票記錄和開獎號碼持久化儲存。

簡易前端介面：提供一個網頁介面供使用者手動輸入發票號碼和日期進行對獎。

技術棧
後端框架：Python 3, Flask

資料庫：PostgreSQL (透過 DATABASE_URL 配置)

ORM：Flask-SQLAlchemy

網頁爬蟲：Requests, BeautifulSoup4

排程任務：Flask-APScheduler

環境管理：python-dotenv

容器化：Docker, Docker Compose

前端：HTML, CSS, JavaScript (Vanilla JS)

先決條件
在運行此專案之前，請確保您的系統已安裝以下軟體：

Docker

Docker Compose

Git

安裝與設定
請依照以下步驟設定並運行您的應用程式：

clone專案儲存庫：

git clone
cd
建立 .env 環境變數檔案：
在專案的根目錄下建立一個名為 .env 的檔案，並填入您的資料庫連線字串。

程式碼片段

# .env
DATABASE_URL=postgresql://user:password@host:port/database_name
請將 user、password、host、port 和 database_name 替換為您實際的 PostgreSQL 資料庫資訊。如果您是本地開發，可以使用 Docker 啟動一個 PostgreSQL 容器。

使用 Docker Compose 啟動服務：
在終端機中，執行以下命令來建置 Docker 映像檔並啟動所有服務。--build 選項會確保您的程式碼修改被包含在映像檔中。

docker compose up --build -d
這將會啟動 Flask 應用程式和您在 docker-compose.yml 中定義的任何其他服務（例如 PostgreSQL 資料庫）。

初始化資料庫 (如果資料庫是空的)：
第一次啟動服務後，您可能需要初始化資料庫。在 app.py 中已經有 init_db() 函數，但它預設在 if __name__ == '__main__': 區塊中被註釋掉。您可以在需要時手動調用它，或者簡單地讓 SQLALCHEMY_DATABASE_URI 指向一個新的資料庫，SQLAlchemy 會自動建立表格。
重要提示：在生產環境中，通常使用資料庫遷移工具（如 Alembic）來管理資料庫結構。對於簡單的開發環境，手動建立或讓 SQLAlchemy 自動建立即可。

手動觸發首次開獎號碼抓取 (可選)：
應用程式會自動排程每 12 小時抓取一次開獎號碼，但您也可以手動觸發立即抓取：

curl -X POST http://localhost:5000/fetch_awards
使用方式
訪問網頁介面：
打開您的網頁瀏覽器，導航到 http://localhost:5000。您將看到一個簡單的發票對獎表單。

在「發票號碼」欄位輸入 8 位數字的發票號碼。

選擇發票的開立年份和月份。

點擊「對獎」按鈕即可查看對獎結果。

API 端點 (供開發者使用)：
以下是應用程式提供的一些主要 API 端點：

健康檢查：
GET /health
回傳應用程式和資料庫的狀態。

新增發票：
POST /invoices
請求範例：

{
    "invoice_number": "12345678",
    "invoice_date": "2024-01-15",
    "total_amount": 100
}
取得所有發票：
GET /invoices

取得單一發票：
GET /invoices/<invoice_id>

更新發票：
PUT /invoices/<invoice_id>
請求範例：

{
    "winning_status": true
}
刪除發票：
DELETE /invoices/<invoice_id>

對獎 (由前端呼叫)：
POST /check_invoice
請求範例：

{
    "invoice_number": "12345678",
    "invoice_date": "2024-03-25"  // 此日期應為該期發票的開獎日期 (例如 1-2 月發票的開獎日期為 3/25)
}
手動獲取開獎號碼：
POST /fetch_awards
觸發一次從財政部網站抓取最新開獎號碼的動作。

查看排程狀態：
GET /scheduler_status
查看 APScheduler 目前排程中的所有任務。

資料庫模型
Invoice (發票)
id (Integer): 主鍵

invoice_number (String): 發票號碼，唯一

invoice_date (Date): 發票日期 (非開獎日期)

winning_status (Boolean): 是否中獎，預設為 False

award_id (Integer): 關聯到 Award 模型的外鍵，表示中獎的獎項

Award (獎項)
id (Integer): 主鍵

prize_name (String): 獎項名稱 (如「特別獎」、「頭獎」等)

winning_numbers (String): 中獎號碼，多組號碼以逗號分隔

award_date (Date): 開獎日期 (例如 2024-03-25 代表 1-2 月發票的開獎日)


排程任務
應用程式內建一個排程任務 scheduled_fetch_awards，使用 Flask-APScheduler 每 12 小時自動執行一次 _execute_fetch_awards_logic 函數，以確保開獎號碼資料庫保持最新。

注意事項
錯誤處理：本應用程式包含基本的錯誤處理，但對於生產環境，建議加入更詳盡的日誌記錄（例如使用 Python 的 logging 模組）和更健壯的錯誤回報機制。

網頁結構變動：網頁爬蟲的實現依賴於財政部電子發票平台的網頁 HTML 結構。如果該網站的結構發生重大變化，_execute_fetch_awards_logic 函數中的爬蟲邏輯可能需要更新。

時區：排程器的時間可能需要根據部署環境的時區進行調整。

安全性：此專案未包含使用者認證和授權功能，若要公開部署，請務必考慮增加這些安全措施。

