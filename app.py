import math
import datetime
import pandas as pd
import plotly.graph_objects as gg
from plotly.subplots import make_subplots
import requests
import streamlit as st

# --- 月齢計算関数（標準ライブラリのみ使用） ---
def get_moon_phase(date_obj):
    # 2000年1月6日 18:14 UTC（新月）を基準点とする
    known_new_moon = datetime.datetime(2000, 1, 6, 18, 14)
    if isinstance(date_obj, datetime.date) and not isinstance(date_obj, datetime.datetime):
        date_datetime = datetime.datetime.combine(date_obj, datetime.time(12, 0))
    else:
        date_datetime = date_obj
        
    synodic_month = 29.53058867
    diff_days = (date_datetime - known_new_moon).total_seconds() / 86400.0
    age = diff_days % synodic_month
    
    # 月相番号 (1:新月〜8:月)
    phase_num = int((age / synodic_month) * 8) % 8 + 1
    return f"{phase_num}/8", float(age)

# --- タイトル ---
st.title("天気・風向き・月齢 ダッシュボード")

# --- 設定パラメータ ---
LAT = 35.3606  # 緯度（例：出雲市付近）
LON = 132.7548 # 経度

# --- Open-Meteo APIからのデータ取得 ---
@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,wind_speed_10m,wind_direction_10m&timezone=Asia%2FTokyo"
    response = requests.get(url)
    data = response.json()
    
    df = pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "temperature": data["hourly"]["temperature_2m"],
        "wind_speed": data["hourly"]["wind_speed_10m"],
        "wind_direction": data["hourly"]["wind_direction_10m"]
    })
    return df

try:
    df = get_weather_data(LAT, LON)
    
    # --- 日付選択 ---
    available_dates = df["time"].dt.date.unique()
    selected_date = st.selectbox("日付を選択してください", available_dates)
    
    # 選択した日付のデータ抽出
    df_selected = df[df["time"].dt.date == selected_date].copy()
    df_selected["hour"] = df_selected["time"].dt.hour
    
    # --- 月齢計算 ---
    phase_str, moon_age = get_moon_phase(selected_date)
    
    # メトリクス表示
    col1, col2 = st.columns(2)
    with col1:
        st.metric("選択日", str(selected_date))
    with col2:
        st.metric("月齢", f"{moon_age:.1f} (月相: {phase_str})")
        
    # --- グラフ作成 ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 気温 (左Y軸)
    fig.add_trace(
        gg.Scatter(
            x=df_selected["hour"],
            y=df_selected["temperature"],
            name="気温 (℃)",
            line=dict(color="#ff7f0e", width=3),
            mode="lines+markers",
        ),
        secondary_y=False,
    )
    
    # 風速 (右Y軸)
    fig.add_trace(
        gg.Scatter(
            x=df_selected["hour"],
            y=df_selected["wind_speed"],
            name="風速 (m/s)",
            line=dict(color="#2ca02c", width=3),
            mode="lines+markers",
        ),
        secondary_y=True,
    )
    
    fig.update_layout(
        title=f"{selected_date} の時間別天気データ",
        xaxis_title="時間 (時)",
        yaxis_title="気温 (℃)",
        yaxis2_title="風速 (m/s)",
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # --- データテーブル表示 ---
    with st.expander("詳細データを表示"):
        st.dataframe(df_selected[["hour", "temperature", "wind_speed", "wind_direction"]])

except Exception as e:
    st.error(f"データの取得または処理中にエラーが発生しました: {e}")
