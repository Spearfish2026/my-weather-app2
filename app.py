import datetime
import math
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st


# --- 月齢・月相絵文字・潮回り計算関数 ---
def get_moon_phase_and_tide_name(date_obj):
    if isinstance(date_obj, datetime.date) and not isinstance(
        date_obj, datetime.datetime
    ):
        date_obj = datetime.datetime.combine(date_obj, datetime.time(12, 0))

    ref_date = datetime.datetime(2000, 1, 6, 18, 14)
    diff = (date_obj - ref_date).total_seconds() / 86400.0
    synodic_month = 29.53058882
    age = diff % synodic_month

    # メガテン方式（1/8〜8/8）
    phase_num = int((age / synodic_month) * 8) % 8 + 1
    mega_str = f"{phase_num}/8"

    # 月の絵文字
    emojis = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]
    emoji = emojis[int((age / synodic_month) * 8) % 8]

    # 潮回り判定（月齢ベースの目安）
    a = round(age, 1)
    if (a >= 28.5 or a < 2.5) or (13.8 <= a < 17.5):
        tide_name = "大潮"
    elif (2.5 <= a < 6.5) or (11.5 <= a < 13.8) or (17.5 <= a < 21.5) or (26.5 <= a < 28.5):
        tide_name = "中潮"
    elif (6.5 <= a < 9.5) or (21.5 <= a < 24.5):
        tide_name = "小潮"
    elif (9.5 <= a < 10.5) or (24.5 <= a < 25.5):
        tide_name = "長潮"
    else:
        tide_name = "若潮"

    return mega_str, emoji, tide_name, float(age)


# --- 簡易潮汐計算 ---
def get_tide_series(date_obj, lon):
    if isinstance(date_obj, datetime.date) and not isinstance(
        date_obj, datetime.datetime
    ):
        date_obj = datetime.datetime.combine(date_obj, datetime.time(12, 0))

    ref_date = datetime.datetime(2000, 1, 6, 18, 14)
    diff = (date_obj - ref_date).total_seconds() / 86400.0
    m_age = diff % 29.53058882

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


def wind_degree_to_arrow(deg):
    arrows = ["↓", "↙", "←", "↖", "↑", "↗", "→", "↘"]
    idx = int((deg + 22.5) / 45) % 8
    return arrows[idx]


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
        return "🌧️ 雨"


def fetch_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weathercode&hourly=windspeed_10m,winddirection_10m&timezone=Asia%2FTokyo"
    res = requests.get(url)
    return res.json()


def geocode_location(location_name):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={location_name}&count=1&language=ja&format=json"
    res = requests.get(url).json()
    if "results" in res and len(res["results"]) > 0:
        loc = res["results"][0]
        return loc["latitude"], loc["longitude"], loc.get("name", location_name)
    return None, None, None


# --- Streamlit UI 設定 ---
st.set_page_config(
    page_title="天気予報＆海況ダッシュボード", layout="wide", page_icon="🎣"
)

# サイドバー設定
st.sidebar.header("📍 参照位置の設定")
presets = {
    "出雲 (Izumo)": (35.36, 132.75),
    "猪目 (Inome)": (35.44, 132.71),
    "鵜峠 (Udo)": (35.46, 132.75),
    "日御碕 (Hinomisaki)": (35.43, 132.63),
    "境港 (Sakaiminato)": (35.54, 133.23),
}

preset_choice = st.sidebar.selectbox("プリセットから選択", list(presets.keys()))
default_lat, default_lon = presets[preset_choice]

st.sidebar.markdown("---")
search_query = st.sidebar.text_input("🔍 地名・スポット名検索（例: 松江）")

if search_query:
    s_lat, s_lon, s_name = geocode_location(search_query)
    if s_lat is not None:
        lat, lon = s_lat, s_lon
        st.sidebar.success(f"「{s_name}」を取得しました")
    else:
        st.sidebar.error("見つかりませんでした")
        lat, lon = default_lat, default_lon
else:
    lat, lon = default_lat, default_lon

st.sidebar.markdown("---")
lat = st.sidebar.number_input("緯度 (Lat)", value=float(lat), format="%.4f")
lon = st.sidebar.number_input("経度 (Lon)", value=float(lon), format="%.4f")

# メインコンテンツ
st.title("🎣 天気予報＆海況ダッシュボード")
st.caption(f"現在の参照位置: **{preset_choice}** (緯度: {lat:.4f}, 経度: {lon:.4f})")

data = fetch_weather_data(lat, lon)

