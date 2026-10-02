import datetime
import math
import ephem
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st


# --- 月齢計算関数（標準計算方式） ---
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


# --- 簡易潮汐計算関数（24時間分の潮位グラフ用データの生成） ---
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


# --- 風向・波向角度（0〜360度）を矢印シンボルに変換 ---
def degree_to_arrow(deg):
    if deg is None or math.isnan(deg):
        return "-"
    arrows = ["↓", "↙", "←", "↖", "↑", "↗", "→", "↘"]
    idx = int((deg + 22.5) / 45) % 8
    return arrows[idx]


# --- 天気コード（WMO Code）を絵文字に変換 ---
def weather_code_to_icon(code):
    if code in [0]:
        return "☀️ 晴れ"
    elif code in [1, 2]:
        return "🌤️ 晴れ/時々曇り"
    elif code in [3]:
        return "☁️ 曇り"
    elif code in [45, 48]:
        return "🌫️ 霧"
    elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
        return "☔ 雨"
    elif code in [95, 96, 99]:
        return "⚡ 雷雨"
    else:
        return "🌧️ 雨/その他"


# --- Open-Meteo API から気象＆海洋データ取得 ---
def fetch_weather_and_marine_data(lat, lon):
    # 気象API
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,wind_speed_10m_max,wind_direction_10m_dominant&hourly=wind_speed_10m,wind_direction_10m&timezone=Asia%2FTokyo"
    # 海洋API（波高・波向・水温）
    marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&daily=sea_water_temperature_max,wave_height_max&hourly=wave_height,wave_direction&timezone=Asia%2FTokyo"

    weather_res = requests.get(weather_url).json()
    marine_res = requests.get(marine_url).json()

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
    dates = daily_w["time"]

    # 上段：1週間の概況
    st.subheader("🗓️ 向こう1週間の概況")
    cols = st.columns(len(dates))

    for idx, date_str in enumerate(dates):
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%m/%d")

        w_code = daily_w["weather_code"][idx]
        w_icon = weather_code_to_icon(w_code)
        w_speed = round(daily_w["wind_speed_10m_max"][idx] / 3.6, 1)
        w_deg = daily_w["wind_direction_10m_dominant"][idx]
        w_arrow = degree_to_arrow(w_deg)

        # 海洋データの安全な取得
        water_temp_str = "--"
        if (
            "sea_water_temperature_max" in daily_m
            and daily_m["sea_water_temperature_max"][idx] is not None
        ):
            water_temp_str = (
                f"{round(daily_m['sea_water_temperature_max'][idx], 1)}℃"
            )

        moon_8th, _ = get_moon_phase(dt)
        high_tide, low_tide = get_tide_times(dt, lon)

        with cols[idx]:
            st.markdown(f"### {display_date}")
            st.write(w_icon)
            st.write(f"**風:** {w_arrow} {w_speed} m/s")
            st.write(f"🌡️ **水温:** {water_temp_str}")
            st.write(f"**月齢:** {moon_8th}")
            st.write(f"🔺 **満潮:** {high_tide}")
            st.write(f"🔻 **干潮:** {low_tide}")

    st.divider()

    # 下段：選択日の時間軸グラフ
    st.subheader("📊 時間軸での詳細（風・潮位・波）")

    # 日付選択
    selected_date_str = st.selectbox(
        "確認したい日付を選択してください",
        dates,
        format_func=lambda x: datetime.datetime.strptime(
            x, "%Y-%m-%d"
        ).strftime("%m/%d (%a)"),
    )

    # 時間データのデータフレーム作成
    hourly_w = w_data["hourly"]
    hourly_m = m_data.get("hourly", {})

    df_hourly = pd.DataFrame(
        {
            "time": hourly_w["time"],
            "wind_speed": [
                round(s / 3.6, 1) for s in hourly_w["wind_speed_10m"]
            ],
            "wind_dir": hourly_w["wind_direction_10m"],
            "wave_height": hourly_m.get("wave_height", [None] * len(hourly_w["time"])),
            "wave_dir": hourly_m.get("wave_direction", [None] * len(hourly_w["time"])),
        }
    )

    # 選択日付でフィルタリング
    df_selected = df_hourly[
        df_hourly["time"].str.startswith(selected_date_str)
    ].copy()
    df_selected["hour"] = df_selected["time"].apply(lambda x: x.split("T")[1])
    df_selected["wind_arrow"] = df_selected["wind_dir"].apply(degree_to_arrow)
    df_selected["wave_arrow"] = df_selected["wave_dir"].apply(degree_to_arrow)

    # 潮位データの計算
    sel_dt = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d")
    tide_data = get_tide_series(sel_dt, lon)
    df_selected["tide"] = tide_data

    # --- 1. 風速＆潮位グラフ ---
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

    # 風向矢印の追加
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
            font=dict(size=14, color="#333333"),
            xref="x",
            yref="y1",
        )

    fig_wind.update_layout(
        title=f"💨 {sel_dt.strftime('%m/%d')} の風速・潮位推移（上部矢印：風向）",
        xaxis_title="時刻",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20),
        height=380,
    )
    fig_wind.update_yaxes(
        title_text="風速 (m/s)", secondary_y=False, gridcolor="#eee"
    )
    fig_wind.update_yaxes(
        title_text="潮位 (相対cm)", secondary_y=True, showgrid=False
    )

    st.plotly_chart(fig_wind, use_container_width=True)

    # --- 2. 波高＆波向グラフ（新規追加） ---
    fig_wave = go.Figure()

    fig_wave.add_trace(
        go.Bar(
            x=df_selected["hour"],
            y=df_selected["wave_height"],
            name="波高 (m)",
            marker_color="#17becf",
            opacity=0.85,
        )
    )

    # 波向矢印の追加
    max_wave = (
        df_selected["wave_height"].dropna().max()
        if not df_selected["wave_height"].dropna().empty
        else 1.0
    )
    if max_wave == 0:
        max_wave = 1.0

    for idx, row in df_selected.iterrows():
        if pd.notna(row["wave_height"]):
            fig_wave.add_annotation(
                x=row["hour"],
                y=max_wave * 1.1 + 0.1,
                text=row["wave_arrow"],
                showarrow=False,
                font=dict(size=14, color="#005580"),
                xref="x",
                yref="y",
            )

    fig_wave.update_layout(
        title=f"🌊 {sel_dt.strftime('%m/%d')} の波高・波向推移（上部矢印：波向）",
        xaxis_title="時刻",
        yaxis_title="波高 (m)",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=60, b=20),
        height=350,
    )
    fig_wave.update_yaxes(gridcolor="#eee")

    st.plotly_chart(fig_wave, use_container_width=True)

else:
    st.error("データの取得に失敗しました。")
