import os
import requests
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from dotenv import load_dotenv
from datetime import datetime
from bs4 import BeautifulSoup
from flask_apscheduler import APScheduler

# 加載 .env 檔案中的環境變數
load_dotenv()

app = Flask(__name__)
app.json.ensure_ascii = False # 確保 JSON 輸出正確顯示中文字符

# 從環境變數配置資料庫
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # 禁用事件追蹤，減少記憶體開銷

# --- Flask-APScheduler 初始化 ---
scheduler = APScheduler()
scheduler.init_app(app) 

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
    return render_template('index.html') # 提供前端 HTML 頁面

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

    invoice_number = data['invoice_number'].strip().replace('-', '') # 清理發票號碼
    try:
        check_date = datetime.strptime(data['invoice_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"message": "invoice_date 格式不正確，應為YYYY-MM-DD"}), 400
    
    if len(invoice_number) != 8 or not invoice_number.isdigit(): # 增加數字檢查
        return jsonify({"message": "發票號碼應為8位數字"}), 400

    # 2. 根據開獎日期查詢所有獎項號碼
    awards_for_date = db.session.execute(
        db.select(Award).filter_by(award_date=check_date)
    ).scalars().all()

    if not awards_for_date:
        return jsonify({"message": f"該開獎日期 ({check_date.isoformat()}) 無任何獎項資料，無法檢核"}), 404

    result_message = "很抱歉，您的發票未中獎。"
    is_winning = False
    winning_award = None
    winning_details = [] # 儲存所有中獎的詳細資訊，即使只返回最高獎項

    # 3. 比對發票號碼與中獎號碼
    # 按照獎項等級從高到低比對，確保正確判斷中獎狀態和訊息
    # 修正後的 prize_order，確保依獎金高低排序
    prize_order = {
        "特別獎": 1,
        "特獎": 2,
        "頭獎": 3,
        "二獎": 4,
        "三獎": 5,
        "四獎": 6,
        "五獎": 7,
        "六獎": 8,
        "增開六獎": 9 # 增開六獎放在最後，因為獎金最低且為額外增開
    }

    # 對獎項進行排序，確保高獎項先比對
    awards_for_date.sort(key=lambda x: prize_order.get(x.prize_name, 99))

    # 提取頭獎號碼，用於後續二獎、三獎等比對
    head_prize_numbers = [
        n.strip() for award in awards_for_date
        if award.prize_name == "頭獎"
        for n in award.winning_numbers.split(',')
    ]

    for award in awards_for_date:
        # winning_numbers_list 只用於特別獎、特獎、頭獎的完全比對 (或增開六獎的末三碼比對，如果它有自己的獨立號碼)
        # 對於二獎到六獎和增開六獎，我們將使用 head_prize_numbers
        winning_numbers_list = [n.strip() for n in award.winning_numbers.split(',')]

        # 首先處理需要完全比對的獎項 (特別獎, 特獎, 頭獎)
        if award.prize_name == "特別獎":
            for winning_num_exact in winning_numbers_list: 
                if invoice_number == winning_num_exact:
                    is_winning = True
                    winning_award = award
                    winning_details.append({"prize": award.prize_name, "message": f"恭喜您，中了 {award.prize_name}！號碼: {winning_num_exact}"})
                    break 
            if is_winning: 
                break 

        elif award.prize_name == "特獎":
            for winning_num_exact in winning_numbers_list:
                if invoice_number == winning_num_exact:
                    is_winning = True
                    winning_award = award
                    winning_details.append({"prize": award.prize_name, "message": f"恭喜您，中了 {award.prize_name}！號碼: {winning_num_exact}"})
                    break 
            if is_winning: 
                break

        elif award.prize_name == "頭獎":
            for winning_num_exact in winning_numbers_list:
                if invoice_number == winning_num_exact:
                    is_winning = True
                    winning_award = award
                    winning_details.append({"prize": award.prize_name, "message": f"恭喜您，中了 {award.prize_name}！號碼: {winning_num_exact}"})
                    break 
            if is_winning: 
                break

        # 處理二獎、三獎、四獎、五獎、六獎，以及增開六獎
        # 這些獎項都使用頭獎號碼的末幾碼進行比對
        elif award.prize_name in ["二獎", "三獎", "四獎", "五獎", "六獎", "增開六獎"]:
            for head_num_for_suffix in head_prize_numbers: 
                print(f"--- 偵錯 ---", flush=True)
                print(f"發票號碼: {invoice_number}", flush=True)
                print(f"當前頭獎號碼 (完整): {head_num_for_suffix}", flush=True)
                print(f"比對獎項: {award.prize_name}", flush=True) 

                matched_suffix = ""
                if award.prize_name == "二獎" and invoice_number[-7:] == head_num_for_suffix[-7:]:
                    is_winning = True; winning_award = award; matched_suffix = head_num_for_suffix[-7:]
                    winning_details.append({"prize": award.prize_name, "message": f"恭喜您，中了 {award.prize_name}！號碼後七碼: {matched_suffix}"}); break
                elif award.prize_name == "三獎" and invoice_number[-6:] == head_num_for_suffix[-6:]:
                    is_winning = True; winning_award = award; matched_suffix = head_num_for_suffix[-6:]
                    winning_details.append({"prize": award.prize_name, "message": f"恭喜您，中了 {award.prize_name}！號碼後六碼: {matched_suffix}"}); break
                elif award.prize_name == "四獎" and invoice_number[-5:] == head_num_for_suffix[-5:]:
                    is_winning = True; winning_award = award; matched_suffix = head_num_for_suffix[-5:]
                    winning_details.append({"prize": award.prize_name, "message": f"恭喜您，中了 {award.prize_name}！號碼後五碼: {matched_suffix}"}); break
                elif award.prize_name == "五獎" and invoice_number[-4:] == head_num_for_suffix[-4:]:
                    is_winning = True; winning_award = award; matched_suffix = head_num_for_suffix[-4:]
                    winning_details.append({"prize": award.prize_name, "message": f"恭喜您，中了 {award.prize_name}！號碼後四碼: {matched_suffix}"}); break
                elif award.prize_name == "六獎" and invoice_number[-3:] == head_num_for_suffix[-3:]:
                    is_winning = True; winning_award = award; matched_suffix = head_num_for_suffix[-3:]
                    winning_details.append({"prize": award.prize_name, "message": f"恭喜您，中了 {award.prize_name}！號碼後三碼: {matched_suffix}"}); break
                elif award.prize_name == "增開六獎" and invoice_number[-3:] == head_num_for_suffix[-3:]:
                    is_winning = True; winning_award = award; matched_suffix = head_num_for_suffix[-3:]
                    winning_details.append({"prize": award.prize_name, "message": f"恭喜您，中了 {award.prize_name}！號碼後三碼: {matched_suffix}"}); break
            if is_winning: 
                break 

    try:
        if is_winning: 
            highest_prize_detail = winning_details[0]

            return jsonify({
                "message": highest_prize_detail["message"],
                "invoice_number": invoice_number,
                "invoice_date": check_date.isoformat(),
                "winning_status": True, 
                "award_details": {
                    "prize_name": highest_prize_detail["prize"],
                    "winning_numbers": winning_award.winning_numbers 
                } if winning_award else None 
            }), 200
        else: 
            return jsonify({
                "message": result_message, 
                "invoice_number": invoice_number,
                "invoice_date": check_date.isoformat(),
                "winning_status": False, 
                "award_details": None 
            }), 200
    except Exception as e:
        print(f"對獎過程中發生錯誤: {e}", flush=True) 
        return jsonify({"message": "檢核發票失敗，發生內部錯誤", "error": str(e)}), 500
    
# --- 自動獲取開獎號碼 API (網頁爬蟲版本) ---
@app.route('/fetch_awards', methods=['POST'])
def fetch_awards():
    """
    從財政部電子發票平台（網頁）獲取最新開獎號碼並存入資料庫。
    """
    try:
        _execute_fetch_awards_logic()
        return jsonify({"message": "開獎號碼已成功獲取並更新至資料庫 (來自手動觸發)"}), 200
    except Exception as e:
        return jsonify({"message": "手動獲取開獎號碼失敗", "error": str(e)}), 500

# 將核心爬蟲和儲存邏輯抽離成一個獨立的函數
def _execute_fetch_awards_logic():
    invoice_web_url = "https://invoice.etax.nat.gov.tw/"

    print("--- 開始從財政部網頁獲取開獎數據 ---", flush=True)
    try:
        response = requests.get(invoice_web_url)
        response.encoding = 'utf-8' # 強制設定編碼為 UTF-8
        response.raise_for_status() # 如果請求失敗，拋出 HTTPError
        html_content = response.text
    except requests.exceptions.RequestException as e:
        raise Exception(f"無法從財政部網頁獲取開獎數據: {str(e)}")

    soup = BeautifulSoup(html_content, 'html.parser')

    try:
        # 尋找帶有 etw-on class 的 <a> 標籤，並從 title 屬性獲取期別
        period_element = soup.find('a', class_='etw-on')
        
        if not period_element:
            raise Exception("無法解析網頁中的開獎期別信息，未找到包含期別的<a>標籤或其class已變更")

        period_title = period_element.get('title', '')
        period_text_raw = period_title.replace('中獎號碼單', '').strip()
        
        if not period_text_raw:
            raise Exception("解析開獎期別文本失敗，title屬性內容無效")

        actual_award_date = parse_award_date_from_period(period_text_raw)
        print(f"解析到開獎日期: {actual_award_date.isoformat()}", flush=True)
        
        awards_to_save = []

        # 用於暫存頭獎號碼，以便賦予二獎到六獎和增開六獎
        current_head_prize_numbers = []
        
        # 尋找所有 class 為 'text-center' 且 headers 為 'th01' 的 <td> 標籤作為獎項名稱
        prize_name_tds = soup.find_all('td', headers='th01', class_='text-center')

        for prize_name_td in prize_name_tds:
            prize_name = prize_name_td.get_text(strip=True)
            winning_numbers = []
            
            # 獲取下一個 td 元素，它應該包含中獎號碼或說明
            numbers_td = prize_name_td.find_next_sibling('td')
            
            if numbers_td:
                # 針對 特別獎, 特獎, 頭獎 獲取實際號碼
                if prize_name in ["特別獎", "特獎", "頭獎"]:
                    num_elements = numbers_td.find_all(class_='etw-tbiggest')
                    for elem in num_elements:
                        num = elem.get_text(strip=True)
                        if num:
                            winning_numbers.append(num)
                    # 如果是頭獎，額外保存號碼供後續獎項使用
                    if prize_name == "頭獎":
                        current_head_prize_numbers = winning_numbers
                        print(f"--- 偵錯 --- 已獲取頭獎號碼: {current_head_prize_numbers}", flush=True)


                # 處理二獎、三獎、四獎、五獎、六獎，以及【增開六獎】
                # 這些獎項的中獎號碼實際上就是頭獎號碼
                # 這樣 check_invoice 函數才能根據獎項名稱（例如六獎對末三碼）進行比對
                elif prize_name in ["二獎", "三獎", "四獎", "五獎", "六獎", "增開六獎"]:
                    if current_head_prize_numbers:
                        # 將這些獎項的 winning_numbers 設置為當期所有頭獎號碼
                        winning_numbers = current_head_prize_numbers
                        print(f"--- 偵錯 --- {prize_name} 的號碼被設置為頭獎號碼: {winning_numbers}", flush=True)
                    else:
                        print(f"警告: 嘗試處理 {prize_name} 但未找到頭獎號碼，可能導致數據不完整。跳過此獎項。", flush=True)
                        continue # 如果沒有頭獎號碼，跳過當前獎項

            if winning_numbers:
                awards_to_save.append(Award(
                    prize_name=prize_name,
                    winning_numbers=",".join(winning_numbers),
                    award_date=actual_award_date
                ))
                print(f"已解析獎項: {prize_name}, 號碼: {','.join(winning_numbers)}", flush=True)
            else:
                print(f"警告: 未能為 {prize_name} 找到中獎號碼，跳過此獎項。", flush=True)


    except Exception as e:
        raise Exception(f"解析網頁內容失敗，請檢查網頁結構是否變更或聯繫開發者。錯誤: {str(e)}")

    if not awards_to_save:
        raise Exception("未能從網頁提取任何有效的開獎號碼，請檢查網頁結構或期別。")

    try:
        with db.session.begin():
            for new_award_entry in awards_to_save:
                existing_award = db.session.execute(
                    db.select(Award).filter_by(
                        award_date=new_award_entry.award_date,
                        prize_name=new_award_entry.prize_name
                    )
                ).scalar_one_or_none()

                if existing_award:
                    # 只有當號碼確實不同時才更新，避免不必要的資料庫操作
                    if existing_award.winning_numbers != new_award_entry.winning_numbers:
                        existing_award.winning_numbers = new_award_entry.winning_numbers
                        db.session.add(existing_award) # 標記為需要更新
                        print(f"更新現有獎項: {new_award_entry.prize_name} for {new_award_entry.award_date}, 號碼: {new_award_entry.winning_numbers}", flush=True)
                    else:
                        print(f"獎項已存在且號碼相同，無需更新: {new_award_entry.prize_name} for {new_award_entry.award_date}", flush=True)
                else:
                    db.session.add(new_award_entry)
                    print(f"新增獎項: {new_award_entry.prize_name} for {new_award_entry.award_date}, 號碼: {new_award_entry.winning_numbers}", flush=True)

            db.session.commit()
            print("--- 開獎號碼已成功儲存至資料庫 ---", flush=True)
    except Exception as e:
        db.session.rollback()
        raise Exception(f"儲存開獎號碼失敗: {str(e)}")


# 輔助函數：從期別字串解析開獎日期
def parse_award_date_from_period(period_str):
    """
    從統一發票期別字串 (e.g., "113年03-04月") 解析出實際開獎日期。
    開獎日期是發票月份區間中第二個月份的下一個月的 25 號。
    """
    try:
        # 移除前後空白和 '期' 字，例如 '113年03-04月'
        cleaned_period_str = period_str.strip().replace('期', '')
        
        # 分割年份和月份範圍
        parts = cleaned_period_str.split('年')
        republic_year_str = parts[0]
        month_range_str = parts[1].replace('月', '') # 例如 "03-04"

        # 將民國年轉換為西元年
        ce_year = int(republic_year_str) + 1911

        # 提取月份範圍的第二個月份
        end_month = int(month_range_str.split('-')[1])

        # 計算實際開獎月份 (通常是第二個月份的下一個月)
        # 例如 03-04月發票在 05/25 開獎
        # 01-02月發票在 03/25 開獎
        award_month = (end_month % 12) + 1 # 處理 12 月跨年到次年 1 月的情況

        # 開獎日期固定是 25 日
        award_day = 25

        # 處理跨年情況 (例如 112年11-12月發票，在 113年01月25日開獎)
        if end_month == 12:
            # 如果發票期是 11-12月，開獎月份是 1月，但年份應為下一年
            ce_year += 1 
        
        return datetime(ce_year, award_month, award_day).date()
    except Exception as e:
        print(f"解析期別 '{period_str}' 失敗: {e}", flush=True)
        # 如果解析失敗，提供一個合理的預設值或拋出錯誤
        # 這裡為了繼續流程，可以返回 None 或拋出，但在實際應用中應有更完善的錯誤處理
        raise ValueError(f"無法從期別 '{period_str}' 解析出正確的開獎日期: {e}")

# --- 檢視排程任務狀態 ---
@app.route('/scheduler_status', methods=['GET'])
def scheduler_status():
    """
    查看 APScheduler 目前排程中的所有任務。
    """
    if not scheduler.running:
        return jsonify({"status": "scheduler is not running"}), 200

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "func": job.func_ref
        })
    return jsonify({"status": "scheduler running", "jobs": jobs}), 200


