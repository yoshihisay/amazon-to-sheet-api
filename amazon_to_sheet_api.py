import gspread
from oauth2client.service_account import ServiceAccountCredentials
from amazon_paapi import AmazonApi
from datetime import datetime
from dateutil import parser

# 🔐 Google Sheets API 認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(credentials)

# 📄 スプレッドシートを開く
spreadsheet = gc.open("スクレイピング検証")
worksheet = spreadsheet.sheet1

# 🔐 Amazon PA-API 認証情報
access_key = 'AKPAWNVMBA1746859276'
secret_key = '1jVIahJObZ5zgRe65uuchg8cLHVu+ZAblCd+Hb2g'
associate_tag = 'marumooon0210-22'
country = 'JP'

# 🔍 Amazon API インスタンス
amazon = AmazonApi(access_key, secret_key, associate_tag, country)

# 🧭 空白行を探す（B列の最終データ行 + 1）
def get_next_empty_row(col_letter='B'):
    col_values = worksheet.col_values(ord(col_letter.upper()) - 64)
    return len(col_values) + 1

row_index = get_next_empty_row()

# 🔄 複数ページ（1〜3ページ = 最大30件）
for page in range(1, 4):
    response = amazon.search_items(
        keywords='マテル',
        search_index='All',
        item_count=10,
        item_page=page
    )

    items = response.items
    print(f"{page}ページ目: {len(items)} 件")

    for item in items:
        title = item.item_info.title.display_value if item.item_info.title else 'N/A'
        url = item.detail_page_url.split('?')[0] if item.detail_page_url else 'N/A'

        if item.item_info and item.item_info.product_info and item.item_info.product_info.release_date:
            raw_release_str = item.item_info.product_info.release_date.display_value
            try:
                parsed_date = parser.isoparse(raw_release_str)
                release_str = parsed_date.strftime('%Y-%m-%d')
            except Exception:
                continue

            # B列（商品名）、C列（URL）、D列（発売日）に出力
            worksheet.update(
                values=[[title, url, release_str]],
                range_name=f'B{row_index}:D{row_index}'
            )
            row_index += 1