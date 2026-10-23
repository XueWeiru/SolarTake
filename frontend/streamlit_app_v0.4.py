# -*- coding: utf-8 -*-
"""
太陽能板裝設評估 —— 前端（Streamlit）
======================================
前端只負責：輸入、呼叫外部資料服務、顯示結果、呼叫後端 LLM API。
LLM 的 prompt、金鑰、模型全部在後端（backend/app/services/llm_service.py）。

執行方式（需先啟動後端）：
    streamlit run frontend/streamlit_app.py
"""

import os
import re
import time
from datetime import datetime

import requests
import streamlit as st

# ---------------------------------------------------------------
# 基本設定
# ---------------------------------------------------------------

st.set_page_config(page_title="太陽能裝設評估", page_icon="☀️", layout="centered")

# 後端位址；你的 router 掛在 /api 底下，所以完整路徑是 /api/auth/login、/api/llm/report
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API = f"{BACKEND_URL}/api"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PVGIS_PVCALC_URL = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"

# 方位角換算表（PVGIS 慣例：0=正南，往西為正，往東為負，正北為 ±180）
ASPECT_MAP = {
    "南": 0, "西南": 45, "西": 90, "西北": 135,
    "北": 180, "東北": -135, "東": -90, "東南": -45,
}

for key, default in {
    "history": [], "geo": None, "sim": None,
    "token": None, "user": None, "report": None, "chat": [], "login_notice": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------
# 後端呼叫（登入 / LLM）
# ---------------------------------------------------------------

class AuthError(Exception):
    """後端回 401：token 失效或未登入"""


def login(email: str, password: str) -> str | None:
    """登入成功回傳 access_token，帳密錯誤回傳 None。連不上後端時丟出 RequestException。"""
    resp = requests.post(f"{API}/auth/login",
                         json={"email": email, "password": password}, timeout=10)
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None


def register(email: str, password: str, full_name: str = "") -> tuple[bool, str]:
    """註冊帳號。回傳 (是否成功, 失敗時的錯誤訊息)。連不上後端時丟出 RequestException。"""
    payload = {"email": email, "password": password}
    if full_name.strip():
        payload["full_name"] = full_name.strip()
    resp = requests.post(f"{API}/auth/register", json=payload, timeout=10)
    if resp.status_code in (200, 201):
        return True, ""
    try:
        detail = resp.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list):  # 422 驗證錯誤：把每個欄位的訊息串起來
        detail = "；".join(str(d.get("msg", "")) for d in detail)
    return False, detail or f"註冊失敗（HTTP {resp.status_code}）"


def fetch_me(token: str) -> dict | None:
    """取得目前登入者資料（需要後端有 GET /api/users/me）。失敗時回傳 None。"""
    resp = requests.get(f"{API}/users/me",
                        headers={"Authorization": f"Bearer {token}"}, timeout=10)
    return resp.json() if resp.status_code == 200 else None


def finish_login(token: str):
    """登入或註冊成功後的共同流程：存 token、抓使用者資料、重新整理畫面。"""
    st.session_state.token = token
    try:
        st.session_state.user = fetch_me(token)
    except requests.RequestException:
        st.session_state.user = None
    st.session_state.login_notice = None
    st.rerun()


def stream_from_backend(path: str, payload: dict):
    """呼叫後端串流端點，逐段 yield 文字，可直接餵給 st.write_stream。"""
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    with requests.post(f"{API}{path}", json=payload, headers=headers,
                       stream=True, timeout=90) as resp:
        if resp.status_code in (401, 403):
            raise AuthError()
        resp.raise_for_status()
        resp.encoding = "utf-8"
        for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                yield chunk


def to_payload(ctx: dict) -> dict:
    """只挑後端需要的欄位；回本年限為無限大時改送 None（JSON 不支援 inf）。"""
    keys = ["address", "aspect_name", "tilt_deg", "peak_power_kwp", "annual_kwh",
            "annual_loss_pct", "system_cost", "annual_saving"]
    payload = {k: ctx[k] for k in keys}
    pb = ctx["payback_years"]
    payload["payback_years"] = None if pb == float("inf") else pb
    return payload


