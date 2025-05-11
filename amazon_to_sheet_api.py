from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from amazon_paapi import AmazonApi
from datetime import datetime
from dateutil import parser
import os
import json

app = Flask(__name__)

@app.route('/amazon-to-sheet', methods=['POST'])
def amazon_to_sheet():
    try:
        # ✅ Google Sheets 認証（credentials.json → 環境変数から）
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
        credentials_dict = json.loads(credentials_json)
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        gc = gspread.authorize(credentials)
        worksheet = gc.open("スクレイピング検証").sheet1

        # ✅ Amazon API 認証（できれば環境変数へ移行）
        amazon = AmazonApi(
            access_key=os.environ.get('AMAZON_ACCESS_KEY', 'AKPAWNVMBA1746859276'),
            secret_key=os.environ.get('AMAZON_SECRET_KEY', '1jVIahJObZ5zgRe65uuchg8cLHVu+ZAblCd+Hb2g'),
            associate_tag=os.environ.get('AMAZON_ASSOCIATE_TAG', 'marumooon0210-22'),
            country='JP'
        )

        # スプレッドシート書き込み開始位置
        col_values = worksheet.col_values(2)
        row_index = len(col_values) + 1

        for page in range(1, 4):
            response = amazon.search_items(keywords='マテル', search_index='All', item_count=10, item_page=page)
            for item in response.items:
                if not item.item_info.title or not item.item_info.product_info.release_date:
                    continue
                title = item.item_info.title.display_value
                url = item.detail_page_url.split('?')[0]
                try:
                    release_str = parser.isoparse(item.item_info.product_info.release_date.display_value).strftime('%Y-%m-%d')
                except:
                    continue
                worksheet.update(values=[[title, url, release_str]], range_name=f'B{row_index}:D{row_index}')
                row_index += 1

        return jsonify({"status": "success", "message": "Data written to sheet."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

app = app  # WSGI用のエントリーポイント