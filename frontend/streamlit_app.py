# -*- coding: utf-8 -*-
"""
太陽能板裝設評估推薦 App —— MVP 範例
======================================
對應先前規劃的「MVP 階梯」欄位：
    前端      → Streamlit（本檔案）
    地圖/座標 → Nominatim 地理編碼 + st.map
    後端      → 無獨立 FastAPI，運算邏輯直接寫在這裡
    背景任務  → 無 Celery/Redis，直接同步等待（運算僅需幾秒）
    資料庫    → 無 PostgreSQL，用 st.session_state 模擬本次 session 的評估紀錄
    日照模擬  → 直接呼叫 PVGIS 官方 PVcalc API（免費、無需金鑰），
               比自建 pvlib ModelChain 更省工，先驗證流程對不對再說
    LLM       → 呼叫 Anthropic API 生成白話報告；沒填金鑰時走「示範模式」樣板文字

執行方式：
    pip install -r requirements.txt
    streamlit run solar_mvp_app.py
"""

import time
from datetime import datetime

import requests
import streamlit as st

# ---------------------------------------------------------------
# 基本設定
# ---------------------------------------------------------------

st.set_page_config(page_title="太陽能裝設評估（MVP）", page_icon="☀️", layout="centered")
# Nominatim 地理編碼服務
# 歐盟委員會聯合研究中心（JRC) PVGIS
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search" 
PVGIS_PVCALC_URL = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"

# 方位角換算表（PVGIS 慣例：0=正南，往西為正，往東為負，正北為 ±180）
ASPECT_MAP = {
    "南": 0, "西南": 45, "西": 90, "西北": 135,
    "北": 180, "東北": -135, "東": -90, "東南": -45,
}

if "history" not in st.session_state:
    # 用記憶體模擬正式版的 BUILDINGS / SOLAR_SIMULATIONS 資料表
    st.session_state.history = []
if "geo" not in st.session_state:
    st.session_state.geo = None
if "sim" not in st.session_state:
    st.session_state.sim = None


# ---------------------------------------------------------------
# 工具函式
# ---------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def geocode_address(address: str):
    """用 Nominatim 把地址轉成經緯度（免費，但依使用規範需帶 User-Agent 且控制頻率）。"""
    headers = {"User-Agent": "solar-assessment-mvp/0.1 (demo)"}
    params = {"q": address, "format": "json", "limit": 1, "countrycodes": "tw"}
    resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    return {
        "lat": float(results[0]["lat"]),
        "lon": float(results[0]["lon"]),
        "display_name": results[0]["display_name"],
    }


