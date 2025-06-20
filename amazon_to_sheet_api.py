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

# === Google Sheets API 認証情報 ===
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
GCP_CREDENTIALS_JSON = os.getenv("GCP_CREDENTIALS_JSON")

# === Amazon API クライアント初期化 ===
amazon = AmazonApi(ACCESS_KEY, SECRET_KEY, ASSOCIATE_TAG, LOCALE)

# === スプレッドシートへ出力 ===
def write_to_sheet(spreadsheet_id, sheet_name, rows, headers):
    creds_dict = json.loads(GCP_CREDENTIALS_JSON)  # ✅ 安全なJSONパース
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
    sheet.clear()
    sheet.append_row(headers)
    for row in rows:
        sheet.append_row(row)

# === 動作確認用ルート ===
@app.route("/")
def index():
    return "✅ Amazon to Sheet API is running!", 200

# === キーワード検索 API ===
@app.route("/amazon-search", methods=["POST"])
def amazon_search():
    try:
        data = request.get_json()
        keyword = data.get("keyword")
        spreadsheet_id = data.get("spreadsheet_id")
        sheet_name = data.get("sheet_name", "Amazon検索結果")

        if not keyword or not spreadsheet_id:
            return jsonify({"error": "Missing keyword or spreadsheet_id"}), 400

        items = amazon.search_items(keywords=keyword, item_count=10)

        results = []
        for item in items:
            title = item.title or ""
            url = item.detail_page_url or ""
            price = item.list_price or ""
            pub_date = item.publication_date or ""
            desc = item.features[0] if item.features else ""
            results.append([title, url, pub_date, price, "", "", desc])  # カラム合わせ

        headers = ["商品名", "URL", "発売日", "現在価格", "元価格", "割引率", "説明"]
        write_to_sheet(spreadsheet_id, sheet_name, results, headers)

        return jsonify({"message": f"{len(results)} items written to sheet '{sheet_name}'"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === ASINリスト検索 API ===
@app.route("/amazon-asin-search", methods=["POST"])
def amazon_asin_search():
    try:
        data = request.get_json()
        asin_list = data.get("asin_list", [])
        spreadsheet_id = data.get("spreadsheet_id")
        sheet_name = data.get("sheet_name", "AmazonASIN出力")

        if not asin_list or not spreadsheet_id:
            return jsonify({"error": "Missing ASINs or spreadsheet_id"}), 400

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

                # 割引率が無い場合は手動計算
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
                    title,
                    url,
                    pub_date,
                    price,
                    list_price,
                    f"{discount_percent}%" if discount_percent else "",
                    desc
                ])
            except Exception as item_error:
                print(f"⚠️ 商品処理スキップ: {item_error}")
                continue

        headers = ["商品名", "URL", "発売日", "現在価格", "元価格", "割引率", "説明"]
        write_to_sheet(spreadsheet_id, sheet_name, results, headers)

        return jsonify({"message": f"{len(results)} items written to sheet '{sheet_name}'"}), 200

    except Exception as e:
        print(f"❌ ASIN検索エラー: {e}")
        return jsonify({"error": str(e)}), 500

# === アプリ起動 ===
if __name__ == "__main__":
    app.run(debug=True)

