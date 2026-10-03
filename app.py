
import datetime
import math
import ephem
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st


# --- 月齢＆潮名計算関数 ---
def get_moon_phase(date_obj):
    if isinstance(date_obj, datetime.date) and not isinstance(
        date_obj, datetime.datetime
    ):
        date_obj = datetime.datetime.combine(date_obj, datetime.time(12, 0))

    ref_date = datetime.datetime(2000, 1, 6, 18, 14)
    diff = (date_obj - ref_date).total_seconds() / 86400.0
    synodic_month = 29.53058882
    age = diff % synodic_month
    phase_num = int((age / synodic_month) * 8) % 8 + 1
    return f"{phase_num}/8", float(age)


def get_tide_name(age):
    """月齢から潮名を判定"""
    if (0 <= age < 3.0) or (13.8 <= age < 17.8) or (28.5 <= age):
        return "大潮"
    elif (3.0 <= age < 6.8) or (17.8 <= age < 21.6):
        return "中潮"
    elif (6.8 <= age < 9.8) or (21.6 <= age < 24.6):
        return "小潮"
    elif (9.8 <= age < 10.8) or (24.6 <= age < 25.6):
        return "長潮"
    elif (10.8 <= age < 13.8) or (25.6 <= age < 28.5):
        return "若潮"
    return "中潮"


# --- 簡易潮汐計算関数 ---
def get_tide_series(date_obj, lon):
    d = ephem.Date(date_obj)
    prev_nm = ephem.previous_new_moon(d)
    m_age = d - prev_nm

    tide_heights = []
    for hour in range(24):
        lunar_hour = (hour + (lon / 15.0) - (m_age * 0.8)) % 12.42
        height = math.cos(2 * math.pi * lunar_hour / 12.42) * (
            100.0 + 50.0 * math.cos(2 * math.pi * m_age / 14.76)
        )
        tide_heights.append(round(height, 1))
    return tide_heights


def get_tide_times(date_obj, lon):
    tides = get_tide_series(date_obj, lon)
    high_tides = []
    low_tides = []

    for i in range(1, 23):
        if tides[i] > tides[i - 1] and tides[i] > tides[i + 1]:
            high_tides.append(f"{i:02d}:00")
        elif tides[i] < tides[i - 1] and tides[i] < tides[i + 1]:
            low_tides.append(f"{i:02d}:00")

    high_str = "/".join(high_tides) if high_tides else "--:--"
    low_str = "/".join(low_tides) if low_tides else "--:--"

    return high_str, low_str


# --- 角度から矢印への変換 ---
def degree_to_arrow(deg):
    if deg is None or pd.isna(deg):
        return "-"
    arrows = ["↓", "↙", "←", "↖", "↑", "↗", "→", "↘"]
    idx = int((deg + 22.5) / 45) % 8
    return arrows[idx]


# --- 天気コードを絵文字に変換 ---
def weather_code_to_icon(code):
    if code in [0]:
        return "☀️ 晴れ"
    elif code in [1, 2]:
        return "🌤 晴れ/時々曇り"
    elif code in [3]:
        return "☁ 曇り"
    elif code in [45, 48]:
        return "🌫️ 霧"
    elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
        return "☔ 雨"
    elif code in [95, 96, 99]:
        return "⚡ 雷雨"
    else:
        return "🌧 雨/その他"


# --- 直近の気温連動型・水温推計ロジック ---
def estimate_water_temp(daily_temp_max):
    """過去〜予報の平均気温から島根沿岸の水温を推計"""
    if not daily_temp_max:
        return None
    valid_temps = [t for t in daily_temp_max if t is not None]
    if not valid_temps:
        return None

    avg_temp = sum(valid_temps) / len(valid_temps)
    # 日本海沿岸（島根）の水温応答モデル（気温に対し緩やかに追従）
    estimated_temp = 12.0 + (avg_temp - 5.0) * 0.65
    return round(max(8.0, min(29.0, estimated_temp)), 1)


# --- APIから気象＆海洋データ取得 ---
def fetch_weather_and_marine_data(lat, lon):
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,temperature_2m_max,wind_speed_10m_max,wind_direction_10m_dominant&hourly=wind_speed_10m,wind_direction_10m&past_days=3&timezone=Asia%2FTokyo"
    weather_res = requests.get(weather_url).json()

    marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&daily=sea_water_temperature_max,wave_height_max&hourly=wave_height,wave_direction&timezone=Asia%2FTokyo"
    try:
        marine_res = requests.get(marine_url).json()
    except Exception:
        marine_res = {}

    return weather_res, marine_res


