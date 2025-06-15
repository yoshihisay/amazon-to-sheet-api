from flask import Flask, request, jsonify
from amazon_paapi import AmazonAPI
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import traceback

app = Flask(__name__)

# === Amazon PA-API 認証 ===
ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY", "your_access_key")
SECRET_KEY = os.getenv("AMAZON_SECRET_KEY", "your_secret_key")
ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "your_tag")
LOCALE = "JP"

# === Google Sheets 認証 ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
gc = gspread.authorize(credentials)

# === 通常検索・予約・割引フィルター ===
def fetch_amazon_items_filtered(keyword, start_page=1, max_pages=10, search_index="All", filter_type="normal"):
    amazon = AmazonAPI(ACCESS_KEY, SECRET_KEY, ASSOCIATE_TAG, LOCALE)
    items = []
    seen_urls = set()
    pages_fetched = 0
    today = datetime.now().date()

    for page in range(start_page, min(start_page + max_pages, 11)):
        try:
            print(f"\n📄 ページ {page} を検索中…")
            response = amazon.search_items(
                keywords=keyword,
                search_index=search_index,
                item_count=10,
                item_page=page
            )

            raw_items = getattr(response, "items", None)
            if not raw_items:
                print(f"⚠️ ページ {page} に商品が見つかりません（空ページ）")
                pages_fetched += 1
                time.sleep(1.5)
                continue

            for item in raw_items:
                try:
                    url = getattr(item, "detail_page_url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = getattr(item.item_info.title, "display_value", "") if item.item_info and item.item_info.title else ""
                    release_date = ""
                    release_date_obj = None

                    if item.item_info and item.item_info.product_info and getattr(item.item_info.product_info, "release_date", None):
                        release_date = item.item_info.product_info.release_date.display_value
                        try:
                            release_date_obj = datetime.strptime(release_date, "%Y-%m-%d").date()
                        except:
                            release_date_obj = None

                    price = 0
                    list_price = 0
                    discount = 0

                    if item.offers and item.offers.listings:
                        offer = item.offers.listings[0]
                        if offer.price and offer.price.amount:
                            price = offer.price.amount
                        if offer.price and offer.price.savings and offer.price.savings.amount:
                            discount = offer.price.savings.amount

                    if item.item_info and item.item_info.product_info and getattr(item.item_info.product_info, "list_price", None):
                        list_price = item.item_info.product_info.list_price.amount

                    if filter_type == "normal":
                        if release_date_obj and release_date_obj > today:
                            continue
                    elif filter_type == "reserve":
                        if not release_date_obj or release_date_obj <= today:
                            continue
                    elif filter_type == "discount":
                        if not (list_price and price and price < list_price):
                            continue

                    items.append({
                        "title": title,
                        "url": url,
                        "price": price,
                        "list_price": list_price,
                        "discount": discount,
                        "release_date": release_date
                    })

                except Exception as item_error:
                    print(f"⚠️ 商品処理スキップ: {item_error}")
                    continue

            pages_fetched += 1
            time.sleep(1.5)

        except Exception as e:
            print(f"❌ ページ {page} でエラー: {e}")
            traceback.print_exc()
            pages_fetched += 1
            continue

    return items, pages_fetched

# === ASIN指定検索 ===
def fetch_items_by_asins(asin_list):
    amazon = AmazonAPI(ACCESS_KEY, SECRET_KEY, ASSOCIATE_TAG, LOCALE)
    items = []
    try:
        response = amazon.get_items(asin_list)
        for item in response.items:
            title = item.item_info.title.display_value if item.item_info and item.item_info.title else ""
            url = item.detail_page_url
            price = item.offers.listings[0].price.amount if item.offers and item.offers.listings else 0
            list_price = item.item_info.product_info.list_price.amount if item.item_info and item.item_info.product_info and item.item_info.product_info.list_price else 0
            discount = list_price - price if list_price > price else 0
            release_date = item.item_info.product_info.release_date.display_value if item.item_info and item.item_info.product_info and item.item_info.product_info.release_date else ""
            items.append({
                "title": title,
                "url": url,
                "price": price,
                "list_price": list_price,
                "discount": discount,
                "release_date": release_date
            })
    except Exception as e:
        print("❌ ASIN取得エラー:", e)
        traceback.print_exc()
    return items

# === 出力共通関数 ===
def write_to_sheet(sheet_name, items):
    spreadsheet = gc.open(sheet_name)
    sheet = spreadsheet.sheet1
    existing = sheet.get_all_values()
    start_row = len(existing) + 1 if existing else 1

    for idx, item in enumerate(items):
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            item.get("title", ""),
            item.get("url", ""),
            item.get("price", ""),
            item.get("list_price", ""),
            item.get("discount", ""),
            item.get("release_date", "")
        ]
        sheet.insert_row(row, start_row + idx)

# === APIエンドポイント ===
@app.route("/amazon-to-sheet", methods=["POST"])
def amazon_to_sheet():
    try:
        data = request.get_json()
        print(f"\n📩 リクエスト受信: {data}")

        keyword = data.get("keyword", "").strip()
        start_page = int(data.get("start_page", 1))
        max_pages = int(data.get("page_count", 10))
        sheet_name = data.get("sheet_name", "Amazon出力")
        search_index = data.get("search_index", "All")
        filter_type = data.get("type", "normal")

        items, fetched_pages = fetch_amazon_items_filtered(
            keyword=keyword,
            start_page=start_page,
            max_pages=max_pages,
            search_index=search_index,
            filter_type=filter_type
        )

        if items:
            write_to_sheet(sheet_name, items)
            return jsonify({
                "status": "success",
                "message": f"{len(items)}件の商品をシート『{sheet_name}』に出力しました。",
                "fetched_pages": fetched_pages
            })
        else:
            return jsonify({
                "status": "ok",
                "message": f"'{keyword}' に該当する商品が見つかりませんでした。",
                "fetched_pages": fetched_pages
            })

    except Exception as e:
        print(f"❌ APIエラー: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 200

@app.route("/amazon-asin-to-sheet", methods=["POST"])
def asin_to_sheet():
    try:
        data = request.get_json()
        print(f"\n📩 ASINリクエスト受信: {data}")
        asin_list = data.get("asin_list", [])
        sheet_name = data.get("sheet_name", "Amazon出力")
        if not asin_list:
            return jsonify({"status": "error", "message": "ASINが指定されていません"})

        items = fetch_items_by_asins(asin_list)

        if items:
            write_to_sheet(sheet_name, items)
            return jsonify({
                "status": "success",
                "message": f"{len(items)}件の商品をシート『{sheet_name}』に出力しました。",
                "count": len(items)
            })
        else:
            return jsonify({
                "status": "ok",
                "message": "商品情報が取得できませんでした"
            })

    except Exception as e:
        print(f"❌ ASIN APIエラー: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)})

# === 起動（Renderでは無視されるがローカル動作用） ===
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=10000)