if "daily" in data and "hourly" in data:
    daily = data["daily"]
    dates = daily["time"]
    hourly = data["hourly"]

    # 時間データからデータフレームを作成
    df_hourly = pd.DataFrame(
        {
            "time": hourly["time"],
            "wind_speed": [round(s / 3.6, 1) for s in hourly["windspeed_10m"]],
            "wind_dir": hourly["winddirection_10m"],
        }
    )

    st.subheader("🗓️ 向こう1週間の概況（👈左右スワイプでスクロール）")

    # 横スクロールコンテナ用CSS
    scroll_html = """
    <style>
    .scroll-container {
        display: flex;
        overflow-x: auto;
        gap: 12px;
        padding-bottom: 12px;
        -webkit-overflow-scrolling: touch;
    }
    .card {
        min-width: 150px;
        max-width: 150px;
        background-color: rgba(128, 128, 128, 0.15);
        border-radius: 10px;
        padding: 12px;
        border: 1px solid rgba(128, 128, 128, 0.3);
        flex-shrink: 0;
    }
    .card h4 { margin: 0 0 8px 0; font-size: 1.1rem; }
    .card p { margin: 4px 0; font-size: 0.85rem; line-height: 1.3; }
    </style>
    <div class="scroll-container">
    """

    for idx, date_str in enumerate(dates):
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%m/%d(%a)")

        w_code = daily["weathercode"][idx]
        w_icon = weather_code_to_icon(w_code)

        # 該当日の平均/最大風速を算出
        df_day = df_hourly[df_hourly["time"].str.startswith(date_str)]
        if not df_day.empty:
            w_speed = df_day["wind_speed"].max()
            w_deg = df_day["wind_dir"].mean()
            w_arrow = wind_degree_to_arrow(w_deg)
        else:
            w_speed = 0.0
            w_arrow = "↑"

        mega_moon, emoji, tide_name, _ = get_moon_phase_and_tide_name(dt)
        high_tide, low_tide = get_tide_times(dt, lon)

        scroll_html += f"""
        <div class="card">
            <h4>{display_date}</h4>
            <p>{w_icon}</p>
            <p><b>風:</b> {w_arrow} {w_speed}m/s</p>
            <p><b>月:</b> {mega_moon} {emoji}</p>
            <p><b>潮:</b> {tide_name}</p>
            <p style="color: #ff4b4b; margin-top:6px;">🔺 {high_tide}</p>
            <p style="color: #1c83e1;">🔻 {low_tide}</p>
        </div>
        """

    scroll_html += "</div>"
    st.markdown(scroll_html, unsafe_allow_html=True)

    st.divider()

    # 下段：時間軸グラフ
    st.subheader("📊 時間軸での詳細（風速・風向・潮位）")

    selected_date_str = st.selectbox(
        "日付を選択してください",
        dates,
        format_func=lambda x: datetime.datetime.strptime(
            x, "%Y-%m-%d"
        ).strftime("%m/%d (%a)"),
    )

    df_selected = df_hourly[
        df_hourly["time"].str.startswith(selected_date_str)
    ].copy()
    df_selected["hour"] = df_selected["time"].apply(lambda x: x.split("T")[1])
    df_selected["arrow"] = df_selected["wind_dir"].apply(wind_degree_to_arrow)

    sel_dt = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d")
    tide_data = get_tide_series(sel_dt, lon)
    df_selected["tide"] = tide_data

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 風速
    fig.add_trace(
        go.Scatter(
            x=df_selected["hour"],
            y=df_selected["wind_speed"],
            name="風速 (m/s)",
            line=dict(color="#2ca02c", width=2.5),
            mode="lines+markers",
        ),
        secondary_y=False,
    )

    # 潮位
    fig.add_trace(
        go.Scatter(
            x=df_selected["hour"],
            y=df_selected["tide"],
            name="潮位 (cm)",
            line=dict(color="#1f77b4", width=2.5, shape="spline"),
            mode="lines",
        ),
        secondary_y=True,
    )

    # 風向矢印（ダーク/ライト両対応の高コントラスト色：黄色 #FFD700）
    max_wind = (
        max(df_selected["wind_speed"])
        if max(df_selected["wind_speed"]) > 0
        else 5
    )
    for idx, row in df_selected.iterrows():
        fig.add_annotation(
            x=row["hour"],
            y=max_wind * 1.1 + 0.2,
            text=f"<b>{row['arrow']}</b>",
            showarrow=False,
            font=dict(size=14, color="#FFD700"),
            xref="x",
            yref="y1",
        )

    fig.update_layout(
        title=dict(
            text=f"{sel_dt.strftime('%m/%d')} 風速・潮位推移（上部: 風向）",
            font=dict(size=14),
        ),
        xaxis_title="時刻",
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
        margin=dict(l=5, r=5, t=50, b=10),
        height=380,
    )

    fig.update_yaxes(
        title_text="風速(m/s)", secondary_y=False, gridcolor="rgba(128,128,128,0.2)"
    )
    fig.update_yaxes(title_text="潮位(cm)", secondary_y=True, showgrid=False)

    st.plotly_chart(
        fig, use_container_width=True, config={"displayModeBar": False}
    )

else:
    st.error("データの取得に失敗しました。")
