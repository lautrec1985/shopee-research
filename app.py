import streamlit as st
import httpx
import asyncio
import csv
import io
import re
import time
from typing import Optional
import pandas as pd

st.set_page_config(
    page_title="Shopee Research Tool",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Mono', monospace;
}

.main-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 2rem;
    border-radius: 12px;
    margin-bottom: 2rem;
    border: 1px solid #e94560;
}

.metric-card {
    background: #1a1a2e;
    border: 1px solid #0f3460;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
}

.preferred-badge {
    background: #f0a500;
    color: #000;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: bold;
}

.stButton > button {
    background: #e94560 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'DM Mono', monospace !important;
    font-weight: 500 !important;
}

.stButton > button:hover {
    background: #c73652 !important;
}

div[data-testid="stTab"] {
    font-family: 'DM Mono', monospace;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
SHOPEE_BASE = "https://shopee.co.jp"
SHOPEE_API = "https://shopee.co.jp/api/v4"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://shopee.co.jp/",
    "Accept": "application/json",
    "X-API-SOURCE": "pc",
    "X-Requested-With": "XMLHttpRequest",
}

SHOPEE_CATEGORIES = {
    "Electronics（電子機器）": 11044906,
    "Fashion（ファッション）": 11044914,
    "Home & Living（ホーム）": 11044916,
    "Sports & Outdoors（スポーツ）": 11044932,
    "Toys & Games（おもちゃ）": 11044924,
    "Baby & Kids（ベビー）": 11044956,
    "Health & Beauty（美容）": 11044970,
    "Food & Beverages（食品）": 11044972,
    "Books & Stationery（本）": 11044982,
    "Automotive（自動車）": 11044998,
}

# ─────────────────────────────────────────────
# API Functions
# ─────────────────────────────────────────────

def shopee_search(keyword: str, page: int = 0) -> dict:
    params = {
        "by": "sales",
        "keyword": keyword,
        "limit": 60,
        "newest": page * 60,
        "order": "desc",
        "page_type": "search",
        "scenario": "PAGE_GLOBAL_SEARCH",
        "version": 2,
    }
    try:
        with httpx.Client(headers=HEADERS, timeout=20) as client:
            r = client.get(f"{SHOPEE_API}/search/search_items/", params=params)
            return r.json() if r.status_code == 200 else {}
    except Exception as e:
        st.warning(f"API エラー: {e}")
        return {}

def shopee_category_search(category_id: int, page: int = 0) -> dict:
    params = {
        "by": "sales",
        "limit": 60,
        "newest": page * 60,
        "order": "desc",
        "catid": category_id,
        "version": 2,
    }
    try:
        with httpx.Client(headers=HEADERS, timeout=20) as client:
            r = client.get(f"{SHOPEE_API}/search/search_items/", params=params)
            return r.json() if r.status_code == 200 else {}
    except Exception as e:
        st.warning(f"API エラー: {e}")
        return {}

def get_shop_info(shop_id: int) -> dict:
    try:
        with httpx.Client(headers=HEADERS, timeout=20) as client:
            r = client.get(f"{SHOPEE_API}/shop/get_shop_detail/", params={"shopid": shop_id})
            return r.json().get("data", {}) if r.status_code == 200 else {}
    except:
        return {}

def get_shop_items(shop_id: int, page: int = 0, limit: int = 100) -> list:
    params = {
        "shopid": shop_id,
        "sort_by": "sales",
        "order": "desc",
        "limit": limit,
        "offset": page * limit,
        "filter_sold_out": 0,
    }
    try:
        with httpx.Client(headers=HEADERS, timeout=20) as client:
            r = client.get(f"{SHOPEE_API}/recommend/recommend_items/", params=params)
            return r.json().get("items", []) if r.status_code == 200 else []
    except:
        return []

