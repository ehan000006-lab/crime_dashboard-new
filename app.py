import streamlit as st
import pandas as pd
import numpy as np
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
    # 범죄율 검거율
    try:
        crime = pd.read_csv('자치구별 범죄율 검거율 5개년.csv', encoding='utf-8', header=1)
    except:
        crime = pd.read_csv('자치구별 범죄율 검거율 5개년.csv', encoding='cp949', header=1)
    crime.columns = ['자치구별',
                     '2019_범죄율', '2019_검거율',
                     '2020_범죄율', '2020_검거율',
                     '2021_범죄율', '2021_검거율',
                     '2022_범죄율', '2022_검거율',
                     '2023_범죄율', '2023_검거율']
    crime = crime.dropna(subset=['자치구별'])
    for c in crime.columns[1:]:
        crime[c] = pd.to_numeric(crime[c], errors='coerce')

    # 전국 발생 검거 수
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
    occur = occur[occur['자치구별'] != '소계']
    for c in occur.columns[1:]:
        occur[c] = pd.to_numeric(occur[c].astype(str).str.replace(',', ''), errors='coerce')

    # CCTV
    try:
        cctv = pd.read_csv('cctv_clean.csv', encoding='utf-8')
    except:
        cctv = pd.read_csv('cctv_clean.csv', encoding='cp949')
    cctv['총 계'] = pd.to_numeric(cctv['총 계'].astype(str).str.replace(',', ''), errors='coerce')

    # 인구
    try:
        pop = pd.read_csv('인구 수.csv', encoding='utf-8', header=1)
    except:
        pop = pd.read_csv('인구 수.csv', encoding='cp949', header=1)
    pop.columns = ['자치구별', '2019_인구', '2020_인구', '2021_인구', '2022_인구', '2023_인구']
    pop = pop.dropna(subset=['자치구별'])
    pop = pop[pop['자치구별'] != '서울특별시']
    for c in pop.columns[1:]:
        pop[c] = pd.to_numeric(pop[c].astype(str).str.replace(',', ''), errors='coerce')

    return crime, occur, cctv, pop

crime, occur, cctv, pop = load_data()

# --- GeoJSON 불러오기 ---
@st.cache_data
def load_geojson():
    url = "https://raw.githubusercontent.com/southkorea/seoul-maps/master/kostat/2013/json/seoul_municipalities_geo_simple.json"
    return requests.get(url).json()

seoul_geo = load_geojson()

