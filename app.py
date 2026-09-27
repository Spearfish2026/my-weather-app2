import datetime
import math
import re
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

    # 潮回り判定
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

# スマホ向け横スクロールCSSの挿入
st.markdown(
    """
    <style>
    .scroll-container {
        display: flex;
        overflow-x: auto;
        gap: 12px;
        padding-bottom: 12px;
        -webkit-overflow-scrolling: touch;
    }
    .scroll-card {
        min-width: 145px;
        max-width: 145px;
        flex: 0 0 auto;
        background-color: rgba(128, 128, 128, 0.12);
        border: 1px solid rgba(128, 128, 128, 0.3);
        border-radius: 10px;
        padding: 12px;
        font-size: 0.88rem;
    }
    .scroll-card h4 {
        margin: 0 0 8px 0;
        font-size: 1.05rem;
    }
    .scroll-card p {
        margin: 4px 0;
        line-height: 1.3;
    }
    </style>
""",
    unsafe_allow_html=True,
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
lat, lon = presets[preset_choice]
location_title = preset_choice

# 1. 地名・スポット検索
st.sidebar.markdown("---")
search_query = st.sidebar.text_input("🔍 地名・スポット名検索（例: 松江）")

if search_query:
    s_lat, s_lon, s_name = geocode_location(search_query)
    if s_lat is not None:
        lat, lon = s_lat, s_lon
        location_title = f"検索: {s_name}"
        st.sidebar.success(f"「{s_name}」を取得しました")
    else:
        st.sidebar.error("見つかりませんでした")

# 2. Google Map 座標貼り付け欄
st.sidebar.markdown("---")
map_coord_input = st.sidebar.text_input(
    "📌 Google Map座標ペースト",
    placeholder="35.6336, 133.1303",
    help="Google Maps等からコピーした「緯度, 経度」の文字列をそのまま貼り付けできます",
)

if map_coord_input:
    # 数値（小数含む）のペアを抽出
    coords = re.findall(r"[-+]?\d*\.\d+|\d+", map_coord_input)
    if len(coords) >= 2:
        try:
            parsed_lat = float(coords[0])
            parsed_lon = float(coords[1])
            lat, lon = parsed_lat, parsed_lon
            location_title = f"指定座標 ({lat:.4f}, {lon:.4f})"
            st.sidebar.success(
                f"座標を取得しました\n(Lat: {lat:.4f}, Lon: {lon:.4f})"
            )
        except ValueError:
            st.sidebar.error("座標の解析に失敗しました")
    else:
        st.sidebar.error("「緯度, 経度」の形式で入力してください")

# 3. 緯度・経度の個別数値入力欄
st.sidebar.markdown("---")
lat = st.sidebar.number_input("緯度 (Lat)", value=float(lat), format="%.6f")
lon = st.sidebar.number_input("経度 (Lon)", value=float(lon), format="%.6f")

# メインコンテンツ
st.title("🎣 天気予報＆海況ダッシュボード")
st.caption(
    f"現在の参照位置: **{location_title}** (緯度: {lat:.6f}, 経度: {lon:.6f})"
)

data = fetch_weather_data(lat, lon)

if "daily" in data and "hourly" in data:
    daily = data["daily"]
    dates = daily["time"]
    hourly = data["hourly"]

    df_hourly = pd.DataFrame(
        {
            "time": hourly["time"],
            "wind_speed": [round(s / 3.6, 1) for s in hourly["windspeed_10m"]],
            "wind_dir": hourly["winddirection_10m"],
        }
    )

    st.subheader("🗓️ 向こう1週間の概況（👉スワイプでスクロール）")

    # 横スワイプ（カード型）UIの構築
    cards_list = []
    for idx, date_str in enumerate(dates):
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%m/%d(%a)")

        w_code = daily["weathercode"][idx]
        w_icon = weather_code_to_icon(w_code)

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

        card_html = (
            f'<div class="scroll-card">'
            f"<h4>{display_date}</h4>"
            f"<p>{w_icon}</p>"
            f"<p><b>風:</b> {w_arrow} {w_speed}m/s</p>"
            f"<p><b>月:</b> {mega_moon} {emoji}</p>"
            f"<p><b>潮:</b> {tide_name}</p>"
            f'<p style="color: #ff4b4b; margin-top:6px;">🔺 {high_tide}</p>'
            f'<p style="color: #1c83e1;">🔻 {low_tide}</p>'
            f"</div>"
        )
        cards_list.append(card_html)

    full_html = (
        '<div class="scroll-container">' + "".join(cards_list) + "</div>"
    )
    st.markdown(full_html, unsafe_allow_html=True)

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

    sel_dt = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d")

    # グラフ上部用タイトル
    st.markdown(f"**{sel_dt.strftime('%m/%d')} 風速・潮位推移（上部: 風向）**")

    df_selected = df_hourly[
        df_hourly["time"].str.startswith(selected_date_str)
    ].copy()
    df_selected["hour"] = df_selected["time"].apply(lambda x: x.split("T")[1])
    df_selected["arrow"] = df_selected["wind_dir"].apply(wind_degree_to_arrow)

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

    # 風向矢印（高コントラスト黄色）
    max_wind = (
        max(df_selected["wind_speed"])
        if max(df_selected["wind_speed"]) > 0
        else 5
    )
    arrow_y = max_wind * 1.15 + 0.3

    for idx_r, row in df_selected.iterrows():
        fig.add_annotation(
            x=row["hour"],
            y=arrow_y,
            text=f"<b>{row['arrow']}</b>",
            showarrow=False,
            font=dict(size=13, color="#FFD700"),
            xref="x",
            yref="y1",
        )

    # レイアウト設定
    fig.update_layout(
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.12, xanchor="right", x=1
        ),
        margin=dict(l=10, r=10, t=40, b=10),
        height=380,
    )

    # 軸の設定
    fig.update_xaxes(
        title_text="時刻",
        fixedrange=True,
        gridcolor="rgba(128,128,128,0.2)",
    )
    fig.update_yaxes(
        title_text="風速(m/s)",
        secondary_y=False,
        fixedrange=True,
        range=[0, max_wind * 1.35],
        gridcolor="rgba(128,128,128,0.2)",
    )
    fig.update_yaxes(
        title_text="潮位(cm)", secondary_y=True, fixedrange=True, showgrid=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "scrollZoom": False,
            "doubleClick": "reset",
        },
    )

else:
    st.error("データの取得に失敗しました。")
