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
        # 💬 ログ出力
        print(f"🔍 キーワード: {keyword}")
        print(f"📄 出力先シート名: {sheet_name}")
        print(f"📦 開始ページ: {start_page}")
        print(f"📅 予約商品のみ: {preorder_only}")

        # Google Sheets 認証
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
        credentials_dict = json.loads(credentials_json)
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        gc = gspread.authorize(credentials)

        worksheet = gc.open("スクレイピング検証").worksheet(sheet_name)
        existing_urls = set(worksheet.col_values(3))  # C列がURL

        # Amazon API 認証
        access_key = os.environ.get('AKPAWNVMBA1746859276')
        secret_key = os.environ.get('1jVIahJObZ5zgRe65uuchg8cLHVu+ZAblCd+Hb2g')
        partner_tag = os.environ.get('marumooon0210-22')
        print(f"🔑 Amazon認証情報 → access_key: {bool(access_key)}, secret_key: {bool(secret_key)}, tag: {partner_tag}")

        amazon = AmazonApi(access_key, secret_key, partner_tag, 'JP')

        col_values = worksheet.col_values(2)
        row_index = len(col_values) + 1
        today = datetime.today()

        for page in range(start_page, start_page + 3):
            print(f"📄 ページ {page} を検索中…")
            response = amazon.search_items(keywords=keyword, search_index='All', item_count=10, item_page=page)
            for item in response.items:
                if not item.item_info.title or not item.item_info.product_info.release_date:
                    continue

                try:
                    release_date = parser.isoparse(item.item_info.product_info.release_date.display_value)
                    if preorder_only and release_date <= today:
                        continue
                    release_str = release_date.strftime('%Y-%m-%d')
                except Exception as e:
                    print(f"⚠️ 日付変換失敗: {e}")
                    continue

                title = item.item_info.title.display_value
                url = item.detail_page_url.split('?')[0]

                if url in existing_urls:
                    print(f"⛔ 重複スキップ: {url}")
                    continue

                worksheet.update(values=[[title, url, release_str]], range_name=f'B{row_index}:D{row_index}')
                print(f"✅ 出力: {title} ({release_str}) → {url}")
                row_index += 1
                existing_urls.add(url)

        return jsonify({
            "status": "success",
            "message": f"'{keyword}' の商品{'（予約のみ）' if preorder_only else ''}をシート「{sheet_name}」に出力しました。重複除外済み。"
        })

    except Exception as e:
        print(f"❌ エラー発生: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ✅ 通常商品（全件）
@app.route('/amazon-to-sheet', methods=['POST'])
def amazon_to_sheet():
    data = request.get_json()
    print("📩 リクエスト受信: ", data)
    keyword = data.get("keyword", "マテル")
    start_page = int(data.get("start_page", 1))
    sheet_name = data.get("sheet_name", "シート1")
    return search_and_write(keyword, start_page=start_page, sheet_name=sheet_name)

# ✅ 予約商品のみ
@app.route('/preorder', methods=['POST'])
def extract_preorder():
    data = request.get_json()
    print("📩 リクエスト受信（予約）: ", data)
    keyword = data.get("keyword", "マテル")
    start_page = int(data.get("start_page", 1))
    sheet_name = data.get("sheet_name", "シート1")
    return search_and_write(keyword, preorder_only=True, start_page=start_page, sheet_name=sheet_name)

# WSGI用（Render）
app = app