# ==========================================
# 복합 위험도 점수 계산 함수
# ==========================================
@st.cache_data
def calc_risk_score(crime_df, occur_df, cctv_df, pop_df, year=2023):
    risk = pd.DataFrame()
    risk['자치구별'] = crime_df['자치구별'].str.strip()

    col_crime = f'{year}_범죄율'
    if col_crime in crime_df.columns:
        risk['범죄율'] = pd.to_numeric(crime_df[col_crime], errors='coerce').values
    else:
        risk['범죄율'] = 0

    col_arrest = f'{year}_검거율'
    if col_arrest in crime_df.columns:
        risk['검거율'] = pd.to_numeric(crime_df[col_arrest], errors='coerce').values
    else:
        risk['검거율'] = 0

    col_occur = f'{year}_발생'
    col_pop = f'{year}_인구'

    occur_clean = occur_df.copy()
    occur_clean['자치구별'] = occur_clean['자치구별'].str.strip()
    if col_occur in occur_clean.columns:
        occur_clean[col_occur] = pd.to_numeric(occur_clean[col_occur].astype(str).str.replace(',', ''), errors='coerce')
    risk = risk.merge(occur_clean[['자치구별', col_occur]], on='자치구별', how='left')

    pop_clean = pop_df.copy()
    pop_clean['자치구별'] = pop_clean['자치구별'].str.strip()
    if col_pop in pop_clean.columns:
        pop_clean[col_pop] = pd.to_numeric(pop_clean[col_pop].astype(str).str.replace(',', ''), errors='coerce')
    risk = risk.merge(pop_clean[['자치구별', col_pop]], on='자치구별', how='left')

    risk['인구만명당_범죄'] = (risk[col_occur] / risk[col_pop] * 10000).round(2)

    cctv_clean = cctv_df.copy()
    cctv_clean = cctv_clean.rename(columns={'자치구': '자치구별'})
    cctv_clean['자치구별'] = cctv_clean['자치구별'].str.strip()
    cctv_clean['총 계'] = pd.to_numeric(cctv_clean['총 계'].astype(str).str.replace(',', ''), errors='coerce')
    risk = risk.merge(cctv_clean[['자치구별', '총 계']], on='자치구별', how='left')
    risk['인구천명당_CCTV'] = (risk['총 계'] / risk[col_pop] * 1000).round(2)

    def normalize(series):
        min_val = series.min()
        max_val = series.max()
        if max_val == min_val:
            return pd.Series([0.5] * len(series))
        return ((series - min_val) / (max_val - min_val)).round(4)

    risk['범죄율_norm'] = normalize(risk['범죄율'])
    risk['검거율_norm'] = 1 - normalize(risk['검거율'])
    risk['인구만명당범죄_norm'] = normalize(risk['인구만명당_범죄'])
    risk['CCTV_norm'] = 1 - normalize(risk['인구천명당_CCTV'])

    risk['위험도_점수'] = (
        risk['범죄율_norm'] * 0.30 +
        risk['검거율_norm'] * 0.20 +
        risk['인구만명당범죄_norm'] * 0.30 +
        risk['CCTV_norm'] * 0.20
    ).round(4)
    risk['위험도_점수_100'] = (risk['위험도_점수'] * 100).round(1)

    def grade(score):
        if score >= 70:
            return '🔴 위험'
        elif score >= 50:
            return '🟠 주의'
        elif score >= 30:
            return '🟡 보통'
        else:
            return '🟢 안전'

    risk['위험등급'] = risk['위험도_점수_100'].apply(grade)
    return risk

# --- 사이드바 ---
menu = st.sidebar.radio(
    "📌 메뉴 선택",
    ["범죄 현황 분석", "CCTV 현황", "위험도 지도", "🆕 복합 위험도 분석", "🆕 맞춤형 조회"]
)

# ==========================================
# 페이지 1: 범죄 현황 분석
# ==========================================
if menu == "범죄 현황 분석":
    st.header("📊 자치구별 범죄 현황 분석")
    year = st.sidebar.selectbox("연도 선택", [2023, 2022, 2021, 2020, 2019])

    st.subheader(f"{year}년 자치구별 범죄 발생 건수")
    col_occur = f'{year}_발생'
    if col_occur in occur.columns:
        occur_sorted = occur.sort_values(col_occur, ascending=False)
        fig1 = px.bar(occur_sorted, x='자치구별', y=col_occur,
                      color=col_occur, color_continuous_scale='Reds',
                      labels={col_occur: '발생 건수', '자치구별': '자치구'})
        fig1.update_layout(xaxis_tickangle=-45, height=500)
        st.plotly_chart(fig1, use_container_width=True)

    st.subheader(f"{year}년 자치구별 범죄율(%)")
    col_rate = f'{year}_범죄율'
    if col_rate in crime.columns:
        crime_sorted = crime.sort_values(col_rate, ascending=False)
        fig2 = px.bar(crime_sorted, x='자치구별', y=col_rate,
                      color=col_rate, color_continuous_scale='OrRd',
                      labels={col_rate: '범죄율(%)', '자치구별': '자치구'})
        fig2.update_layout(xaxis_tickangle=-45, height=500)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("연도별 범죄 발생 추이 (상위 5개 구)")
    occur_years = occur[['자치구별', '2019_발생', '2020_발생', '2021_발생', '2022_발생', '2023_발생']].copy()
    top5 = occur_years.nlargest(5, '2023_발생')['자치구별'].tolist()
    top5_data = occur_years[occur_years['자치구별'].isin(top5)]
    top5_melted = top5_data.melt(id_vars='자치구별', var_name='연도', value_name='발생건수')
    top5_melted['연도'] = top5_melted['연도'].str.replace('_발생', '')
    fig3 = px.line(top5_melted, x='연도', y='발생건수', color='자치구별',
                   markers=True, labels={'발생건수': '발생 건수', '연도': '연도'})
    fig3.update_layout(height=450)
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader(f"{year}년 자치구별 검거율(%)")
    col_arrest = f'{year}_검거율'
    if col_arrest in crime.columns:
        crime_arrest = crime.sort_values(col_arrest, ascending=True)
        fig4 = px.bar(crime_arrest, x=col_arrest, y='자치구별', orientation='h',
                      color=col_arrest, color_continuous_scale='Blues',
                      labels={col_arrest: '검거율(%)', '자치구별': '자치구'})
        fig4.update_layout(height=600)
        st.plotly_chart(fig4, use_container_width=True)