@st.cache_data(show_spinner=False, ttl=3600)
def get_pvgis_estimate(lat: float, lon: float, peak_power_kwp: float,
                        loss_pct: float, tilt_deg: float, aspect_deg: float):
    """呼叫 PVGIS PVcalc API，取得年/月發電量估算（不用自己跑 pvlib ModelChain）。"""
    params = {
        "lat": lat,
        "lon": lon,
        "peakpower": peak_power_kwp,
        "loss": loss_pct,
        "angle": tilt_deg,
        "aspect": aspect_deg,
        "outputformat": "json",
        "pvtechchoice": "crystSi",
        "mountingplace": "building",
    }
    resp = requests.get(PVGIS_PVCALC_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    totals = data["outputs"]["totals"]["fixed"]
    monthly = data["outputs"]["monthly"]["fixed"]
    return {
        "annual_kwh": totals["E_y"],           # 年發電量 (kWh)
        "annual_loss_pct": totals["l_total"],  # 系統總損失 (%)
        "monthly_kwh": [m["E_m"] for m in monthly],
    }


def estimate_financials(annual_kwh: float, peak_power_kwp: float,
                         cost_per_kwp: float, price_per_kwh: float,
                         subsidy: float):
    """簡化版投報試算：不考慮電價逐年調整、躉購與自用混合等複雜情境，MVP 先抓量級。"""
    system_cost = peak_power_kwp * cost_per_kwp - subsidy
    annual_saving = annual_kwh * price_per_kwh
    payback_years = system_cost / annual_saving if annual_saving > 0 else float("inf")
    return {
        
        "system_cost": system_cost,
        "annual_saving": annual_saving,
        "payback_years": payback_years,
    }


def generate_report_demo_mode(ctx: dict) -> str:
    """沒有 LLM 金鑰時的樣板文字，讓流程在不花 API 費用的情況下也能展示。"""
    return (
        f"【示範模式報告，非 AI 生成】\n\n"
        f"根據輸入資料，此地點在裝設 {ctx['peak_power_kwp']:.1f} kWp 的太陽能系統後，"
        f"估算年發電量約 {ctx['annual_kwh']:.0f} 度電，系統總損失約 {ctx['annual_loss_pct']:.1f}%。\n"
        f"以目前輸入的電價與造價估算，簡易回本年限約 {ctx['payback_years']:.1f} 年。\n\n"
        f"提醒：以上為估算值，實際發電量會受屋頂遮蔭、面板衰減、饋線容量等因素影響，"
        f"僅供初步評估參考，正式規劃仍建議實地會勘。\n"
        f"（要看到 AI 生成的白話說明版本，請在左側欄填入 Anthropic API 金鑰。）"
    )


def generate_report_llm(ctx: dict, api_key: str) -> str:
    """呼叫 LLM 把運算數字轉成白話評估報告。正式版可在這裡接 RAG 檢索法規/補助。"""
    try:
        import anthropic
    except ImportError:
        return "尚未安裝 anthropic 套件，請先 `pip install anthropic`，或改用示範模式。"

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        "你是台灣住宅太陽能裝設評估顧問。請根據以下資料，用親切易懂的中文，"
        "寫一段給屋主看的評估說明（約200-300字），內容包含：這個屋頂裝太陽能划不划算、"
        "大致多久回本、需要注意什麼風險或限制。不要用條列式法規名稱，用白話說明即可，"
        "並清楚標示這是估算值而非保證值。\n\n"
        f"地址：{ctx['address']}\n"
        f"建議裝設容量：{ctx['peak_power_kwp']:.1f} kWp\n"
        f"屋頂朝向：{ctx['aspect_name']}，傾角：{ctx['tilt_deg']} 度\n"
        f"估算年發電量：{ctx['annual_kwh']:.0f} 度\n"
        f"系統總損失估算：{ctx['annual_loss_pct']:.1f}%\n"
        f"系統造價估算：{ctx['system_cost']:.0f} 元（已扣除輸入的補助金額）\n"
        f"每年估算節省電費：{ctx['annual_saving']:.0f} 元\n"
        f"簡易回本年限：{ctx['payback_years']:.1f} 年\n"
    )
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in message.content if hasattr(block, "text"))


# ---------------------------------------------------------------
# 介面：左側欄（設定）
# ---------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ 設定")
    api_key = st.text_input("Anthropic API 金鑰（選填）", type="password",
                             help="不填也能跑，會改用示範模式的樣板文字")
    st.caption("MVP 階段不需要金鑰也能看到完整流程；"
               "待填LLM金鑰生成白話報告。")
    st.divider()
    st.subheader("財務假設")
    cost_per_kwp = st.number_input("每 kWp 造價（元）", value=35000, step=1000)
    price_per_kwh = st.number_input("每度電估算節省（元）", value=4.5, step=0.1)
    subsidy = st.number_input("補助金額（元，選填）", value=0, step=1000)

st.title("☀️ 太陽能板裝設評估（MVP 範例）")
st.caption("輸入地址與屋頂資訊 → 抓日照資料估算發電量 → 生成評估報告")

# ---------------------------------------------------------------
# 步驟 1：地址 → 地理編碼
# ---------------------------------------------------------------

st.subheader("1️⃣ 輸入地址")
address = st.text_input("請輸入建物地址", placeholder="例如：台北市信義區市府路1號")

if st.button("定位地址", type="primary", use_container_width=True):
    if not address.strip():
        st.warning("請先輸入地址")
    else:
        with st.spinner("正在定位…"):
            try:
                geo = geocode_address(address)
            except requests.RequestException as e:
                st.error(f"定位失敗，請稍後再試：{e}")
                geo = None
        if geo is None:
            st.error("找不到這個地址，請試著輸入更完整的地址（含縣市、路名、門牌號）")
        else:
            st.session_state.geo = geo
            st.session_state.sim = None  # 地址變了，先清掉舊的評估結果

if st.session_state.geo:
    geo = st.session_state.geo
    st.success(f"定位成功：{geo['display_name']}")
    st.map({"lat": [geo["lat"]], "lon": [geo["lon"]]}, zoom=16)