# 設定排程任務
# 這裡設定為每 12 小時執行一次 fetch_awards
# 您可以根據實際需求調整 interval 或使用 cron 設定更精確的時間
@scheduler.task('interval', id='do_fetch_awards', hours=12, misfire_grace_time=900)
def scheduled_fetch_awards():
    with app.app_context(): # 確保在應用程式上下文中執行
        print("--- 排程任務啟動：自動獲取開獎號碼 ---", flush=True)
        try:
            # 調用抽離出來的核心邏輯函數
            _execute_fetch_awards_logic()
            print("--- 排程任務完成：開獎號碼已成功獲取並更新至資料庫 ---", flush=True)
        except Exception as e:
            # 任務失敗時，回滾可能存在的資料庫事務（_execute_fetch_awards_logic 內部已有處理）
            # 並打印錯誤信息
            print(f"--- 排程任務失敗：儲存開獎號碼失敗。錯誤: {str(e)} ---", flush=True)


# --- 資料庫初始化函數 ---
def init_db():
    with app.app_context():
        print("--- 正在創建或更新資料庫表結構 ---", flush=True)
        db.create_all()
        print("--- 資料庫表結構已完成 ---", flush=True)

if __name__ == '__main__':
    print("Flask 應用程式已啟動。請確保您的資料庫Schema已通過Alembic正確初始化和更新。", flush=True)
    # 如果您只是在本地測試，可以在這裡呼叫 init_db()
    # init_db() 
    app.run(host='0.0.0.0', port=5000, debug=True)