# --- 地名から緯度経度を取得 ---
def geocode_location(location_name):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={location_name}&count=1&language=ja&format=json"
    res = requests.get(url).json()
    if "results" in res and len(res["results"]) > 0:
        loc = res["results"][0]
        return loc["latitude"], loc["longitude"], loc.get("name", location_name)
    return None, None, None


# --- Streamlit UI 構築 ---
st.set_page_config(
    page_title="天気予報＆海況ダッシュボード", layout="wide", page_icon="🎣"
)

# サイドバー設定
st.sidebar.header("📍 参照位置の設定")

presets = {
    "出雲 (Izumo)": (35.36, 132.75),
    "猪目 (Inome)": (35.44, 132.71),
    "十六島 (Uppurui)": (35.46, 132.81),
    "鵜峠 (Udo)": (35.46, 132.75),
    "日御碕 (Hinomisaki)": (35.43, 132.63),
    "境港 (Sakaiminato)": (35.54, 133.23),
}

preset_choice = st.sidebar.selectbox("プリセットから選択", list(presets.keys()))
default_lat, default_lon = presets[preset_choice]

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 地名・スポット名で検索")
search_query = st.sidebar.text_input("地名を入力（例: 松江, 大社）")

if search_query:
    s_lat, s_lon, s_name = geocode_location(search_query)
    if s_lat is not None:
        lat, lon = s_lat, s_lon
        st.sidebar.success(f"「{s_name}」の位置を取得しました")
    else:
        st.sidebar.error("該当する場所が見つかりませんでした")
        lat, lon = default_lat, default_lon
else:
    lat, lon = default_lat, default_lon

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 座標直接調整")
lat = st.sidebar.number_input(
    "緯度 (Latitude)", value=float(lat), format="%.4f"
)
lon = st.sidebar.number_input(
    "経度 (Longitude)", value=float(lon), format="%.4f"
)


# --- メインコンテンツ ---
st.title("🎣 天気予報＆海況ダッシュボード")
st.caption(f"現在の参照位置: **{preset_choice}** (緯度: {lat:.4f}, 経度: {lon:.4f})")

# データ取得
w_data, m_data = fetch_weather_and_marine_data(lat, lon)