def handle_auth_error():
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.login_notice = "登入已失效，請重新登入"
    st.rerun()


# ---------------------------------------------------------------
# 外部資料工具函式（地理編碼 / PVGIS / 財務試算）
# ---------------------------------------------------------------

def _swap_tai(text: str) -> str:
    """臺 / 台 互換（OSM 兩種寫法都有）"""
    return text.replace("臺", "台") if "臺" in text else text.replace("台", "臺")


def address_candidates(address: str) -> list[tuple[str, bool]]:
    """由精確到粗略產生查詢字串，回傳 [(查詢字串, 是否為約略位置)]。
    OSM 在台灣的門牌資料不完整，常見失敗原因：里名、「之1號」、樓層會讓搜尋找不到。"""
    a = re.sub(r"\s+", "", address)
    no_village = re.sub(r"(?<=[區鄉鎮市])[\u4e00-\u9fff]{1,3}[里村](?=[\u4e00-\u9fff0-9])", "", a)
    no_sub = re.sub(r"號.*$", "號", re.sub(r"之\d+(?=號)", "", no_village))
    road_only = re.sub(r"\d+號.*$", "", no_sub)

    ordered = [(a, False), (no_village, False), (no_sub, False), (road_only, True)]
    candidates, seen = [], set()
    for text, approx in ordered:
        for variant in (text, _swap_tai(text)):
            if len(variant) >= 4 and variant not in seen:
                seen.add(variant)
                candidates.append((variant, approx))
    return candidates


@st.cache_data(show_spinner=False, ttl=3600)
def geocode_address(address: str):
    """用 Nominatim 把地址轉成經緯度。找不到時依序嘗試簡化後的查詢（見 address_candidates）。
    Nominatim 規範：需帶 User-Agent，且每秒最多 1 次請求。"""
    headers = {"User-Agent": "solar-assessment-mvp/0.1 (demo)"}
    for i, (query, approx) in enumerate(address_candidates(address)):
        if i:
            time.sleep(1.1)
        params = {"q": query, "format": "json", "limit": 1, "countrycodes": "tw"}
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if results:
            r = results[0]
            return {
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "display_name": r["display_name"],
                "matched_query": query,
                # 查詢被簡化到道路層級，或回傳的是道路 / 行政區，都視為約略位置
                "approximate": approx or r.get("class") in ("highway", "boundary"),
            }
    return None


