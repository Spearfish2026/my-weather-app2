import datetime
import math
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st


# --- 月齢計算関数（標準計算方式・外部ライブラリ不使用） ---
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


# --- 風向角度（0〜360度）を矢印シンボルに変換 ---
def wind_degree_to_arrow(deg):
    arrows = ["↓", "↙", "←", "↖", "↑", "↗", "→", "↘"]
    idx = int((deg + 22.5) / 45) % 8
    return arrows[idx]


# --- 天気コード（WMO Code）を絵文字に変換 ---
def weather_code_to_icon(code):
    if code in [0]:
        return "☀️ 晴れ"
    elif code in [1, 2]:
        return "🌤️ 晴れ/晴れ時々曇り"
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


# --- Open-Meteo API からデータ取得 ---
def fetch_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,wind_speed_10m_max,wind_direction_10m_dominant&hourly=wind_speed_10m,wind_direction_10m&timezone=Asia%2FTokyo"
    res = requests.get(url)
    return res.json()


# --- 地名から緯度経度を取得（Open-Meteo Geocoding） ---
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

# メインコンテンツ
st.title("🎣 天気予報＆海況ダッシュボード")
st.caption(f"現在の参照位置: **{preset_choice}** (緯度: {lat:.4f}, 経度: {lon:.4f})")

data = fetch_weather_data(lat, lon)

