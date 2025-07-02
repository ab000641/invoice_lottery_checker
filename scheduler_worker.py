# scheduler_worker.py
import time
from app import app, scheduler # 從 app.py 導入 app 和 scheduler 實例

print("--- scheduler_worker.py: 準備啟動 APScheduler ---", flush=True)

with app.app_context(): # 確保在 Flask 應用程式上下文中啟動排程器
    if not scheduler.running:
        try:
            scheduler.start()
            print("--- scheduler_worker.py: APScheduler 已成功啟動 ---", flush=True)
        except Exception as e:
            print(f"--- scheduler_worker.py: APScheduler 啟動失敗: {e} ---", flush=True)

try:
    while True:
        time.sleep(1)
except (KeyboardInterrupt, SystemExit):
    if scheduler.running:
        scheduler.shutdown()
        print("--- scheduler_worker.py: APScheduler 已停止 ---", flush=True)
    print("--- scheduler_worker.py: 腳本終止 ---", flush=True)