@st.cache_data(show_spinner=False, ttl=3600)
def get_pvgis_estimate(lat: float, lon: float, peak_power_kwp: float,
                       loss_pct: float, tilt_deg: float, aspect_deg: float):
    """呼叫 PVGIS PVcalc API，取得年/月發電量估算。"""
    params = {
        "lat": lat, "lon": lon, "peakpower": peak_power_kwp, "loss": loss_pct,
        "angle": tilt_deg, "aspect": aspect_deg, "outputformat": "json",
        "pvtechchoice": "crystSi", "mountingplace": "building",
    }
    resp = requests.get(PVGIS_PVCALC_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    totals = data["outputs"]["totals"]["fixed"]
    monthly = data["outputs"]["monthly"]["fixed"]
    return {
        "annual_kwh": totals["E_y"],
        "annual_loss_pct": totals["l_total"],
        "monthly_kwh": [m["E_m"] for m in monthly],
    }


def estimate_financials(annual_kwh: float, peak_power_kwp: float,
                        cost_per_kwp: float, price_per_kwh: float, subsidy: float):
    """簡化版投報試算：MVP 先抓量級。"""
    system_cost = peak_power_kwp * cost_per_kwp - subsidy
    annual_saving = annual_kwh * price_per_kwh
    payback_years = system_cost / annual_saving if annual_saving > 0 else float("inf")
    return {
        "system_cost": system_cost,
        "annual_saving": annual_saving,
        "payback_years": payback_years,
    }


# ---------------------------------------------------------------
# 介面：左側欄（登入 + 財務假設）
# ---------------------------------------------------------------

with st.sidebar:
    st.header("👤 登入")
    if st.session_state.token:
        user = st.session_state.user
        name = (user.get("full_name") or user.get("email")) if user else None
        st.success(f"歡迎，{name}" if name else "已登入")
        if st.button("登出", use_container_width=True):
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.report = None
            st.session_state.chat = []
            st.rerun()
    else:
        if st.session_state.login_notice:
            st.warning(st.session_state.login_notice)
        tab_login, tab_register = st.tabs(["登入", "註冊"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("密碼", type="password")
                submitted = st.form_submit_button("登入", use_container_width=True)
            if submitted:
                try:
                    token = login(email, password)
                except requests.RequestException as e:
                    st.error(f"無法連線到後端，請確認後端已啟動：{e}")
                    token = None
                else:
                    if token:
                        finish_login(token)
                    else:
                        st.error("帳號或密碼錯誤")

        with tab_register:
            with st.form("register_form"):
                reg_email = st.text_input("Email", key="reg_email")
                reg_name = st.text_input("姓名（選填）", key="reg_name")
                reg_password = st.text_input("密碼", type="password", key="reg_password")
                reg_confirm = st.text_input("再次輸入密碼", type="password", key="reg_confirm")
                reg_submitted = st.form_submit_button("建立帳號", use_container_width=True)
            if reg_submitted:
                if not reg_email.strip() or not reg_password:
                    st.warning("請填寫 Email 與密碼")
                elif reg_password != reg_confirm:
                    st.warning("兩次輸入的密碼不一致")
                else:
                    try:
                        ok, msg = register(reg_email.strip(), reg_password, reg_name)
                        if not ok:
                            st.error(msg)
                        else:
                            # 註冊成功後直接登入，省去使用者再輸入一次
                            token = login(reg_email.strip(), reg_password)
                            if token:
                                finish_login(token)
                            else:
                                st.success("註冊成功，請切換到「登入」分頁登入")
                    except requests.RequestException as e:
                        st.error(f"無法連線到後端，請確認後端已啟動：{e}")

        st.caption("登入後才能生成 AI 評估報告；其他評估功能不需要登入。")

    st.divider()
    st.subheader("財務假設")
    cost_per_kwp = st.number_input("每 kWp 造價（元）", value=35000, step=1000)
    price_per_kwh = st.number_input("每度電估算節省（元）", value=4.5, step=0.1)
    subsidy = st.number_input("補助金額（元，選填）", value=0, step=1000)

st.title("☀️ 太陽能板裝設評估")
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
            st.error("找不到這個地址（已自動嘗試去掉里名、之號、門牌的簡化查詢）。"
                     "OpenStreetMap 在台灣的門牌資料不完整，請改用下方「手動輸入座標」。")
        else:
            st.session_state.geo = geo
            st.session_state.sim = None      # 地址變了，清掉舊的評估與報告
            st.session_state.report = None
            st.session_state.chat = []

with st.expander("找不到地址？改用手動輸入座標"):
    st.caption("在 Google 地圖對目標屋頂按右鍵，第一行數字就是「緯度, 經度」，分別貼在下面。")
    mc1, mc2 = st.columns(2)
    man_lat = mc1.number_input("緯度", value=25.0330, format="%.6f", key="man_lat")
    man_lon = mc2.number_input("經度", value=121.5654, format="%.6f", key="man_lon")
    if st.button("使用這組座標", use_container_width=True):
        st.session_state.geo = {
            "lat": man_lat, "lon": man_lon,
            "display_name": f"手動輸入座標（{man_lat:.6f}, {man_lon:.6f}）",
            "approximate": False,
        }
        st.session_state.sim = None
        st.session_state.report = None
        st.session_state.chat = []

if st.session_state.geo:
    geo = st.session_state.geo
    st.success(f"定位成功：{geo['display_name']}")
    if geo.get("approximate"):
        st.warning("找不到精確門牌，目前是道路或區域的約略位置。日照試算仍可參考，"
                   "但建議用手動座標微調。")
    st.map({"lat": [geo["lat"]], "lon": [geo["lon"]]}, zoom=16)

# ---------------------------------------------------------------
# 步驟 2：屋頂資訊
# ---------------------------------------------------------------

if st.session_state.geo:
    st.subheader("2️⃣ 屋頂資訊（手動輸入）")

    col1, col2 = st.columns(2)
    with col1:
        roof_area = st.number_input("可用屋頂面積（平方公尺）", value=30.0, min_value=1.0, step=1.0)
        tilt_deg = st.slider("屋頂傾角（度）", 0, 60, 20)
    with col2:
        aspect_name = st.selectbox("屋頂朝向", list(ASPECT_MAP.keys()), index=0)
        loss_pct = st.slider("系統損耗估算（%）", 5, 30, 14,
                             help="含逆變器效率、線損、灰塵、溫度效應等，14% 是 PVGIS 常用預設值")

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
            st.session_state.report = None   # 新評估不要顯示舊報告
            st.session_state.chat = []
            st.session_state.history.append({
                "時間": datetime.now().strftime("%H:%M:%S"),
                "地址": address,
                "容量(kWp)": peak_power_kwp,
                "年發電量(度)": round(sim["annual_kwh"]),
                "回本年限": round(fin["payback_years"], 1),
            })

# ---------------------------------------------------------------
# 步驟 3、4：評估結果 + 後端 LLM 報告
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
    if not st.session_state.token:
        st.info("請先在左側欄登入，才能生成 AI 評估報告。")
    else:
        if st.button("🤖 生成 AI 評估報告", use_container_width=True):
            st.session_state.chat = []
            try:
                with st.container(border=True):
                    st.session_state.report = st.write_stream(
                        stream_from_backend("/llm/report", to_payload(ctx))
                    )
            except AuthError:
                handle_auth_error()
            except requests.RequestException as e:
                st.error(f"無法連線到後端：{e}")
        elif st.session_state.report:
            with st.container(border=True):
                st.markdown(st.session_state.report)

# ---------------------------------------------------------------
# 追問聊天（報告產生後才出現）
# ---------------------------------------------------------------

if st.session_state.sim and st.session_state.token and st.session_state.report:
    st.subheader("💬 追問")
    for m in st.session_state.chat:
        st.chat_message(m["role"]).write(m["content"])

    if q := st.chat_input("對報告有問題嗎？例如：台灣現行太陽能相關法律？"):
        st.session_state.chat.append({"role": "user", "content": q})
        st.chat_message("user").write(q)
        try:
            with st.chat_message("assistant"):
                answer = st.write_stream(stream_from_backend("/llm/chat", {
                    "ctx": to_payload(st.session_state.sim),
                    "messages": st.session_state.chat,
                }))
            st.session_state.chat.append({"role": "assistant", "content": answer})
        except AuthError:
            st.session_state.chat.pop()
            handle_auth_error()
        except requests.RequestException as e:
            st.session_state.chat.pop()
            st.error(f"無法連線到後端：{e}")

# ---------------------------------------------------------------
# 本次 session 的評估紀錄
# ---------------------------------------------------------------

if st.session_state.history:
    st.divider()
    st.subheader("📋 本次評估紀錄（僅存於本次瀏覽，重整頁面後消失）")
    st.dataframe(st.session_state.history, use_container_width=True, hide_index=True)
    st.caption("正式版會把這張表換成資料庫的 assessments 資料表，才能跨裝置、跨 session 查詢歷史紀錄。")
