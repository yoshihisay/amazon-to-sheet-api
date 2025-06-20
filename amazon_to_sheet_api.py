from flask import Flask, request, jsonify
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from amazon_paapi import AmazonApi

app = Flask(__name__)

# Amazon API 認証情報
ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")
LOCALE = "JP"

# Google Sheets 認証設定
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
GCP_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

# Amazon API クライアント
amazon = AmazonApi(ACCESS_KEY, SECRET_KEY, ASSOCIATE_TAG, LOCALE)

def write_to_sheet(spreadsheet_id, sheet_name, rows):
    creds_dict = eval(GCP_CREDENTIALS_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
    sheet.clear()
    sheet.append_row(["商品名", "URL", "発売日", "価格", "説明"])
    for row in rows:
        sheet.append_row(row)

@app.route("/")
def index():
    return "Amazon to Sheet API is running!", 200

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
            results.append([title, url, pub_date, price, desc])

        write_to_sheet(spreadsheet_id, sheet_name, results)
        return jsonify({"message": f"{len(results)} items written to sheet '{sheet_name}'"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/amazon-asin-search", methods=["POST"])
def amazon_asin_search():
    try:
        data = request.get_json()
        asin_list = data.get("asin_list", [])
        spreadsheet_id = data.get("spreadsheet_id")
        sheet_name = data.get("sheet_name", "AmazonASIN出力")

        if not asin_list or not spreadsheet_id:
            return jsonify({"error": "ASINリストまたはスプレッドシートIDが不足しています"}), 400

        items = amazon.get_items(asin_list)

        results = []
        for item in items:
            title = item.title or ""
            url = item.detail_page_url or ""
            price = item.list_price or ""
            pub_date = item.publication_date or ""
            desc = item.features[0] if item.features else ""
            results.append([title, url, pub_date, price, desc])

        write_to_sheet(spreadsheet_id, sheet_name, results)
        return jsonify({"message": f"{len(results)} 件の商品を出力しました"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