if "daily" in w_data and "hourly" in w_data:
    daily_w = w_data["daily"]
    daily_m = m_data.get("daily", {})

    all_dates = daily_w["time"]

    # 日本時間(JST)の今日の日付文字列を取得
    jst_now = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    )
    today_str = jst_now.strftime("%Y-%m-%d")

    # 本日以降の日付のみを正確にフィルタリングして先頭7日分を取得
    dates = [d for d in all_dates if d >= today_str][:7]

    # 実気温からの推定水温を算出
    est_water_temp = estimate_water_temp(daily_w.get("temperature_2m_max", []))

    # 上段：1週間の概況
    st.subheader("🗓️ 向こう1週間の概況")

    # スタイル指定：白背景＆視認性の高い文字色に明確に固定
    st.markdown(
        """<style>
.horizontal-scroll-container {
    display: flex;
    flex-direction: row;
    overflow-x: auto;
    gap: 12px;
    padding-bottom: 12px;
    -webkit-overflow-scrolling: touch;
}
.horizontal-scroll-container::-webkit-scrollbar {
    height: 6px;
}
.horizontal-scroll-container::-webkit-scrollbar-thumb {
    background-color: #888;
    border-radius: 3px;
}
.metric-card-scroll {
    min-width: 175px;
    max-width: 185px;
    flex: 0 0 auto;
    background-color: #ffffff !important;
    color: #222222 !important;
    border-radius: 12px;
    padding: 12px;
    border: 1px solid #dcdcdc;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.metric-card-scroll * {
    color: #222222;
}
</style>""",
        unsafe_allow_html=True,
    )

    cards_html = []
    for idx, date_str in enumerate(dates):
        orig_idx = all_dates.index(date_str)
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%m/%d (%a)")

        w_code = daily_w["weather_code"][orig_idx]
        w_icon = weather_code_to_icon(w_code)
        w_speed = round(daily_w["wind_speed_10m_max"][orig_idx] / 3.6, 1)
        w_deg = daily_w["wind_direction_10m_dominant"][orig_idx]
        w_arrow = degree_to_arrow(w_deg)

        water_temp_str = f"約{est_water_temp}℃ (推定)"
        if (
            "sea_water_temperature_max" in daily_m
            and daily_m["sea_water_temperature_max"] is not None
            and orig_idx < len(daily_m["sea_water_temperature_max"])
            and daily_m["sea_water_temperature_max"][orig_idx] is not None
        ):
            water_temp_str = (
                f"{round(daily_m['sea_water_temperature_max'][orig_idx], 1)}℃"
            )

        moon_8th, m_age = get_moon_phase(dt)
        tide_name = get_tide_name(m_age)
        high_tide, low_tide = get_tide_times(dt, lon)

        card = f'<div class="metric-card-scroll"><h4 style="margin:0; text-align:center; color:#0277bd !important; font-size:1.05em; font-weight:bold;">{display_date}</h4><p style="text-align:center; font-size:1em; margin:6px 0; color:#222222 !important;"><b>{w_icon}</b></p><hr style="margin:6px 0; border-color:#eee;"><p style="margin:4px 0; font-size:0.85em; color:#222222 !important;"><b>風:</b> <span style="color:#e65100 !important; font-weight:bold;">{w_arrow}</span> {w_speed} m/s</p><p style="margin:4px 0; font-size:0.85em; color:#222222 !important;">🌡 <b>水温:</b> {water_temp_str}</p><p style="margin:4px 0; font-size:0.85em; color:#222222 !important;">🌕 <b>月齢:</b> {moon_8th} <span style="background-color:#0288d1; color:#ffffff !important; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em;">{tide_name}</span></p><p style="margin:4px 0; font-size:0.82em; color:#c62828 !important;">🔺 <b>満潮:</b> {high_tide}</p><p style="margin:4px 0; font-size:0.82em; color:#1565c0 !important;">🔻 <b>干潮:</b> {low_tide}</p></div>'
        cards_html.append(card)

    scroll_html = f'<div class="horizontal-scroll-container">{"".join(cards_html)}</div>'
    st.markdown(scroll_html, unsafe_allow_html=True)

    st.divider()

    # 下段：選択日の時間軸グラフ
    st.subheader("📊 時間軸での詳細（風・潮位・波）")

    selected_date_str = st.selectbox(
        "確認したい日付を選択してください",
        dates,
        format_func=lambda x: datetime.datetime.strptime(
            x, "%Y-%m-%d"
        ).strftime("%m/%d (%a)"),
    )

    hourly_w = w_data["hourly"]
    hourly_m = m_data.get("hourly", {})

    wave_h_list = hourly_m.get("wave_height", [None] * len(hourly_w["time"]))
    wave_d_list = hourly_m.get(
        "wave_direction", [None] * len(hourly_w["time"])
    )

    df_hourly = pd.DataFrame(
        {
            "time": hourly_w["time"],
            "wind_speed": [
                round(s / 3.6, 1) for s in hourly_w["wind_speed_10m"]
            ],
            "wind_dir": hourly_w["wind_direction_10m"],
            "wave_height": wave_h_list,
            "wave_dir": wave_d_list,
        }
    )

    df_selected = df_hourly[
        df_hourly["time"].str.startswith(selected_date_str)
    ].copy()
    df_selected["hour"] = df_selected["time"].apply(lambda x: x.split("T")[1])
    df_selected["wind_arrow"] = df_selected["wind_dir"].apply(degree_to_arrow)

    # 波高がNullの場合の安全フォールバック（風速からの風浪推計）
    is_wave_estimated = False
    if df_selected["wave_height"].isnull().all():
        is_wave_estimated = True
        df_selected["wave_height"] = df_selected["wind_speed"].apply(
            lambda w: round(max(0.2, w * 0.12), 2)
        )
        df_selected["wave_arrow"] = df_selected["wind_arrow"]
    else:
        df_selected["wave_arrow"] = df_selected["wave_dir"].apply(
            degree_to_arrow
        )

    # 潮位データ計算
    sel_dt = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d")
    tide_data = get_tide_series(sel_dt, lon)
    df_selected["tide"] = tide_data

  # 風速＆潮位グラフ
    fig_wind = make_subplots(specs=[[{"secondary_y": True}]])

    fig_wind.add_trace(
        go.Scatter(
            x=df_selected["hour"],
            y=df_selected["wind_speed"],
            name="風速 (m/s)",
            line=dict(color="#2ca02c", width=3),
            mode="lines+markers",
        ),
        secondary_y=False,
    )

    fig_wind.add_trace(
        go.Scatter(
            x=df_selected["hour"],
            y=df_selected["tide"],
            name="潮位 (cm)",
            line=dict(color="#1f77b4", width=3, shape="spline"),
            mode="lines",
        ),
        secondary_y=True,
    )

    max_wind = (
        max(df_selected["wind_speed"])
        if max(df_selected["wind_speed"]) > 0
        else 5
    )
    for idx, row in df_selected.iterrows():
        fig_wind.add_annotation(
            x=row["hour"],
            y=max_wind * 1.1 + 0.3,
            text=row["wind_arrow"],
            showarrow=False,
            font=dict(size=16, color="#ff7f0e"),
            xref="x",
            yref="y1",
        )

    fig_wind.update_layout(
        title=dict(
            text=f"💨 {sel_dt.strftime('%m/%d')} の風速・潮位推移（上部矢印：風向）",
            x=0,
            xanchor="left",
            font=dict(size=14, color="#ffffff"),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cccccc"),
        xaxis_title="時刻",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.28,
            xanchor="center",
            x=0.5,
            font=dict(color="#ffffff"),
        ),
        margin=dict(l=10, r=10, t=50, b=80),
        height=420,
        # ダブルクリック時のリセット挙動を確実に設定
        uirevision=selected_date_str,
    )

    # 軸のレンジを毎回自動スケール（固定化を解除）
    fig_wind.update_xaxes(
        gridcolor="#333333", zerolinecolor="#333333", autorange=True
    )
    fig_wind.update_yaxes(
        title_text="風速 (m/s)",
        secondary_y=False,
        gridcolor="#333333",
        zerolinecolor="#333333",
        autorange=True,
    )
    fig_wind.update_yaxes(
        title_text="潮位 (相対cm)",
        secondary_y=True,
        showgrid=False,
        autorange=True,
    )

    # 日付ごとの一意なkeyを渡すことで、日付切替時にコンポーネントを完全再描画させる
    st.plotly_chart(
        fig_wind, use_container_width=True, key=f"wind_chart_{selected_date_str}"
    )

    # 波高＆波向グラフ
    fig_wave = go.Figure()

    fig_wave.add_trace(
        go.Bar(
            x=df_selected["hour"],
            y=df_selected["wave_height"],
            name="波高 (m)" if not is_wave_estimated else "波高 (推定 m)",
            marker_color="#17becf",
            opacity=0.85,
        )
    )

    max_wave = max(df_selected["wave_height"])
    if max_wave == 0:
        max_wave = 1.0

    for idx, row in df_selected.iterrows():
        fig_wave.add_annotation(
            x=row["hour"],
            y=max_wave * 1.1 + 0.1,
            text=row["wave_arrow"],
            showarrow=False,
            font=dict(size=16, color="#ff7f0e"),
            xref="x",
            yref="y",
        )

    title_wave = (
        f"🌊 {sel_dt.strftime('%m/%d')} の波高・波向推移（上部矢印：波向）"
    )
    if is_wave_estimated:
        title_wave += " ※風速からの推定表示"

    fig_wave.update_layout(
        title=dict(
            text=title_wave,
            x=0,
            xanchor="left",
            font=dict(size=14, color="#ffffff"),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cccccc"),
        xaxis_title="時刻",
        yaxis_title="波高 (m)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.28,
            xanchor="center",
            x=0.5,
            font=dict(color="#ffffff"),
        ),
        margin=dict(l=10, r=10, t=50, b=80),
        height=390,
        uirevision=selected_date_str,
    )

    fig_wave.update_xaxes(
        gridcolor="#333333", zerolinecolor="#333333", autorange=True
    )
    fig_wave.update_yaxes(
        gridcolor="#333333", zerolinecolor="#333333", autorange=True
    )

    st.plotly_chart(
        fig_wave, use_container_width=True, key=f"wave_chart_{selected_date_str}"
    )

else:
    st.error("データの取得に失敗しました。")
