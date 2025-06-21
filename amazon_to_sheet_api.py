import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from amazon.paapi import AmazonApi
import gspread
from google.oauth2 import service_account

# 環境変数の読み込み（Render環境では不要だがローカル検証用に）
load_dotenv()

app = Flask(__name__)

@app.route("/")
def home():
    return "Amazon to Sheet API is running."

@app.route("/amazon-to-sheet", methods=["POST"])
def amazon_to_sheet():
    data = request.json
    keyword = data.get("keyword")
    sheet_name = data.get("sheet_name", "Amazon出力")

    if not keyword:
        return jsonify({"error": "キーワードが指定されていません。"}), 400

    try:
        amazon = AmazonApi(
            access_key=os.getenv("AMAZON_ACCESS_KEY"),
            secret_key=os.getenv("AMAZON_SECRET_KEY"),
            associate_tag=os.getenv("AMAZON_ASSOCIATE_TAG"),
            country="JP"
        )

        response = amazon.search_items(keywords=keyword, search_index="All")
        items = []

        for item in response.items:
            asin = item.asin
            title = item.item_info.title.display_value if item.item_info.title else ""
            url = item.detail_page_url
            price = ""

            try:
                price = item.offers.listings[0].price.display_amount
            except:
                price = "価格情報なし"

            items.append([asin, title, price, url])

        # Google Sheets 書き込み
        credentials = service_account.Credentials.from_service_account_info(json.loads(os.environ["GOOGLE_CREDENTIALS"]))
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])
        worksheet = sh.worksheet(sheet_name)
        worksheet.clear()
        worksheet.append_row(["ASIN", "タイトル", "価格", "URL"])
        for row in items:
            worksheet.append_row(row)

        return jsonify({"message": "出力成功", "count": len(items)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/amazon-asin-to-sheet", methods=["POST"])
def amazon_asin_to_sheet():
    data = request.json
    asin_list = data.get("asins", [])
    sheet_name = data.get("sheet_name", "AmazonASIN出力")

    if not asin_list:
        return jsonify({"error": "ASINリストが空です。"}), 400

    try:
        amazon = AmazonApi(
            access_key=os.getenv("AMAZON_ACCESS_KEY"),
            secret_key=os.getenv("AMAZON_SECRET_KEY"),
            associate_tag=os.getenv("AMAZON_ASSOCIATE_TAG"),
            country="JP"
        )

        response = amazon.get_items(asin_list)
        items = []

        for item in response.items_result.items:
            asin = item.asin
            title = item.item_info.title.display_value if item.item_info.title else ""
            url = item.detail_page_url
            price = ""

            try:
                price = item.offers.listings[0].price.display_amount
            except:
                price = "価格情報なし"

            items.append([asin, title, price, url])

        credentials = service_account.Credentials.from_service_account_info(json.loads(os.environ["GOOGLE_CREDENTIALS"]))
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])
        worksheet = sh.worksheet(sheet_name)
        worksheet.clear()
        worksheet.append_row(["ASIN", "タイトル", "価格", "URL"])
        for row in items:
            worksheet.append_row(row)

        return jsonify({"message": "ASIN出力成功", "count": len(items)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)