# ---------------------------------------------------------------
# 步驟 2：屋頂資訊（MVP 先用手動輸入，取代 AI 屋頂辨識）
# ---------------------------------------------------------------

if st.session_state.geo:
    st.subheader("2️⃣ 屋頂資訊（手動輸入?google gps定位）")

    col1, col2 = st.columns(2)
    with col1:
        roof_area = st.number_input("可用屋頂面積（平方公尺）", value=30.0, min_value=1.0, step=1.0)
        tilt_deg = st.slider("屋頂傾角（度）", 0, 60, 20)
    with col2:
        aspect_name = st.selectbox("屋頂朝向", list(ASPECT_MAP.keys()), index=0)
        loss_pct = st.slider("系統損耗估算（%）", 5, 30, 14,
                              help="含逆變器效率、線損、灰塵、溫度效應等，14% 是 PVGIS 常用預設值")

    # 用「每平方公尺約可裝 0.2 kWp」的粗估把面積換算成建議容量，讓使用者可再手動調整
    suggested_kwp = round(roof_area * 0.2, 1)
    peak_power_kwp = st.number_input("建議裝設容量（kWp，可手動調整）",
                                      value=suggested_kwp, min_value=0.5, step=0.5)

    if st.button("🔍 開始評估", type="primary", use_container_width=True):
        with st.spinner("正在向 PVGIS 取得日照資料並試算…"):
            try:
                sim = get_pvgis_estimate(
                    lat=geo["lat"], lon=geo["lon"],
                    peak_power_kwp=peak_power_kwp, loss_pct=loss_pct,
                    tilt_deg=tilt_deg, aspect_deg=ASPECT_MAP[aspect_name],
                )
                fin = estimate_financials(
                    annual_kwh=sim["annual_kwh"], peak_power_kwp=peak_power_kwp,
                    cost_per_kwp=cost_per_kwp, price_per_kwh=price_per_kwh, subsidy=subsidy,
                )
            except requests.RequestException as e:
                st.error(f"PVGIS 資料取得失敗：{e}")
                sim, fin = None, None

        if sim and fin:
            ctx = {
                "address": address,
                "aspect_name": aspect_name,
                "tilt_deg": tilt_deg,
                "peak_power_kwp": peak_power_kwp,
                **sim,
                **fin,
            }
            st.session_state.sim = ctx
            st.session_state.history.append({
                "時間": datetime.now().strftime("%H:%M:%S"),
                "地址": address,
                "容量(kWp)": peak_power_kwp,
                "年發電量(度)": round(sim["annual_kwh"]),
                "回本年限": round(fin["payback_years"], 1),
            })

# ---------------------------------------------------------------
# 步驟 3：顯示結果 + LLM 報告
# ---------------------------------------------------------------

if st.session_state.sim:
    ctx = st.session_state.sim
    st.subheader("3️⃣ 評估結果")

    c1, c2, c3 = st.columns(3)
    c1.metric("年發電量估算", f"{ctx['annual_kwh']:.0f} 度")
    c2.metric("系統總損失", f"{ctx['annual_loss_pct']:.1f} %")
    c3.metric("簡易回本年限", f"{ctx['payback_years']:.1f} 年")

    st.bar_chart(
        {"月發電量 (kWh)": ctx["monthly_kwh"]},
        x_label="月份", y_label="kWh",
    )

    st.subheader("4️⃣ 評估報告")
    if api_key:
        with st.spinner("正在請 AI 生成白話報告…"):
            try:
                report = generate_report_llm(ctx, api_key)
            except Exception as e:
                report = f"LLM 呼叫失敗，改顯示示範模式報告。\n\n錯誤訊息：{e}\n\n" + \
                          generate_report_demo_mode(ctx)
    else:
        report = generate_report_demo_mode(ctx)
    st.info(report)

# ---------------------------------------------------------------
# 本次 session 的評估紀錄（模擬正式版資料庫的查詢紀錄表）
# ---------------------------------------------------------------

if st.session_state.history:
    st.divider()
    st.subheader("📋 本次評估紀錄（僅存於本次瀏覽，重整頁面後消失）")
    st.dataframe(st.session_state.history, use_container_width=True, hide_index=True)
    st.caption("正式版會把這張表換成 PostgreSQL + PostGIS 的 BUILDINGS / SOLAR_SIMULATIONS 資料表，"
               "才能跨裝置、跨 session 查詢歷史紀錄。")