def search_asin(title: str) -> Optional[str]:
    clean = re.sub(r'[【】「」\[\]（）()]', ' ', title)
    clean = ' '.join(clean.split()[:8])
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ja-JP,ja;q=0.9",
        }
        with httpx.Client(headers=headers, timeout=15, follow_redirects=True) as client:
            r = client.get("https://www.amazon.co.jp/s", params={"k": clean})
            if r.status_code == 200:
                asins = re.findall(r'/dp/([A-Z0-9]{10})', r.text)
                if asins:
                    return asins[0]
    except:
        pass
    return None

def parse_item(item: dict, japan_only: bool) -> Optional[dict]:
    try:
        basic = item.get("item_basic", {})
        location = basic.get("shop_location", "")
        if japan_only and location != "Japan":
            return None
        return {
            "shop_name": basic.get("shop_name", ""),
            "shop_id": basic.get("shopid", 0),
            "shop_url": f"{SHOPEE_BASE}/{basic.get('shop_name', '')}",
            "item_id": basic.get("itemid", 0),
            "item_url": f"{SHOPEE_BASE}/{basic.get('shop_name', '')}-i.{basic.get('shopid', '')}.{basic.get('itemid', '')}",
            "title": basic.get("name", ""),
            "sold": basic.get("historical_sold", 0),
            "price": basic.get("price", 0) / 100000,
            "is_preferred": basic.get("is_preferred_plus_seller", False),
            "location": location,
        }
    except:
        return None

def to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1 style="color:#e94560; margin:0; font-size:1.8rem;">🛍️ Shopee Research Tool</h1>
    <p style="color:#a0aec0; margin:0.5rem 0 0 0; font-size:0.85rem;">shopee.co.jp セラー・商品リサーチ自動化</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "① キーワード検索",
    "② カテゴリ検索",
    "③ 専門店リサーチ",
    "④ ASIN抽出",
])

# ═══════════════════════════════════════════
# ① キーワード検索
# ═══════════════════════════════════════════
with tab1:
    st.subheader("🔤 キーワードから売れてる店舗を探す")

    col1, col2 = st.columns([2, 1])
    with col1:
        keyword = st.text_input("キーワード（英語）", placeholder="例: golf club, baby toy, kitchen")
    with col2:
        pages = st.number_input("検索ページ数", min_value=1, max_value=20, value=3)

    col3, col4, col5 = st.columns(3)
    with col3:
        japan_only = st.toggle("🇯🇵 日本セラーのみ", value=True)
    with col4:
        preferred_only = st.toggle("⭐ Preferredのみ", value=False)
    with col5:
        min_sold = st.number_input("最低Sold数", min_value=0, value=1)

    min_products = st.number_input("最低商品数（0=制限なし）", min_value=0, value=0)

    if st.button("🔍 検索実行", key="btn1"):
        if not keyword:
            st.warning("キーワードを入力してください")
        else:
            shops = {}
            items_list = []
            progress = st.progress(0, text="検索中...")

            for page in range(pages):
                progress.progress((page + 1) / pages, text=f"ページ {page+1}/{pages} 検索中...")
                data = shopee_search(keyword, page)
                raw = data.get("items", [])
                if not raw:
                    break

                for item in raw:
                    parsed = parse_item(item, japan_only)
                    if not parsed:
                        continue
                    if parsed["sold"] < min_sold:
                        continue
                    if preferred_only and not parsed["is_preferred"]:
                        continue

                    items_list.append(parsed)
                    sid = parsed["shop_id"]
                    if sid not in shops:
                        shops[sid] = {
                            "店舗名": parsed["shop_name"],
                            "店舗URL": parsed["shop_url"],
                            "Preferred": "⭐ YES" if parsed["is_preferred"] else "NO",
                            "地域": parsed["location"],
                            "総Sold数": 0,
                            "商品数": 0,
                        }
                    shops[sid]["総Sold数"] += parsed["sold"]
                    shops[sid]["商品数"] += 1

                time.sleep(0.5)

            progress.empty()

            shop_list = list(shops.values())
            if min_products > 0:
                shop_list = [s for s in shop_list if s["商品数"] >= min_products]

            shop_list.sort(key=lambda x: x["総Sold数"], reverse=True)

            st.success(f"✅ 店舗数: {len(shop_list)} 件 / 商品数: {len(items_list)} 件")

            if shop_list:
                df = pd.DataFrame(shop_list)
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    "📥 CSV ダウンロード",
                    data=to_csv(df),
                    file_name=f"shopee_keyword_{keyword}.csv",
                    mime="text/csv"
                )

