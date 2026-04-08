import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import requests

# --- 페이지 설정 ---
st.set_page_config(page_title="서울시 범죄 위험도 분석", layout="wide")
st.title("🔍 서울시 범죄 위험도 분석 대시보드")

# --- 데이터 불러오기 ---
@st.cache_data
def load_data():
    # 범죄율 검거율 (헤더가 2줄이라 skiprows로 처리)
    try:
        crime = pd.read_csv('자치구별 범죄율 검거율 5개년.csv', encoding='utf-8', header=1)
    except:
        crime = pd.read_csv('자치구별 범죄율 검거율 5개년.csv', encoding='cp949', header=1)
    # 첫번째 행에 자치구별 이름이 있으므로 컬럼명 정리
    crime.columns = ['자치구별',
                     '2019_범죄율', '2019_검거율',
                     '2020_범죄율', '2020_검거율',
                     '2021_범죄율', '2021_검거율',
                     '2022_범죄율', '2022_검거율',
                     '2023_범죄율', '2023_검거율']
    crime = crime.dropna(subset=['자치구별'])

    # 전국 발생 검거 수 (헤더 2줄)
    try:
        occur = pd.read_csv('전국 발생 검거 수.csv', encoding='utf-8', header=1)
    except:
        occur = pd.read_csv('전국 발생 검거 수.csv', encoding='cp949', header=1)
    occur.columns = ['자치구별',
                     '2019_발생', '2019_검거',
                     '2020_발생', '2020_검거',
                     '2021_발생', '2021_검거',
                     '2022_발생', '2022_검거',
                     '2023_발생', '2023_검거']
    occur = occur.dropna(subset=['자치구별'])
    # 소계 행 제거
    occur = occur[occur['자치구별'] != '소계']

    # CCTV
    try:
        cctv = pd.read_csv('cctv_clean.csv', encoding='utf-8')
    except:
        cctv = pd.read_csv('cctv_clean.csv', encoding='cp949')

    # 인구 (헤더 2줄)
    try:
        pop = pd.read_csv('인구 수.csv', encoding='utf-8', header=1)
    except:
        pop = pd.read_csv('인구 수.csv', encoding='cp949', header=1)
    pop.columns = ['자치구별', '2019_인구', '2020_인구', '2021_인구', '2022_인구', '2023_인구']
    pop = pop.dropna(subset=['자치구별'])
    # 서울특별시 합계 행 제거
    pop = pop[pop['자치구별'] != '서울특별시']

    return crime, occur, cctv, pop

crime, occur, cctv, pop = load_data()

# --- GeoJSON 불러오기 ---
@st.cache_data
def load_geojson():
    url = "https://raw.githubusercontent.com/southkorea/seoul-maps/master/kostat/2013/json/seoul_municipalities_geo_simple.json"
    return requests.get(url).json()

seoul_geo = load_geojson()

# --- 사이드바 ---
menu = st.sidebar.radio(
    "📌 메뉴 선택",
    ["범죄 현황 분석", "CCTV 현황", "위험도 지도"]
)