if "daily" in data and "hourly" in data:
    daily = data["daily"]
    dates = daily["time"]

    # 上段：1週間の概況
    st.subheader("🗓️ 向こう1週間の概況")
    cols = st.columns(len(dates))

    for idx, date_str in enumerate(dates):
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%m/%d")

        w_code = daily["weather_code"][idx]
        w_icon = weather_code_to_icon(w_code)
        w_speed = round(daily["wind_speed_10m_max"][idx] / 3.6, 1)
        w_deg = daily["wind_direction_10m_dominant"][idx]
        w_arrow = wind_degree_to_arrow(w_deg)

        moon_8th, _ = get_moon_phase(dt)
        high_tide, low_tide = get_tide_times(dt, lon)

        with cols[idx]:
            st.markdown(f"### {display_date}")
            st.write(w_icon)
            st.write(f"**風:** {w_arrow} {w_speed} m/s")
            st.write(f"**月齢:** {moon_8th}")
            st.write(f"🔺 **満潮:** {high_tide}")
            st.write(f"🔻 **干潮:** {low_tide}")

    st.divider()

    # 下段：選択日の時間軸グラフ
    st.subheader("📊 時間軸での詳細（風速・風向・潮位）")

    selected_date_str = st.selectbox(
        "確認したい日付を選択してください",
        dates,
        format_func=lambda x: datetime.datetime.strptime(
            x, "%Y-%m-%d"
        ).strftime("%m/%d (%a)"),
    )

    hourly = data["hourly"]
    df_hourly = pd.DataFrame(
        {
            "time": hourly["time"],
            "wind_speed": [round(s / 3.6, 1) for s in hourly["wind_speed_10m"]],
            "wind_dir": hourly["wind_direction_10m"],
        }
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

    fig.add_trace(
        go.Scatter(
            x=df_selected["hour"],
            y=df_selected["wind_speed"],
            name="風速 (m/s)",
            line=dict(color="#2ca02c", width=3),
            mode="lines+markers",
        ),
        secondary_y=False,import datetime
import math
import ephem
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st


# --- 月齢計算関数 ---
def get_moon_phase(date_obj):
    d = ephem.Date(date_obj)
    prev_new_moon = ephem.previous_new_moon(d)
    age = d - prev_new_moon
    phase_num = int((age / 29.530588) * 8) % 8 + 1
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


# --- 風向角度（0〜360度）を矢印シンボルに変換 ---
def wind_degree_to_arrow(deg):
    arrows = ["↓", "↙", "←", "↖", "↑", "↗", "→", "↘"]
    idx = int((deg + 22.5) / 45) % 8
    return arrows[idx]


# --- 天気コード（WMO Code）を絵文字に変換 ---
def weather_code_to_icon(code):
    if code in [0]:
        return "☀️ 晴れ"
    elif code in [1, 2]:
        return "🌤️ 晴れ/晴れ時々曇り"
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


# --- Open-Meteo API からデータ取得 ---
def fetch_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,wind_speed_10m_max,wind_direction_10m_dominant&hourly=wind_speed_10m,wind_direction_10m&timezone=Asia%2FTokyo"
    res = requests.get(url)
    return res.json()


# --- 地名から緯度経度を取得（Open-Meteo Geocoding） ---
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

# プリセットポイント
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

# 緯度経度直接調整
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
data = fetch_weather_data(lat, lon)

if "daily" in data and "hourly" in data:
    daily = data["daily"]
    dates = daily["time"]

    # 上段：1週間の概況
    st.subheader("🗓️ 向こう1週間の概況")
    cols = st.columns(len(dates))

    for idx, date_str in enumerate(dates):
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%m/%d")

        w_code = daily["weather_code"][idx]
        w_icon = weather_code_to_icon(w_code)
        w_speed = round(daily["wind_speed_10m_max"][idx] / 3.6, 1)
        w_deg = daily["wind_direction_10m_dominant"][idx]
        w_arrow = wind_degree_to_arrow(w_deg)

        moon_8th, _ = get_moon_phase(dt)
        high_tide, low_tide = get_tide_times(dt, lon)

        with cols[idx]:
            st.markdown(f"### {display_date}")
            st.write(w_icon)
            st.write(f"**風:** {w_arrow} {w_speed} m/s")
            st.write(f"**月齢:** {moon_8th}")
            st.write(f"🔺 **満潮:** {high_tide}")
            st.write(f"🔻 **干潮:** {low_tide}")

    st.divider()

    # 下段：選択日の時間軸グラフ（風速＆潮位）
    st.subheader("📊 時間軸での詳細（風速・風向・潮位）")

    # 日付選択
    selected_date_str = st.selectbox(
        "確認したい日付を選択してください",
        dates,
        format_func=lambda x: datetime.datetime.strptime(
            x, "%Y-%m-%d"
        ).strftime("%m/%d (%a)"),
    )

    # 選択日付の時間データを抽出
    hourly = data["hourly"]
    df_hourly = pd.DataFrame(
        {
            "time": hourly["time"],
            "wind_speed": [
                round(s / 3.6, 1) for s in hourly["wind_speed_10m"]
            ],  # m/s
            "wind_dir": hourly["wind_direction_10m"],
        }
    )

    # 選択した日付でフィルタリング
    df_selected = df_hourly[
        df_hourly["time"].str.startswith(selected_date_str)
    ].copy()
    df_selected["hour"] = df_selected["time"].apply(lambda x: x.split("T")[1])
    df_selected["arrow"] = df_selected["wind_dir"].apply(wind_degree_to_arrow)

    # 潮位データの計算import datetime
import math
import ephem
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st


# --- 月齢計算関数 ---
def get_moon_phase(date_obj):
    d = ephem.Date(date_obj)
    prev_new_moon = ephem.previous_new_moon(d)
    age = d - prev_new_moon
    phase_num = int((age / 29.530588) * 8) % 8 + 1
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


# --- 風向角度（0〜360度）を矢印シンボルに変換 ---
def wind_degree_to_arrow(deg):
    arrows = ["↓", "↙", "←", "↖", "↑", "↗", "→", "↘"]
    idx = int((deg + 22.5) / 45) % 8
    return arrows[idx]


# --- 天気コード（WMO Code）を絵文字に変換 ---
def weather_code_to_icon(code):
    if code in [0]:
        return "☀️ 晴れ"
    elif code in [1, 2]:
        return "🌤️ 晴れ/晴れ時々曇り"
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


# --- Open-Meteo API からデータ取得 ---
def fetch_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,wind_speed_10m_max,wind_direction_10m_dominant&hourly=wind_speed_10m,wind_direction_10m&timezone=Asia%2FTokyo"
    res = requests.get(url)
    return res.json()


# --- 地名から緯度経度を取得（Open-Meteo Geocoding） ---
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

# プリセットポイント
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

# 緯度経度直接調整
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
data = fetch_weather_data(lat, lon)

if "daily" in data and "hourly" in data:
    daily = data["daily"]
    dates = daily["time"]

    # 上段：1週間の概況
    st.subheader("🗓️ 向こう1週間の概況")
    cols = st.columns(len(dates))

    for idx, date_str in enumerate(dates):
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%m/%d")

        w_code = daily["weather_code"][idx]
        w_icon = weather_code_to_icon(w_code)
        w_speed = round(daily["wind_speed_10m_max"][idx] / 3.6, 1)
        w_deg = daily["wind_direction_10m_dominant"][idx]
        w_arrow = wind_degree_to_arrow(w_deg)

        moon_8th, _ = get_moon_phase(dt)
        high_tide, low_tide = get_tide_times(dt, lon)

        with cols[idx]:
            st.markdown(f"### {display_date}")
            st.write(w_icon)
            st.write(f"**風:** {w_arrow} {w_speed} m/s")
            st.write(f"**月齢:** {moon_8th}")
            st.write(f"🔺 **満潮:** {high_tide}")
            st.write(f"🔻 **干潮:** {low_tide}")

    st.divider()

    # 下段：選択日の時間軸グラフ（風速＆潮位）
    st.subheader("📊 時間軸での詳細（風速・風向・潮位）")

    # 日付選択
    selected_date_str = st.selectbox(
        "確認したい日付を選択してください",
        dates,
        format_func=lambda x: datetime.datetime.strptime(
            x, "%Y-%m-%d"
        ).strftime("%m/%d (%a)"),
    )

    # 選択日付の時間データを抽出
    hourly = data["hourly"]
    df_hourly = pd.DataFrame(
        {
            "time": hourly["time"],
            "wind_speed": [
                round(s / 3.6, 1) for s in hourly["wind_speed_10m"]
            ],  # m/s
            "wind_dir": hourly["wind_direction_10m"],
        }
    )

    # 選択した日付でフィルタリング
    df_selected = df_hourly[
        df_hourly["time"].str.startswith(selected_date_str)
    ].copy()
    df_selected["hour"] = df_selected["time"].apply(lambda x: x.split("T")[1])
    df_selected["arrow"] = df_selected["wind_dir"].apply(wind_degree_to_arrow)

    # 潮位データの計算
    sel_dt = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d")
    tide_data = get_tide_series(sel_dt, lon)
    df_selected["tide"] = tide_data

    # --- Plotlyによる2軸グラフ描画 ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 風速（緑色の線）
    fig.add_trace(
        go.Scatter(
            x=df_selected["hour"],
            y=df_selected["wind_speed"],
            name="風速 (m/s)",
            line=dict(color="#2ca02c", width=3),
            mode="lines+markers",
        ),
        secondary_y=False,
    )

    # 潮位（青色の線）
    fig.add_trace(
        go.Scatter(
            x=df_selected["hour"],
            y=df_selected["tide"],
            name="潮位 (cm)",
            line=dict(color="#1f77b4", width=3, shape="spline"),
            mode="lines",
        ),
        secondary_y=True,
    )

    # 風向矢印の注釈をグラフ上部に追加
    max_wind = (
        max(df_selected["wind_speed"])
        if max(df_selected["wind_speed"]) > 0
        else 5
    )
    for idx, row in df_selected.iterrows():
        fig.add_annotation(
            x=row["hour"],
            y=max_wind * 1.1 + 0.3,
            text=row["arrow"],
            showarrow=False,
            font=dict(size=14, color="#333333"),
            xref="x",
            yref="y1",
        )

    # 軸・レイアウトの設定
    fig.update_layout(
        title=f"{sel_dt.strftime('%m/%d')} の風速・潮位推移（上部矢印：風向）",
        xaxis_title="時刻",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20),
        height=400,
    )

    fig.update_yaxes(title_text="風速 (m/s)", secondary_y=False, gridcolor="#eee")
    fig.update_yaxes(
        title_text="潮位 (相対cm)", secondary_y=True, showgrid=False
    )

    # Streamlitにグラフ表示
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("データの取得に失敗しました。")
    sel_dt = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d")
    tide_data = get_tide_series(sel_dt, lon)
    df_selected["tide"] = tide_data

    # --- Plotlyによる2軸グラフ描画 ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 風速（緑色の線）
    fig.add_trace(
        go.Scatter(
            x=df_selected["hour"],
            y=df_selected["wind_speed"],
            name="風速 (m/s)",
            line=dict(color="#2ca02c", width=3),
            mode="lines+markers",
        ),
        secondary_y=False,
    )

    # 潮位（青色の線）
    fig.add_trace(
        go.Scatter(
            x=df_selected["hour"],
            y=df_selected["tide"],
            name="潮位 (cm)",
            line=dict(color="#1f77b4", width=3, shape="spline"),
            mode="lines",
        ),
        secondary_y=True,
    )

    # 風向矢印の注釈をグラフ上部に追加
    max_wind = (
        max(df_selected["wind_speed"])
        if max(df_selected["wind_speed"]) > 0
        else 5
    )
    for idx, row in df_selected.iterrows():
        fig.add_annotation(
            x=row["hour"],
            y=max_wind * 1.1 + 0.3,
            text=row["arrow"],
            showarrow=False,
            font=dict(size=14, color="#333333"),
            xref="x",
            yref="y1",
        )

    # 軸・レイアウトの設定
    fig.update_layout(
        title=f"{sel_dt.strftime('%m/%d')} の風速・潮位推移（上部矢印：風向）",
        xaxis_title="時刻",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20),
        height=400,
    )

    fig.update_yaxes(title_text="風速 (m/s)", secondary_y=False, gridcolor="#eee")
    fig.update_yaxes(
        title_text="潮位 (相対cm)", secondary_y=True, showgrid=False
    )

    # Streamlitにグラフ表示
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("データの取得に失敗しました。")
    )

    fig.add_trace(
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
        fig.add_annotation(
            x=row["hour"],
            y=max_wind * 1.1 + 0.3,
            text=row["arrow"],
            showarrow=False,
            font=dict(size=14, color="#333333"),
            xref="x",
            yref="y1",
        )

    fig.update_layout(
        title=f"{sel_dt.strftime('%m/%d')} の風速・潮位推移（上部矢印：風向）",
        xaxis_title="時刻",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20),
        height=400,
    )

    fig.update_yaxes(title_text="風速 (m/s)", secondary_y=False, gridcolor="#eee")
    fig.update_yaxes(
        title_text="潮位 (相対cm)", secondary_y=True, showgrid=False
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("データの取得に失敗しました。")