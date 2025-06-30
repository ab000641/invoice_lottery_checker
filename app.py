import os
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from dotenv import load_dotenv
from datetime import datetime

# 加載 .env 檔案中的環境變數
load_dotenv()

app = Flask(__name__)

# 從環境變數配置資料庫
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # 禁用事件追蹤，減少記憶體開銷

db = SQLAlchemy(app)

# --- 資料庫模型定義 ---

class Invoice(db.Model):
    __tablename__ = 'invoices' # 資料表名稱
    id = Column(Integer, primary_key=True)
    invoice_number = Column(String(10), unique=True, nullable=False) # 發票號碼
    invoice_date = Column(Date, nullable=False) # 開獎日期
    total_amount = Column(Integer, nullable=False) # 總金額
    winning_status = Column(Boolean, default=False) # 是否中獎

    # 關聯到 Award 模型
    award_id = Column(Integer, ForeignKey('awards.id'), nullable=True) # 關聯的獎項ID
    award = relationship("Award", back_populates="invoices")

    def __repr__(self):
        return f"<Invoice {self.invoice_number} on {self.invoice_date}>"

class Award(db.Model):
    __tablename__ = 'awards' # 資料表名稱
    id = Column(Integer, primary_key=True)
    prize_name = Column(String(50), nullable=False) # 獎項名稱 (特獎, 頭獎等)
    winning_numbers = Column(String(255), nullable=False) # 中獎號碼 (可能有多組)
    award_date = Column(Date, nullable=False, unique=True) # 開獎日期

    # 關聯到 Invoice 模型
    invoices = relationship("Invoice", back_populates="award")

    def __repr__(self):
        return f"<Award {self.prize_name} for {self.award_date}>"

class User(db.Model):
    __tablename__ = 'users' # 資料表名稱
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(120), nullable=False) # 存放密碼的哈希值
    email = Column(String(120), unique=True, nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"

# --- 應用程式路由 ---

@app.route('/')
def index():
    return "統一發票兌獎網站後端服務已啟動！"

@app.route('/health')
def health_check():
    # 檢查資料庫連接
    try:
        db.session.execute(db.select(1))
        return jsonify({"status": "ok", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "error", "database": "disconnected", "details": str(e)}), 500
    
@app.route('/invoices', methods=['POST'])
def add_invoice():
    data = request.get_json() # 獲取 JSON 格式的請求數據

    if not data:
        return jsonify({"message": "請求數據無效"}), 400

    # 檢查必要欄位
    required_fields = ['invoice_number', 'invoice_date', 'total_amount']
    for field in required_fields:
        if field not in data:
            return jsonify({"message": f"缺少必要欄位: {field}"}), 400

    # 轉換日期字串為 date 物件
    try:
        invoice_date = datetime.strptime(data['invoice_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"message": "invoice_date 格式不正確，應為 YYYY-MM-DD"}), 400

    # 創建新的 Invoice 物件
    new_invoice = Invoice(
        invoice_number=data['invoice_number'],
        invoice_date=invoice_date,
        total_amount=data['total_amount'],
        # winning_status 預設為 False，award_id 預設為 None
    )

    try:
        db.session.add(new_invoice)
        db.session.commit() # 提交到資料庫

        return jsonify({
            "message": "發票新增成功",
            "invoice": {
                "id": new_invoice.id,
                "invoice_number": new_invoice.invoice_number,
                "invoice_date": new_invoice.invoice_date.isoformat(), # 將 date 物件轉為 ISO 格式字串
                "total_amount": new_invoice.total_amount,
                "winning_status": new_invoice.winning_status
            }
        }), 201 # 201 Created 狀態碼
    except Exception as e:
        db.session.rollback() # 出錯時回滾事務
        return jsonify({"message": "新增發票失敗", "error": str(e)}), 500

@app.route('/invoices', methods=['GET'])
def get_all_invoices():
    invoices = Invoice.query.all()
    output = []
    for invoice in invoices:
        invoice_data = {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.isoformat(),
            "total_amount": invoice.total_amount,
            "winning_status": invoice.winning_status,
            "award_id": invoice.award_id
        }
        output.append(invoice_data)
    return jsonify({"invoices": output})

# 只有在直接運行此檔案時才執行
if __name__ == '__main__':
    with app.app_context():
        # 首次運行時，如果資料庫不存在，則根據模型創建所有資料表
        # 注意：這只會創建表，不會處理表的修改或數據遷移。
        # 在生產環境中，應使用 Alembic 等資料庫遷移工具。
        print("資料庫已初始化 (如果資料表不存在則會創建)。")
    app.run(host='0.0.0.0', port=5000)