# ==========================================
# 페이지 1: 범죄 현황 분석
# ==========================================
if menu == "범죄 현황 분석":
    st.header("📊 자치구별 범죄 현황 분석")

    # 연도 선택
    year = st.sidebar.selectbox("연도 선택", [2023, 2022, 2021, 2020, 2019])

    # --- 차트 1: 자치구별 범죄 발생 건수 ---
    st.subheader(f"{year}년 자치구별 범죄 발생 건수")
    col_occur = f'{year}_발생'
    if col_occur in occur.columns:
        occur_sorted = occur.sort_values(col_occur, ascending=False)
        fig1 = px.bar(
            occur_sorted,
            x='자치구별',
            y=col_occur,
            color=col_occur,
            color_continuous_scale='Reds',
            labels={col_occur: '발생 건수', '자치구별': '자치구'}
        )
        fig1.update_layout(xaxis_tickangle=-45, height=500)
        st.plotly_chart(fig1, use_container_width=True)

    # --- 차트 2: 자치구별 범죄율 ---
    st.subheader(f"{year}년 자치구별 범죄율(%)")
    col_rate = f'{year}_범죄율'
    if col_rate in crime.columns:
        crime_sorted = crime.sort_values(col_rate, ascending=False)
        fig2 = px.bar(
            crime_sorted,
            x='자치구별',
            y=col_rate,
            color=col_rate,
            color_continuous_scale='OrRd',
            labels={col_rate: '범죄율(%)', '자치구별': '자치구'}
        )
        fig2.update_layout(xaxis_tickangle=-45, height=500)
        st.plotly_chart(fig2, use_container_width=True)

    # --- 차트 3: 범죄 발생 건수 연도별 추이 (상위 5개 구) ---
    st.subheader("연도별 범죄 발생 추이 (상위 5개 구)")
    occur_years = occur[['자치구별', '2019_발생', '2020_발생', '2021_발생', '2022_발생', '2023_발생']].copy()
    # 2023년 기준 상위 5개 구
    top5 = occur_years.nlargest(5, '2023_발생')['자치구별'].tolist()
    top5_data = occur_years[occur_years['자치구별'].isin(top5)]

    # 데이터를 long 형태로 변환
    top5_melted = top5_data.melt(id_vars='자치구별', var_name='연도', value_name='발생건수')
    top5_melted['연도'] = top5_melted['연도'].str.replace('_발생', '')

    fig3 = px.line(
        top5_melted,
        x='연도',
        y='발생건수',
        color='자치구별',
        markers=True,
        labels={'발생건수': '발생 건수', '연도': '연도'}
    )
    fig3.update_layout(height=450)
    st.plotly_chart(fig3, use_container_width=True)

    # --- 차트 4: 검거율 비교 ---
    st.subheader(f"{year}년 자치구별 검거율(%)")
    col_arrest = f'{year}_검거율'
    if col_arrest in crime.columns:
        crime_arrest = crime.sort_values(col_arrest, ascending=True)
        fig4 = px.bar(
            crime_arrest,
            x=col_arrest,
            y='자치구별',
            orientation='h',
            color=col_arrest,
            color_continuous_scale='Blues',
            labels={col_arrest: '검거율(%)', '자치구별': '자치구'}
        )
        fig4.update_layout(height=600)
        st.plotly_chart(fig4, use_container_width=True)

# ==========================================
# 페이지 2: CCTV 현황
# ==========================================
elif menu == "CCTV 현황":
    st.header("📹 자치구별 CCTV 설치 현황")

    # CCTV 데이터 표시
    st.dataframe(cctv, use_container_width=True)

    # --- 차트 5: 인구 대비 정보 ---
    st.subheader("2023년 자치구별 인구 현황")
    if '2023_인구' in pop.columns:
        pop_sorted = pop.sort_values('2023_인구', ascending=False)
        fig5 = px.bar(
            pop_sorted,
            x='자치구별',
            y='2023_인구',
            color='2023_인구',
            color_continuous_scale='Viridis',
            labels={'2023_인구': '인구수', '자치구별': '자치구'}
        )
        fig5.update_layout(xaxis_tickangle=-45, height=500)
        st.plotly_chart(fig5, use_container_width=True)

    st.info("CCTV 대수 데이터가 자치구별로 분리되면 자치구별 CCTV 차트도 추가할 예정입니다.")

# ==========================================
# 페이지 3: 위험도 지도
# ==========================================
elif menu == "위험도 지도":
    st.header("🗺️ 서울시 범죄 위험도 지도")

    year_map = st.sidebar.selectbox("연도 선택", [2023, 2022, 2021, 2020, 2019], key='map_year')

    # 범죄율 데이터로 Choropleth 지도 생성
    col_rate = f'{year_map}_범죄율'

    m = folium.Map(
        location=[37.5665, 126.9780],
        zoom_start=11,
        tiles='CartoDB positron'
    )

    # Choropleth (자치구별 범죄율 색상 지도)
    if col_rate in crime.columns:
        folium.Choropleth(
            geo_data=seoul_geo,
            name='choropleth',
            data=crime,
            columns=['자치구별', col_rate],
            key_on='feature.properties.name',
            fill_color='YlOrRd',
            fill_opacity=0.7,
            line_opacity=0.3,
            legend_name=f'{year_map}년 범죄율(%)'
        ).add_to(m)

    st_folium(m, width=800, height=550)

    # 범죄율 상위/하위 표시
    if col_rate in crime.columns:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("⚠️ 범죄율 상위 5개 구")
            top5 = crime.nlargest(5, col_rate)[['자치구별', col_rate]]
            st.dataframe(top5, use_container_width=True, hide_index=True)
        with col2:
            st.subheader("✅ 범죄율 하위 5개 구")
            bottom5 = crime.nsmallest(5, col_rate)[['자치구별', col_rate]]
            st.dataframe(bottom5, use_container_width=True, hide_index=True)