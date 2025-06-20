from flask import Flask, request, jsonify
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from amazon_paapi import AmazonApi

app = Flask(__name__)

# === Amazon API 認証情報 ===
ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")
LOCALE = "JP"

# Amazon API を明示的に初期化
# Amazon API を明示的に初期化（修正済み）
amazon = AmazonApi(
    key=ACCESS_KEY,
    secret=SECRET_KEY,
    tag=ASSOCIATE_TAG,
    country=LOCALE
)

# === Google Sheets API 認証情報 ===
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
GCP_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

def write_to_sheet(spreadsheet_id, sheet_name, rows, headers):
    if not GCP_CREDENTIALS_JSON:
        raise ValueError("❌ GOOGLE_CREDENTIALS が未設定です")

    creds_dict = json.loads(GCP_CREDENTIALS_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
    sheet.clear()
    sheet.append_row(headers)
    for row in rows:
        sheet.append_row(row)

@app.route("/")
def index():
    return "✅ Amazon to Sheet API is running!", 200

@app.route("/test-credentials")
def test_credentials():
    raw = os.getenv("GOOGLE_CREDENTIALS")
    if not raw:
        return jsonify({"error": "GOOGLE_CREDENTIALS が読み込めません"}), 500
    try:
        creds_dict = json.loads(raw)
        return jsonify({
            "message": "✅ 認証情報を正常に読み込みました",
            "client_email": creds_dict.get("client_email", "なし")
        })
    except Exception as e:
        return jsonify({"error": f"JSONエラー: {str(e)}"}), 500

@app.route("/amazon-asin-search", methods=["POST"])
def amazon_asin_search():
    try:
        data = request.get_json()
        asin_list = data.get("asin_list", [])
        spreadsheet_id = data.get("spreadsheet_id")
        sheet_name = data.get("sheet_name", "AmazonASIN出力")

        if not asin_list or not spreadsheet_id:
            return jsonify({"error": "Missing asin_list or spreadsheet_id"}), 400

        items = amazon.get_items(asin_list)

        results = []
        for info in items:
            try:
                title = info.item_info.title.display_value if info.item_info and info.item_info.title else ""
                url = info.detail_page_url or ""
                pub_date = info.item_info.product_info.release_date.display_value if info.item_info.product_info and info.item_info.product_info.release_date else ""

                offer = info.offers.listings[0] if info.offers and info.offers.listings else None
                price = offer.price.display_amount if offer and offer.price else ""
                list_price = offer.saving_basis.display_amount if offer and offer.saving_basis else ""
                discount_percent = offer.savings.percentage if offer and offer.savings else ""

                # 割引率がなければ自力計算
                if not discount_percent and offer and offer.price and offer.saving_basis:
                    try:
                        current = float(offer.price.amount)
                        original = float(offer.saving_basis.amount)
                        if original > current:
                            discount_percent = round((original - current) / original * 100)
                    except:
                        discount_percent = ""

                desc = info.item_info.features.display_values[0] if info.item_info.features and info.item_info.features.display_values else ""

                results.append([
                    title, url, pub_date, price, list_price,
                    f"{discount_percent}%" if discount_percent else "", desc
                ])
            except Exception as e:
                print(f"⚠️ スキップ: {e}")
                continue

        headers = ["商品名", "URL", "発売日", "現在価格", "元価格", "割引率", "説明"]
        write_to_sheet(spreadsheet_id, sheet_name, results, headers)

        return jsonify({"message": f"{len(results)} 件出力しました"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