# ==========================================
# 페이지 2: CCTV 현황
# ==========================================
elif menu == "CCTV 현황":
    st.header("📹 자치구별 CCTV 설치 현황")
    st.dataframe(cctv, use_container_width=True)

    st.subheader("2023년 자치구별 인구 현황")
    if '2023_인구' in pop.columns:
        pop_sorted = pop.sort_values('2023_인구', ascending=False)
        fig5 = px.bar(pop_sorted, x='자치구별', y='2023_인구',
                      color='2023_인구', color_continuous_scale='Viridis',
                      labels={'2023_인구': '인구수', '자치구별': '자치구'})
        fig5.update_layout(xaxis_tickangle=-45, height=500)
        st.plotly_chart(fig5, use_container_width=True)

# ==========================================
# 페이지 3: 위험도 지도 (기존)
# ==========================================
elif menu == '위험도 지도':
    st.header('🗺️ 서울시 범죄 위험도 지도')
    year_map = st.sidebar.selectbox('연도 선택', [2023, 2022, 2021, 2020, 2019], key='map_year')
    indicator = st.sidebar.selectbox('지표 선택', ['범죄율', '검거율', '범죄 발생 건수', '인구 대비 CCTV'])

    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles='CartoDB positron')

    if indicator == '범죄율':
        col_val = f'{year_map}_범죄율'
        data_df = crime
        legend = f'{year_map}년 범죄율(%)'
        color_scale = 'YlOrRd'
    elif indicator == '검거율':
        col_val = f'{year_map}_검거율'
        data_df = crime
        legend = f'{year_map}년 검거율(%)'
        color_scale = 'YlGnBu'
    elif indicator == '범죄 발생 건수':
        col_val = f'{year_map}_발생'
        data_df = occur
        legend = f'{year_map}년 범죄 발생 건수'
        color_scale = 'OrRd'
    elif indicator == '인구 대비 CCTV':
        cctv_pop = cctv[['자치구', '총 계']].copy().rename(columns={'자치구': '자치구별'})
        cctv_pop['자치구별'] = cctv_pop['자치구별'].str.strip()
        cctv_pop['총 계'] = pd.to_numeric(cctv_pop['총 계'].astype(str).str.replace(',', ''), errors='coerce')
        pop_c = pop.copy()
        pop_c['자치구별'] = pop_c['자치구별'].str.strip()
        pop_c['2023_인구'] = pd.to_numeric(pop_c['2023_인구'].astype(str).str.replace(',', ''), errors='coerce')
        merged = pd.merge(cctv_pop, pop_c[['자치구별', '2023_인구']], on='자치구별', how='inner')
        merged['인구천명당_CCTV'] = (merged['총 계'] / merged['2023_인구'] * 1000).round(2)
        data_df = merged
        col_val = '인구천명당_CCTV'
        legend = '인구 1000명당 CCTV'
        color_scale = 'PuBu'

    if col_val in data_df.columns:
        folium.Choropleth(
            geo_data=seoul_geo, name='choropleth', data=data_df,
            columns=['자치구별', col_val], key_on='feature.properties.name',
            fill_color=color_scale, fill_opacity=0.7, line_opacity=0.3,
            legend_name=legend
        ).add_to(m)

        for feature in seoul_geo['features']:
            gu_name = feature['properties']['name']
            row = data_df[data_df['자치구별'].str.strip() == gu_name]
            if not row.empty:
                val = row[col_val].values[0]
                popup_text = f'<b>{gu_name}</b><br>{legend}: {val}'
                folium.GeoJson(
                    feature,
                    style_function=lambda x: {'fillOpacity': 0, 'weight': 0},
                    tooltip=folium.Tooltip(popup_text)
                ).add_to(m)

    st_folium(m, width=800, height=550)

    if col_val in data_df.columns:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f'⚠️ {indicator} 상위 5개 구')
            st.dataframe(data_df.nlargest(5, col_val)[['자치구별', col_val]], use_container_width=True, hide_index=True)
        with col2:
            st.subheader(f'✅ {indicator} 하위 5개 구')
            st.dataframe(data_df.nsmallest(5, col_val)[['자치구별', col_val]], use_container_width=True, hide_index=True)

