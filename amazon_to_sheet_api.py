from flask import Flask, request, jsonify
import os
import json
from amazon.paapi import AmazonApi
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# ========================
# 認証テスト用エンドポイント
# ========================
@app.route("/test-credentials")
def test_credentials():
    try:
        credentials_json = os.getenv("GOOGLE_CREDENTIALS")
        if not credentials_json:
            return jsonify({"error": "No key could be detected."}), 500

        creds_dict = json.loads(credentials_json)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        # 動作確認用のメール返却
        return jsonify({"client_email": creds_dict.get("client_email"), "message": "✅ 認証情報を正常に読み込みました"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# Amazon API 認証
# ========================
amazon = AmazonApi(
    access_key=os.getenv("AMAZON_ACCESS_KEY"),
    secret_key=os.getenv("AMAZON_SECRET_KEY"),
    tag=os.getenv("AMAZON_ASSOCIATE_TAG"),
    country="JP"
)

# ========================
# スプレッドシート書き込み関数
# ========================
def write_to_sheet(spreadsheet_id, sheet_name, data, headers):
    credentials_json = os.getenv("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(credentials_json)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
    sheet.clear()
    sheet.append_row(headers)
    for row in data:
        sheet.append_row(row)

# ========================
# ASIN検索エンドポイント
# ========================
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

        for asin, info in zip(asin_list, items):
            try:
                title = info.item_info.title.display_value if info.item_info and info.item_info.title else ""
                url = info.detail_page_url or ""
                pub_date = info.item_info.product_info.release_date.display_value if info.item_info.product_info and info.item_info.product_info.release_date else ""

                offer = info.offers.listings[0] if info.offers and info.offers.listings else None
                price = offer.price.display_amount if offer and offer.price else ""
                list_price = offer.saving_basis.display_amount if offer and offer.saving_basis else ""
                discount_percent = offer.savings.percentage if offer and offer.savings else ""

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
                print(f"⚠️ {asin} スキップ: {item_error}")
                continue

        if not results:
            return jsonify({"error": "取得に失敗しました。ASINデータが正しく取得できていない可能性があります"}), 500

        headers = ["商品名", "URL", "発売日", "現在価格", "元価格", "割引率", "説明"]
        write_to_sheet(spreadsheet_id, sheet_name, results, headers)

        return jsonify({"message": f"{len(results)} items written to sheet '{sheet_name}'"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# アプリ起動（ローカル用）
# ========================
if __name__ == "__main__":
    app.run(debug=True)

