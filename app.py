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
    invoice_date = Column(Date, nullable=False) # 開獎日期 (購買發票的日期)
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
    prize_name = Column(String(50), nullable=False) # 獎項名稱 (特別獎, 特獎, 頭獎等)
    winning_numbers = Column(String(255), nullable=False) # 中獎號碼 (可能有多組，用逗號分隔)
    # award_date 不再是 unique，允許相同開獎日期有多個獎項 (如特別獎、特獎)
    award_date = Column(Date, nullable=False) # 開獎日期 (例如 2024-03-25 for 1-2月發票)

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
    """
    健康檢查路由，檢查資料庫連線狀態。
    """
    try:
        # 嘗試執行一個簡單的資料庫查詢來驗證連線
        db.session.execute(db.select(1))
        return jsonify({"status": "ok", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "error", "database": "disconnected", "details": str(e)}), 500

# --- 發票 (Invoice) 相關 API ---

@app.route('/invoices', methods=['POST'])
def add_invoice():
    """
    新增一張發票。
    請求範例:
    {
        "invoice_number": "12345678",
        "invoice_date": "2024-01-15",
        "total_amount": 100
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"message": "請求數據無效，請提供JSON格式數據"}), 400

    required_fields = ['invoice_number', 'invoice_date', 'total_amount']
    for field in required_fields:
        if field not in data:
            return jsonify({"message": f"缺少必要欄位: {field}"}), 400

    try:
        invoice_date = datetime.strptime(data['invoice_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"message": "invoice_date 格式不正確，應為YYYY-MM-DD"}), 400

    new_invoice = Invoice(
        invoice_number=data['invoice_number'],
        invoice_date=invoice_date,
        total_amount=data['total_amount'],
        winning_status=False # 新增發票時預設為未中獎
    )

    try:
        db.session.add(new_invoice)
        db.session.commit()

        return jsonify({
            "message": "發票新增成功",
            "invoice": {
                "id": new_invoice.id,
                "invoice_number": new_invoice.invoice_number,
                "invoice_date": new_invoice.invoice_date.isoformat(),
                "total_amount": new_invoice.total_amount,
                "winning_status": new_invoice.winning_status
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        # 處理唯一約束錯誤 (例如發票號碼重複)
        if "duplicate key value violates unique constraint" in str(e).lower():
             return jsonify({"message": "新增發票失敗：發票號碼已存在", "error": str(e)}), 409 # 409 Conflict
        return jsonify({"message": "新增發票失敗", "error": str(e)}), 500

@app.route('/invoices', methods=['GET'])
def get_all_invoices():
    """
    取得所有發票列表。
    """
    # 依發票日期降序排列，再依 ID 降序排列，通常最新發票會比較重要
    invoices = db.session.execute(db.select(Invoice).order_by(Invoice.invoice_date.desc(), Invoice.id.desc())).scalars().all()
    output = []
    for invoice in invoices:
        invoice_data = {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.isoformat(),
            "total_amount": invoice.total_amount,
            "winning_status": invoice.winning_status,
            "award_id": invoice.award_id # 即使為 None 也會顯示
        }
        output.append(invoice_data)
    return jsonify({"invoices": output}), 200

@app.route('/invoices/<int:invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    """
    根據 ID 取得單一發票資訊。
    """
    # 使用 .get_or_404() 如果找不到會自動返回 404
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        return jsonify({"message": f"找不到 ID 為 {invoice_id} 的發票"}), 404

    invoice_data = {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat(),
        "total_amount": invoice.total_amount,
        "winning_status": invoice.winning_status,
        "award_id": invoice.award_id
    }
    return jsonify({"invoice": invoice_data}), 200

@app.route('/invoices/<int:invoice_id>', methods=['PUT'])
def update_invoice(invoice_id):
    """
    更新一張發票的資訊。
    """
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        return jsonify({"message": f"找不到 ID 為 {invoice_id} 的發票"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"message": "請求數據無效，請提供JSON格式數據"}), 400

    try:
        # 允許部分更新，只更新提供的欄位
        if 'invoice_number' in data:
            invoice.invoice_number = data['invoice_number']
        if 'invoice_date' in data:
            invoice.invoice_date = datetime.strptime(data['invoice_date'], '%Y-%m-%d').date()
        if 'total_amount' in data:
            invoice.total_amount = data['total_amount']
        if 'winning_status' in data:
            invoice.winning_status = data['winning_status']
        if 'award_id' in data:
            invoice.award_id = data['award_id']

        db.session.commit()
        return jsonify({"message": f"ID 為 {invoice_id} 的發票更新成功"}), 200
    except Exception as e:
        db.session.rollback()
        if "duplicate key value violates unique constraint" in str(e).lower():
             return jsonify({"message": "更新發票失敗：發票號碼已存在", "error": str(e)}), 409
        return jsonify({"message": "更新發票失敗", "error": str(e)}), 500

@app.route('/invoices/<int:invoice_id>', methods=['DELETE'])
def delete_invoice(invoice_id):
    """
    刪除一張發票。
    """
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        return jsonify({"message": f"找不到 ID 為 {invoice_id} 的發票"}), 404

    try:
        db.session.delete(invoice)
        db.session.commit()
        return jsonify({"message": f"ID 為 {invoice_id} 的發票刪除成功"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "刪除發票失敗", "error": str(e)}), 500

# --- 獎項 (Award) 相關 API ---

@app.route('/awards', methods=['POST'])
def add_award():
    """
    新增一個獎項。
    請求範例:
    {
        "prize_name": "特別獎",
        "winning_numbers": "12345678",
        "award_date": "2024-03-25"
    }
    或者：
    {
        "prize_name": "頭獎",
        "winning_numbers": "87654321,11112222",
        "award_date": "2024-03-25"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"message": "請求數據無效，請提供JSON格式數據"}), 400

    required_fields = ['prize_name', 'winning_numbers', 'award_date']
    for field in required_fields:
        if field not in data:
            return jsonify({"message": f"缺少必要欄位: {field}"}), 400

    try:
        award_date = datetime.strptime(data['award_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"message": "award_date 格式不正確，應為YYYY-MM-DD"}), 400

    # 由於 award_date 不再是 unique，這裡不需要檢查相同開獎日期的獎項重複問題。
    # 而是應該允許同一開獎日期有多個獎項 (例如特獎、頭獎等)

    new_award = Award(
        prize_name=data['prize_name'],
        winning_numbers=data['winning_numbers'],
        award_date=award_date
    )

    try:
        db.session.add(new_award)
        db.session.commit()
        return jsonify({
            "message": "獎項新增成功",
            "award": {
                "id": new_award.id,
                "prize_name": new_award.prize_name,
                "winning_numbers": new_award.winning_numbers,
                "award_date": new_award.award_date.isoformat()
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "新增獎項失敗", "error": str(e)}), 500

@app.route('/awards', methods=['GET'])
def get_all_awards():
    """
    取得所有獎項列表，通常按開獎日期降序排列。
    """
    # 建議按日期降序排列，然後按 ID 降序排列，確保同一開獎日期有多個獎項時也有穩定排序
    awards = db.session.execute(db.select(Award).order_by(Award.award_date.desc(), Award.id.desc())).scalars().all()
    output = []
    for award in awards:
        award_data = {
            "id": award.id,
            "prize_name": award.prize_name,
            "winning_numbers": award.winning_numbers,
            "award_date": award.award_date.isoformat()
        }
        output.append(award_data)
    return jsonify({"awards": output}), 200

@app.route('/awards/<int:award_id>', methods=['GET'])
def get_award(award_id):
    """
    根據 ID 取得單一獎項資訊。
    """
    award = db.session.get(Award, award_id)
    if not award:
        return jsonify({"message": f"找不到 ID 為 {award_id} 的獎項"}), 404

    award_data = {
        "id": award.id,
        "prize_name": award.prize_name,
        "winning_numbers": award.winning_numbers,
        "award_date": award.award_date.isoformat()
    }
    return jsonify({"award": award_data}), 200

@app.route('/awards/<int:award_id>', methods=['PUT'])
def update_award(award_id):
    """
    更新一個獎項的資訊。
    """
    award = db.session.get(Award, award_id)
    if not award:
        return jsonify({"message": f"找不到 ID 為 {award_id} 的獎項"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"message": "請求數據無效，請提供JSON格式數據"}), 400

    try:
        if 'prize_name' in data:
            award.prize_name = data['prize_name']
        if 'winning_numbers' in data:
            award.winning_numbers = data['winning_numbers']
        if 'award_date' in data:
            # 由於 award_date 不再是 unique，這裡不需要檢查日期重複
            award.award_date = datetime.strptime(data['award_date'], '%Y-%m-%d').date()

        db.session.commit()
        return jsonify({"message": f"ID 為 {award_id} 的獎項更新成功"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "更新獎項失敗", "error": str(e)}), 500

@app.route('/awards/<int:award_id>', methods=['DELETE'])
def delete_award(award_id):
    """
    刪除一個獎項。
    刪除前會將所有關聯到此獎項的發票的 award_id 設為 NULL，並重置其中獎狀態。
    """
    award = db.session.get(Award, award_id)
    if not award:
        return jsonify({"message": f"找不到 ID 為 {award_id} 的獎項"}), 404

    # 處理關聯的發票：將關聯的發票 award_id 設為 NULL，中獎狀態設為 False
    associated_invoices = db.session.execute(db.select(Invoice).filter_by(award_id=award_id)).scalars().all()
    for invoice in associated_invoices:
        invoice.award_id = None
        invoice.winning_status = False

    try:
        db.session.delete(award)
        db.session.commit()
        return jsonify({"message": f"ID 為 {award_id} 的獎項刪除成功"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "刪除獎項失敗", "error": str(e)}), 500

# --- 發票檢核 API ---

@app.route('/check_invoice', methods=['POST'])
def check_invoice():
    """
    檢核發票是否中獎。
    請求範例:
    {
        "invoice_number": "12345678",
        "invoice_date": "2024-03-25" // 此日期應為該期發票的開獎日期
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"message": "請求數據無效，請提供JSON格式數據"}), 400

    required_fields = ['invoice_number', 'invoice_date']
    for field in required_fields:
        if field not in data:
            return jsonify({"message": f"缺少必要欄位: {field}"}), 400

    invoice_number = data['invoice_number']
    try:
        check_date = datetime.strptime(data['invoice_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"message": "invoice_date 格式不正確，應為YYYY-MM-DD"}), 400

    # 1. 查找資料庫中是否存在該發票號碼
    invoice = db.session.execute(db.select(Invoice).filter_by(invoice_number=invoice_number)).scalar_one_or_none()

    if not invoice:
        return jsonify({"message": f"發票號碼 '{invoice_number}' 不存在，請先新增發票"}), 404

    # 2. 根據開獎日期查詢所有獎項號碼
    # 注意：這裡假設一個開獎日期對應多個獎項 (特別獎、特獎、頭獎、增開六獎等)
    awards_for_date = db.session.execute(
        db.select(Award).filter_by(award_date=check_date)
    ).scalars().all()

    if not awards_for_date:
        return jsonify({"message": f"該開獎日期 ({check_date.isoformat()}) 無任何獎項資料，無法檢核"}), 404

    result_message = "很抱歉，您的發票未中獎。"
    is_winning = False
    winning_award = None

    # 3. 比對發票號碼與中獎號碼
    # 按照獎項等級從高到低比對，確保正確判斷中獎狀態和訊息
    # 台灣發票的獎項等級排序 (數值越小，獎項越大)
    prize_order = {
        "特別獎": 1,
        "特獎": 2,
        "頭獎": 3,
        "增開六獎": 4, # 增開六獎通常是獨立的，且與頭獎後三碼不同概念
        "二獎": 5, # 二獎是頭獎號碼後七碼
        "三獎": 6, # 三獎是頭獎號碼後六碼
        "四獎": 7, # 四獎是頭獎號碼後五碼
        "五獎": 8, # 五獎是頭獎號碼後四碼
        "六獎": 9  # 六獎是頭獎號碼後三碼
    }

    # 對獎項進行排序，確保高獎項先比對
    # 如果 prize_name 不在 prize_order 中，將其排在最後
    awards_for_date.sort(key=lambda x: prize_order.get(x.prize_name, 99))

    # 提取頭獎號碼，用於後續二獎、三獎等比對
    head_prize_numbers = [
        n.strip() for award in awards_for_date
        if award.prize_name == "頭獎"
        for n in award.winning_numbers.split(',')
    ]

    for award in awards_for_date:
        winning_numbers_list = [n.strip() for n in award.winning_numbers.split(',')]

        for num in winning_numbers_list:
            if award.prize_name == "特別獎":
                if invoice_number == num:
                    is_winning = True
                    winning_award = award
                    result_message = f"恭喜您，中了 {award.prize_name}！號碼: {num}"
                    break
            elif award.prize_name == "特獎":
                if invoice_number == num:
                    is_winning = True
                    winning_award = award
                    result_message = f"恭喜您，中了 {award.prize_name}！號碼: {num}"
                    break
            elif award.prize_name == "頭獎":
                if invoice_number[-8:] == num:
                    is_winning = True
                    winning_award = award
                    result_message = f"恭喜您，中了 {award.prize_name}！號碼後八碼: {num}"
                    break
            elif award.prize_name == "增開六獎":
                if invoice_number[-3:] == num:
                    is_winning = True
                    winning_award = award
                    result_message = f"恭喜您，中了 {award.prize_name}！號碼後三碼: {num}"
                    break
            # 處理二獎、三獎、四獎、五獎、六獎 (這些獎項是基於頭獎號碼後幾碼)
            # 需要檢查發票號碼的後N碼是否與任一頭獎號碼的後N碼相同
            elif award.prize_name in ["二獎", "三獎", "四獎", "五獎", "六獎"]:
                # 這裡 num 是指該獎項本身的「對獎號碼」（通常就是頭獎號碼），不是單獨的中獎號碼
                # 所以應該比對發票號碼的後N碼是否與『任一頭獎號碼』的後N碼相同
                for head_num in head_prize_numbers:
                    if award.prize_name == "二獎" and len(head_num) >= 7 and invoice_number[-7:] == head_num[-7:]:
                        is_winning = True
                        winning_award = award
                        result_message = f"恭喜您，中了 {award.prize_name}！號碼後七碼: {head_num[-7:]}"
                        break
                    elif award.prize_name == "三獎" and len(head_num) >= 6 and invoice_number[-6:] == head_num[-6:]:
                        is_winning = True
                        winning_award = award
                        result_message = f"恭喜您，中了 {award.prize_name}！號碼後六碼: {head_num[-6:]}"
                        break
                    elif award.prize_name == "四獎" and len(head_num) >= 5 and invoice_number[-5:] == head_num[-5:]:
                        is_winning = True
                        winning_award = award
                        result_message = f"恭喜您，中了 {award.prize_name}！號碼後五碼: {head_num[-5:]}"
                        break
                    elif award.prize_name == "五獎" and len(head_num) >= 4 and invoice_number[-4:] == head_num[-4:]:
                        is_winning = True
                        winning_award = award
                        result_message = f"恭喜您，中了 {award.prize_name}！號碼後四碼: {head_num[-4:]}"
                        break
                    elif award.prize_name == "六獎" and len(head_num) >= 3 and invoice_number[-3:] == head_num[-3:]:
                        is_winning = True
                        winning_award = award
                        result_message = f"恭喜您，中了 {award.prize_name}！號碼後三碼: {head_num[-3:]}"
                        break
                if is_winning: # 如果這個獎項已經中獎，就不用再比對其他號碼
                    break
        if is_winning: # 如果已經中獎，就不用再比對其他獎項了
            break

    # 4. 更新發票的中獎狀態
    if is_winning:
        invoice.winning_status = True
        # 確保 winning_award 存在才設定 award_id
        invoice.award_id = winning_award.id if winning_award else None
    else:
        invoice.winning_status = False
        invoice.award_id = None # 如果之前有中獎，現在沒中，則重置

    try:
        db.session.commit()
        return jsonify({
            "message": result_message,
            "invoice_number": invoice_number,
            "invoice_date": check_date.isoformat(),
            "winning_status": invoice.winning_status,
            "award_details": {
                "id": winning_award.id,
                "prize_name": winning_award.prize_name,
                "winning_numbers": winning_award.winning_numbers
            } if winning_award else None
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "檢核發票失敗，更新資料庫錯誤", "error": str(e)}), 500

if __name__ == '__main__':
    # 在生產環境中，資料庫表的創建和更新應由 Alembic 這樣的遷移工具處理。
    # 這裡不再調用 db.create_all()，避免與 Alembic 衝突或造成混淆。
    # 如果您是在開發環境，且尚未設置 Alembic，需要手動或透過腳本創建數據庫和表。
    print("Flask 應用程式已啟動。請確保您的資料庫Schema已通過Alembic正確初始化和更新。")
    app.run(host='0.0.0.0', port=5000, debug=True)