# ═══════════════════════════════════════════
# ② カテゴリ検索
# ═══════════════════════════════════════════
with tab2:
    st.subheader("📂 カテゴリから商品を探す")

    cat_label = st.selectbox("カテゴリ", list(SHOPEE_CATEGORIES.keys()))
    cat_id = SHOPEE_CATEGORIES[cat_label]

    col1, col2, col3 = st.columns(3)
    with col1:
        japan_only2 = st.toggle("🇯🇵 日本セラーのみ", value=True, key="j2")
    with col2:
        min_sold2 = st.number_input("最低Sold数", min_value=0, value=1, key="ms2")
    with col3:
        pages2 = st.number_input("検索ページ数", min_value=1, max_value=20, value=3, key="p2")

    extract_asin = st.toggle("🔗 ASIN抽出（Amazon検索・時間かかります）", value=False)

    if st.button("🔍 カテゴリ検索", key="btn2"):
        items_list2 = []
        progress2 = st.progress(0, text="検索中...")

        for page in range(pages2):
            progress2.progress((page + 1) / pages2, text=f"ページ {page+1}/{pages2}...")
            data = shopee_category_search(cat_id, page)
            raw = data.get("items", [])
            if not raw:
                break

            for item in raw:
                parsed = parse_item(item, japan_only2)
                if not parsed:
                    continue
                if parsed["sold"] < min_sold2:
                    continue
                items_list2.append(parsed)

            time.sleep(0.5)

        if extract_asin and items_list2:
            asin_progress = st.progress(0, text="ASIN抽出中...")
            for i, item in enumerate(items_list2):
                asin_progress.progress((i + 1) / len(items_list2), text=f"ASIN抽出 {i+1}/{len(items_list2)}...")
                asin = search_asin(item["title"])
                item["asin"] = asin or ""
                item["amazon_url"] = f"https://www.amazon.co.jp/dp/{asin}" if asin else ""
                time.sleep(0.5)
            asin_progress.empty()

        progress2.empty()
        st.success(f"✅ 商品数: {len(items_list2)} 件")

        if items_list2:
            df2 = pd.DataFrame(items_list2)
            cols = ["title", "item_url", "sold", "price", "is_preferred", "shop_name"]
            if extract_asin:
                cols += ["asin", "amazon_url"]
            df2 = df2[[c for c in cols if c in df2.columns]]
            df2.columns = ["タイトル", "商品URL", "Sold", "価格(¥)", "Preferred", "店舗名"] + (["ASIN", "AmazonURL"] if extract_asin else [])

            st.dataframe(df2, use_container_width=True)
            st.download_button(
                "📥 CSV ダウンロード",
                data=to_csv(df2),
                file_name=f"shopee_category_{cat_label}.csv",
                mime="text/csv"
            )

