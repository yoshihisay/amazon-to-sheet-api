from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from amazon_paapi import AmazonApi
from datetime import datetime
from dateutil import parser
import os
import json

app = Flask(__name__)

# 🔧 共通処理関数：Amazon検索 → スプレッドシート出力（重複除外・ページ制御・予約対応・シート指定）
def search_and_write(keyword, preorder_only=False, start_page=1, sheet_name="シート1"):
    try:
        # Google Sheets 認証
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
        credentials_dict = json.loads(credentials_json)
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        gc = gspread.authorize(credentials)

        # 指定シート名で開く
        worksheet = gc.open("スクレイピング検証").worksheet(sheet_name)

        # 既存のURLをC列から取得（重複排除用）
        existing_urls = set(worksheet.col_values(3))  # C列がURL

        # Amazon API 認証
        amazon = AmazonApi(
            os.environ.get('AKPAWNVMBA1746859276'),
            os.environ.get('1jVIahJObZ5zgRe65uuchg8cLHVu+ZAblCd+Hb2g'),
            os.environ.get('marumooon0210-22'),
            'JP'
        )

        col_values = worksheet.col_values(2)
        row_index = len(col_values) + 1
        today = datetime.today()

        for page in range(start_page, start_page + 3):  # 3ページずつ
            response = amazon.search_items(keywords=keyword, search_index='All', item_count=10, item_page=page)
            for item in response.items:
                if not item.item_info.title or not item.item_info.product_info.release_date:
                    continue

                try:
                    release_date = parser.isoparse(item.item_info.product_info.release_date.display_value)
                    if preorder_only and release_date <= today:
                        continue
                    release_str = release_date.strftime('%Y-%m-%d')
                except:
                    continue

                title = item.item_info.title.display_value
                url = item.detail_page_url.split('?')[0]

                if url in existing_urls:
                    continue

                worksheet.update(values=[[title, url, release_str]], range_name=f'B{row_index}:D{row_index}')
                row_index += 1
                existing_urls.add(url)

        return jsonify({
            "status": "success",
            "message": f"'{keyword}' の商品{'（予約のみ）' if preorder_only else ''}をシート「{sheet_name}」に出力しました。重複除外済み。"
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ✅ 通常商品（全件）
@app.route('/amazon-to-sheet', methods=['POST'])
def amazon_to_sheet():
    keyword = request.json.get("keyword", "マテル")
    start_page = int(request.json.get("start_page", 1))
    sheet_name = request.json.get("sheet_name", "シート1")
    return search_and_write(keyword, start_page=start_page, sheet_name=sheet_name)

# ✅ 予約商品のみ
@app.route('/preorder', methods=['POST'])
def extract_preorder():
    keyword = request.json.get("keyword", "マテル")
    start_page = int(request.json.get("start_page", 1))
    sheet_name = request.json.get("sheet_name", "シート1")
    return search_and_write(keyword, preorder_only=True, start_page=start_page, sheet_name=sheet_name)

# WSGI用（Render）
app = app