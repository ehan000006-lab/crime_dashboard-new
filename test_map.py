import folium
import requests

# 1. 서울시 자치구 GeoJSON을 인터넷에서 바로 불러오기
url = "https://raw.githubusercontent.com/southkorea/seoul-maps/master/kostat/2013/json/seoul_municipalities_geo_simple.json"
seoul_geo = requests.get(url).json()

# 2. 서울 중심 좌표로 지도 생성
m = folium.Map(
    location=[37.5665, 126.9780],
    zoom_start=11,
    tiles='CartoDB positron'
)

# 3. 자치구 경계를 지도에 표시
folium.GeoJson(
    seoul_geo,
    name='서울 행정구역',
    style_function=lambda x: {
        'fillColor': '#3186cc',
        'color': 'black',
        'weight': 1,
        'fillOpacity': 0.3
    }
).add_to(m)

# 4. HTML 파일로 저장
m.save('seoul_map_test.html')
print("완료! seoul_map_test.html 파일을 브라우저에서 열어보세요.")