# ═══════════════════════════════════════════
# ③ 専門店リサーチ
# ═══════════════════════════════════════════
with tab3:
    st.subheader("🏪 Amazon仕入れ専門店を探す")

    mode3 = st.radio("入力モード", ["キーワード入力", "CSVバッチ（複数キーワード）"], horizontal=True)

    if mode3 == "キーワード入力":
        keyword3 = st.text_input("キーワード（英語）", placeholder="例: golf, swimming, toys", key="kw3")
        keywords3 = [keyword3] if keyword3 else []
    else:
        st.info("1行に1キーワードのCSVをアップロードしてください（例: golf, swimming, toys）")
        csv_file = st.file_uploader("CSVファイル", type=["csv"])
        if csv_file:
            content = csv_file.read().decode("utf-8-sig")
            keywords3 = [row.strip() for row in content.split("\n") if row.strip()]
            st.write(f"キーワード数: {len(keywords3)} 件 → {', '.join(keywords3[:5])}...")
        else:
            keywords3 = []

    col1, col2 = st.columns(2)
    with col1:
        max_cats = st.select_slider("最大カテゴリ数（専門度）", options=[1, 2, 3, 4, 5], value=1)
        min_sold3 = st.number_input("最低Sold数", min_value=0, value=1, key="ms3")
    with col2:
        min_products3 = st.number_input("最低商品数（0=制限なし）", min_value=0, value=0, key="mp3")
        pages3 = st.number_input("検索ページ数", min_value=1, max_value=20, value=3, key="p3")

    col3, col4, col5 = st.columns(3)
    with col3:
        japan_only3 = st.toggle("🇯🇵 日本セラーのみ", value=True, key="j3")
    with col4:
        preferred_only3 = st.toggle("⭐ Preferredのみ", value=False, key="pref3")
    with col5:
        amazon_only = st.toggle("📦 Amazon仕入れのみ", value=True)

    if st.button("🔍 専門店リサーチ開始", key="btn3"):
        if not keywords3:
            st.warning("キーワードを入力してください")
        else:
            all_results = []

            for kw_idx, kw in enumerate(keywords3):
                st.write(f"🔍 **{kw}** を検索中... ({kw_idx+1}/{len(keywords3)})")
                shops3 = {}
                progress3 = st.progress(0)

                for page in range(pages3):
                    progress3.progress((page + 1) / pages3)
                    data = shopee_search(kw, page)
                    raw = data.get("items", [])
                    if not raw:
                        break

                    for item in raw:
                        parsed = parse_item(item, japan_only3)
                        if not parsed:
                            continue
                        if parsed["sold"] < min_sold3:
                            continue
                        if preferred_only3 and not parsed["is_preferred"]:
                            continue

                        sid = parsed["shop_id"]
                        if sid not in shops3:
                            shops3[sid] = parsed

                    time.sleep(0.5)

                progress3.empty()

                # Check each shop
                checked = st.progress(0, text="店舗チェック中...")
                shop_ids = list(shops3.keys())

                for i, sid in enumerate(shop_ids):
                    checked.progress((i + 1) / max(len(shop_ids), 1), text=f"店舗チェック {i+1}/{len(shop_ids)}...")
                    shop = shops3[sid]

                    # Get shop items to check categories & Amazon sourcing
                    items = get_shop_items(sid, page=0, limit=50)
                    if not items:
                        continue

                    # Category check (approximate using item data)
                    cat_ids = set()
                    amazon_count = 0
                    for it in items:
                        cats = it.get("categories", [])
                        if cats:
                            cat_ids.add(cats[0].get("catid", 0))
                        title = it.get("name", "")
                        if re.search(r'B0[A-Z0-9]{8}', title) or any(kw in title for kw in ["Amazon", "アマゾン"]):
                            amazon_count += 1

                    if len(cat_ids) > max_cats:
                        continue
                    if amazon_only and amazon_count < 1:
                        continue

                    # Get shop detail
                    info = get_shop_info(sid)

                    item_count = info.get("item_count", len(items))
                    if min_products3 > 0 and item_count < min_products3:
                        continue

                    all_results.append({
                        "検索キーワード": kw,
                        "店舗名": shop["shop_name"],
                        "店舗URL": shop["shop_url"],
                        "Preferred": "⭐ YES" if shop["is_preferred"] else "NO",
                        "カテゴリ数": len(cat_ids),
                        "商品数": item_count,
                        "フォロワー数": info.get("follower_count", 0),
                        "レビュー数": info.get("rating_count", 0),
                        "評価": round(info.get("rating_star", 0), 1),
                    })
                    time.sleep(0.3)

                checked.empty()

            st.success(f"✅ 専門店: {len(all_results)} 件見つかりました")

            if all_results:
                df3 = pd.DataFrame(all_results)
                st.dataframe(df3, use_container_width=True)
                st.download_button(
                    "📥 CSV ダウンロード",
                    data=to_csv(df3),
                    file_name="shopee_specialist_shops.csv",
                    mime="text/csv"
                )
                st.info("💡 このCSVを④ ASIN抽出タブに読み込ませると、全商品のASINを一括抽出できます")