# ==========================================
# 페이지 4: 복합 위험도 분석
# ==========================================
elif menu == '🆕 복합 위험도 분석':
    st.header('🗺️ 복합 환경 지표 기반 위험도 지도')
    st.caption('범죄율, 검거율, 인구 대비 범죄, CCTV 밀도를 종합한 복합 위험도 점수입니다.')

    year_risk = st.sidebar.selectbox('연도 선택', [2023, 2022, 2021, 2020, 2019], key='risk_year')
    risk_df = calc_risk_score(crime, occur, cctv, pop, year=year_risk)

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚖️ 가중치 조절")
    w_crime = st.sidebar.slider("범죄율 가중치", 0, 100, 30, key='w1')
    w_arrest = st.sidebar.slider("검거율(역) 가중치", 0, 100, 20, key='w2')
    w_occur = st.sidebar.slider("인구당 범죄 가중치", 0, 100, 30, key='w3')
    w_cctv = st.sidebar.slider("CCTV 부족 가중치", 0, 100, 20, key='w4')

    total_w = w_crime + w_arrest + w_occur + w_cctv
    if total_w > 0:
        risk_df['위험도_점수'] = (
            risk_df['범죄율_norm'] * (w_crime / total_w) +
            risk_df['검거율_norm'] * (w_arrest / total_w) +
            risk_df['인구만명당범죄_norm'] * (w_occur / total_w) +
            risk_df['CCTV_norm'] * (w_cctv / total_w)
        ).round(4)
        risk_df['위험도_점수_100'] = (risk_df['위험도_점수'] * 100).round(1)

        def grade(score):
            if score >= 70:
                return '🔴 위험'
            elif score >= 50:
                return '🟠 주의'
            elif score >= 30:
                return '🟡 보통'
            else:
                return '🟢 안전'
        risk_df['위험등급'] = risk_df['위험도_점수_100'].apply(grade)

    m2 = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles='CartoDB positron')

    folium.Choropleth(
        geo_data=seoul_geo, name='위험도', data=risk_df,
        columns=['자치구별', '위험도_점수_100'],
        key_on='feature.properties.name',
        fill_color='RdYlGn_r', fill_opacity=0.75, line_opacity=0.4,
        legend_name=f'{year_risk}년 복합 위험도 점수 (0~100)'
    ).add_to(m2)

    for feature in seoul_geo['features']:
        gu_name = feature['properties']['name']
        row = risk_df[risk_df['자치구별'] == gu_name]
        if not row.empty:
            r = row.iloc[0]
            popup_html = f"""
            <div style="font-family:sans-serif; font-size:13px; min-width:180px;">
                <b style="font-size:15px;">{gu_name}</b><br><br>
                📊 위험도 점수: <b>{r['위험도_점수_100']}</b>/100<br>
                {r['위험등급']}<br><br>
                ▸ 범죄율: {r['범죄율']}%<br>
                ▸ 검거율: {r['검거율']}%<br>
                ▸ 인구만명당 범죄: {r['인구만명당_범죄']}건<br>
                ▸ 인구천명당 CCTV: {r['인구천명당_CCTV']}대
            </div>
            """
            folium.GeoJson(
                feature,
                style_function=lambda x: {'fillOpacity': 0, 'weight': 0.5, 'color': '#333'},
                tooltip=folium.Tooltip(popup_html)
            ).add_to(m2)

    st_folium(m2, width=800, height=550)

    st.subheader(f'📋 {year_risk}년 자치구별 복합 위험도 랭킹')
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### ⚠️ 위험도 상위 5개 구")
        top5 = risk_df.nlargest(5, '위험도_점수_100')[['자치구별', '위험도_점수_100', '위험등급', '범죄율', '검거율', '인구만명당_범죄', '인구천명당_CCTV']]
        st.dataframe(top5, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("### ✅ 위험도 하위 5개 구 (안전)")
        bot5 = risk_df.nsmallest(5, '위험도_점수_100')[['자치구별', '위험도_점수_100', '위험등급', '범죄율', '검거율', '인구만명당_범죄', '인구천명당_CCTV']]
        st.dataframe(bot5, use_container_width=True, hide_index=True)

    st.subheader(f'{year_risk}년 전체 자치구 위험도 점수')
    risk_sorted = risk_df.sort_values('위험도_점수_100', ascending=True)
    fig_risk = px.bar(risk_sorted, x='위험도_점수_100', y='자치구별', orientation='h',
                      color='위험도_점수_100', color_continuous_scale='RdYlGn_r',
                      labels={'위험도_점수_100': '위험도 점수', '자치구별': '자치구'},
                      hover_data=['위험등급', '범죄율', '검거율', '인구만명당_범죄', '인구천명당_CCTV'])
    fig_risk.update_layout(height=650)
    st.plotly_chart(fig_risk, use_container_width=True)

    st.subheader('🕸️ 상위 위험 지역 세부 지표 비교 (레이더 차트)')
    top3 = risk_df.nlargest(3, '위험도_점수_100')
    categories = ['범죄율', '검거율(역)', '인구당 범죄', 'CCTV 부족']
    fig_radar = go.Figure()
    colors = ['#ff4444', '#ff8800', '#ffcc00']
    for i, (_, row) in enumerate(top3.iterrows()):
        values = [row['범죄율_norm'], row['검거율_norm'], row['인구만명당범죄_norm'], row['CCTV_norm']]
        values.append(values[0])
        fig_radar.add_trace(go.Scatterpolar(
            r=values, theta=categories + [categories[0]],
            fill='toself', name=row['자치구별'], opacity=0.6,
            line=dict(color=colors[i])
        ))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                            showlegend=True, height=500)
    st.plotly_chart(fig_radar, use_container_width=True)

    st.subheader('📈 범죄율 vs 인구당 CCTV 산점도')
    fig_scatter = px.scatter(risk_df, x='인구천명당_CCTV', y='범죄율',
                             size='위험도_점수_100', color='위험도_점수_100',
                             color_continuous_scale='RdYlGn_r', hover_name='자치구별',
                             labels={'인구천명당_CCTV': '인구 천명당 CCTV(대)', '범죄율': '범죄율(%)'},
                             size_max=30)
    fig_scatter.update_layout(height=500)
    st.plotly_chart(fig_scatter, use_container_width=True)