# ═══════════════════════════════════════════
# ④ ASIN抽出
# ═══════════════════════════════════════════
with tab4:
    st.subheader("🔗 店舗の全商品ASINを一括抽出")

    st.info("③専門店リサーチのCSVを読み込む、またはURLを直接入力してください")

    input_mode4 = st.radio("入力方法", ["CSVから読込（③の出力）", "URL直接入力"], horizontal=True)

    shop_urls = []
    if input_mode4 == "CSVから読込（③の出力）":
        csv4 = st.file_uploader("CSVファイル（店舗URL列が必要）", type=["csv"], key="csv4")
        if csv4:
            df_in = pd.read_csv(csv4)
            url_col = None
            for col in df_in.columns:
                if "URL" in col or "url" in col:
                    url_col = col
                    break
            if url_col:
                shop_urls = df_in[url_col].dropna().tolist()
                st.write(f"✅ {len(shop_urls)} 店舗を読み込みました")
                st.write(shop_urls[:5])
            else:
                st.error("「URL」を含む列が見つかりません")
    else:
        urls_text = st.text_area("店舗URL（1行1URL）", placeholder="https://shopee.co.jp/shopname1\nhttps://shopee.co.jp/shopname2", height=150)
        shop_urls = [u.strip() for u in urls_text.split("\n") if u.strip()]

    if shop_urls:
        st.write(f"対象店舗数: **{len(shop_urls)}** 件")

    if st.button("🔎 ASIN一括抽出開始", key="btn4") and shop_urls:
        all_asins = []
        total_progress = st.progress(0, text="ASIN抽出中...")

        for shop_idx, shop_url in enumerate(shop_urls):
            shop_name = shop_url.rstrip("/").split("/")[-1]
            st.write(f"📦 **{shop_name}** の商品を取得中...")

            # Get shop ID from search (simplified)
            page = 0
            shop_items = []
            while True:
                # Try to get items via recommendation API
                # Need shop_id - extract from search
                data = shopee_search(shop_name, 0)
                raw = data.get("items", [])
                found_id = None
                for it in raw:
                    basic = it.get("item_basic", {})
                    if basic.get("shop_name", "") == shop_name:
                        found_id = basic.get("shopid")
                        break
                if found_id:
                    items = get_shop_items(found_id, page=page, limit=100)
                    if not items:
                        break
                    shop_items.extend(items)
                    page += 1
                    if page > 5:
                        break
                    time.sleep(0.5)
                else:
                    break

            item_progress = st.progress(0, text=f"{shop_name}: ASIN検索中...")
            for i, item in enumerate(shop_items):
                item_progress.progress((i + 1) / max(len(shop_items), 1))
                title = item.get("name", "")
                asin = search_asin(title)

                all_asins.append({
                    "店舗名": shop_name,
                    "店舗URL": shop_url,
                    "タイトル": title,
                    "商品URL": f"{SHOPEE_BASE}/{shop_name}-i.{item.get('shopid','')}.{item.get('itemid','')}",
                    "Sold": item.get("historical_sold", 0),
                    "価格(¥)": item.get("price", 0) / 100000,
                    "ASIN": asin or "",
                    "Amazon URL": f"https://www.amazon.co.jp/dp/{asin}" if asin else "",
                })
                time.sleep(0.5)

            item_progress.empty()
            total_progress.progress((shop_idx + 1) / len(shop_urls))

        total_progress.empty()

        asin_found = len([a for a in all_asins if a["ASIN"]])
        st.success(f"✅ 商品数: {len(all_asins)} 件 / ASIN取得: {asin_found} 件")

        if all_asins:
            df4 = pd.DataFrame(all_asins)
            st.dataframe(df4, use_container_width=True)
            st.download_button(
                "📥 ASIN CSV ダウンロード",
                data=to_csv(df4),
                file_name="shopee_asins.csv",
                mime="text/csv"
            )

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#4a5568; font-size:0.75rem;'>Shopee Research Tool — For personal use only. Please respect Shopee's Terms of Service.</p>",
    unsafe_allow_html=True
)