# ==========================================
# 페이지 5: 맞춤형 조회
# ==========================================
elif menu == '🆕 맞춤형 조회':
    st.header('🔎 맞춤형 자치구 조회')
    st.caption('원하는 조건으로 자치구를 검색하고 비교해보세요.')

    year_q = st.sidebar.selectbox('기준 연도', [2023, 2022, 2021, 2020, 2019], key='query_year')
    risk_df = calc_risk_score(crime, occur, cctv, pop, year=year_q)

    tab1, tab2, tab3 = st.tabs(["🏘️ 자치구 선택 조회", "🎯 조건 필터링", "📊 자치구 비교"])

    with tab1:
        selected_gu = st.selectbox('자치구를 선택하세요', sorted(risk_df['자치구별'].tolist()))
        row = risk_df[risk_df['자치구별'] == selected_gu].iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("위험도 점수", f"{row['위험도_점수_100']}/100")
        c2.metric("범죄율", f"{row['범죄율']}%")
        c3.metric("검거율", f"{row['검거율']}%")
        c4.metric("위험등급", row['위험등급'])

        c5, c6 = st.columns(2)
        c5.metric("인구 만명당 범죄", f"{row['인구만명당_범죄']}건")
        c6.metric("인구 천명당 CCTV", f"{row['인구천명당_CCTV']}대")

        st.markdown("---")
        st.subheader(f'📊 {selected_gu} 세부 지표 분석')

        categories = ['범죄율', '검거율(역)', '인구당 범죄', 'CCTV 부족']
        values = [row['범죄율_norm'], row['검거율_norm'], row['인구만명당범죄_norm'], row['CCTV_norm']]
        avg_values = [risk_df['범죄율_norm'].mean(), risk_df['검거율_norm'].mean(),
                      risk_df['인구만명당범죄_norm'].mean(), risk_df['CCTV_norm'].mean()]

        fig_gu = go.Figure()
        fig_gu.add_trace(go.Scatterpolar(
            r=values + [values[0]], theta=categories + [categories[0]],
            fill='toself', name=selected_gu, opacity=0.7, line=dict(color='#ff4444')
        ))
        fig_gu.add_trace(go.Scatterpolar(
            r=avg_values + [avg_values[0]], theta=categories + [categories[0]],
            fill='toself', name='서울 평균', opacity=0.4, line=dict(color='#4488ff', dash='dash')
        ))
        fig_gu.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                             showlegend=True, height=450)
        st.plotly_chart(fig_gu, use_container_width=True)

        st.subheader(f'📈 {selected_gu} 연도별 범죄율 추이')
        gu_crime = crime[crime['자치구별'].str.strip() == selected_gu]
        if not gu_crime.empty:
            years = [2019, 2020, 2021, 2022, 2023]
            rates = []
            for y in years:
                col = f'{y}_범죄율'
                if col in gu_crime.columns:
                    rates.append(pd.to_numeric(gu_crime[col].values[0], errors='coerce'))
                else:
                    rates.append(None)
            trend_df = pd.DataFrame({'연도': years, '범죄율': rates})
            fig_trend = px.line(trend_df, x='연도', y='범죄율', markers=True, labels={'범죄율': '범죄율(%)'})
            fig_trend.update_layout(height=350)
            st.plotly_chart(fig_trend, use_container_width=True)

    with tab2:
        st.subheader('🎯 조건으로 자치구 필터링')
        col_a, col_b = st.columns(2)
        with col_a:
            risk_range = st.slider('위험도 점수 범위', 0.0, 100.0, (0.0, 100.0), step=1.0)
            crime_max = st.number_input('범죄율 상한 (%)', min_value=0.0, max_value=10.0, value=5.0, step=0.1)
        with col_b:
            arrest_min = st.number_input('검거율 하한 (%)', min_value=0.0, max_value=200.0, value=50.0, step=1.0)
            cctv_min = st.number_input('인구천명당 CCTV 하한 (대)', min_value=0.0, max_value=50.0, value=5.0, step=0.5)

        filtered = risk_df[
            (risk_df['위험도_점수_100'] >= risk_range[0]) &
            (risk_df['위험도_점수_100'] <= risk_range[1]) &
            (risk_df['범죄율'] <= crime_max) &
            (risk_df['검거율'] >= arrest_min) &
            (risk_df['인구천명당_CCTV'] >= cctv_min)
        ].sort_values('위험도_점수_100', ascending=True)

        st.markdown(f"**검색 결과: {len(filtered)}개 자치구**")

        if not filtered.empty:
            display_cols = ['자치구별', '위험도_점수_100', '위험등급', '범죄율', '검거율', '인구만명당_범죄', '인구천명당_CCTV']
            st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

            m3 = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles='CartoDB positron')
            filtered_names = filtered['자치구별'].tolist()

            for feature in seoul_geo['features']:
                gu_name = feature['properties']['name']
                is_filtered = gu_name in filtered_names
                row_f = filtered[filtered['자치구별'] == gu_name]

                if is_filtered and not row_f.empty:
                    r = row_f.iloc[0]
                    score = r['위험도_점수_100']
                    if score >= 70:
                        fill_color = '#ff4444'
                    elif score >= 50:
                        fill_color = '#ff8800'
                    elif score >= 30:
                        fill_color = '#ffcc00'
                    else:
                        fill_color = '#44bb44'
                    folium.GeoJson(
                        feature,
                        style_function=lambda x, c=fill_color: {
                            'fillOpacity': 0.6, 'weight': 2, 'color': '#333', 'fillColor': c
                        },
                        tooltip=folium.Tooltip(f"<b>{gu_name}</b><br>위험도: {score}<br>{r['위험등급']}")
                    ).add_to(m3)
                else:
                    folium.GeoJson(
                        feature,
                        style_function=lambda x: {
                            'fillOpacity': 0.1, 'weight': 0.5, 'color': '#999', 'fillColor': '#ddd'
                        },
                        tooltip=folium.Tooltip(f"{gu_name} (필터 외)")
                    ).add_to(m3)
            st_folium(m3, width=800, height=500)
        else:
            st.warning("조건에 맞는 자치구가 없습니다. 조건을 완화해보세요.")

    with tab3:
        st.subheader('📊 자치구 비교 분석')
        all_gu = sorted(risk_df['자치구별'].tolist())
        compare_list = st.multiselect('비교할 자치구 선택 (최대 5개)', all_gu, default=all_gu[:3], max_selections=5)

        if len(compare_list) >= 2:
            compare_df = risk_df[risk_df['자치구별'].isin(compare_list)]
            display_cols = ['자치구별', '위험도_점수_100', '위험등급', '범죄율', '검거율', '인구만명당_범죄', '인구천명당_CCTV']
            st.dataframe(compare_df[display_cols].sort_values('위험도_점수_100', ascending=False),
                         use_container_width=True, hide_index=True)

            categories = ['범죄율', '검거율(역)', '인구당 범죄', 'CCTV 부족']
            colors_list = ['#ff4444', '#4488ff', '#44bb44', '#ff8800', '#aa44ff']
            fig_comp = go.Figure()
            for i, (_, row) in enumerate(compare_df.iterrows()):
                vals = [row['범죄율_norm'], row['검거율_norm'], row['인구만명당범죄_norm'], row['CCTV_norm']]
                fig_comp.add_trace(go.Scatterpolar(
                    r=vals + [vals[0]], theta=categories + [categories[0]],
                    fill='toself', name=row['자치구별'], opacity=0.5,
                    line=dict(color=colors_list[i % len(colors_list)])
                ))
            fig_comp.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                                   showlegend=True, height=500)
            st.plotly_chart(fig_comp, use_container_width=True)

            compare_melted = compare_df[['자치구별', '범죄율', '검거율', '인구만명당_범죄', '인구천명당_CCTV']].melt(
                id_vars='자치구별', var_name='지표', value_name='값')
            fig_bar_comp = px.bar(compare_melted, x='지표', y='값', color='자치구별',
                                 barmode='group', labels={'값': '수치', '지표': '지표'})
            fig_bar_comp.update_layout(height=450)
            st.plotly_chart(fig_bar_comp, use_container_width=True)
        else:
            st.info("2개 이상의 자치구를 선택해주세요.")