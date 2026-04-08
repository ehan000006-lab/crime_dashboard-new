import pandas as pd
import os

# CSV 파일 목록 (파일명이 다르면 실제 파일명으로 수정하세요)
files = [
    '자치구별 범죄율 검거율 5개년.csv',
    '전국 발생 검거 수.csv',
    '인구 수.csv',
    'cctv 대수.csv'
]

for f in files:
    if os.path.exists(f):
        print(f"===== {f} =====")
        try:
            df = pd.read_csv(f, encoding='utf-8')
        except:
            df = pd.read_csv(f, encoding='cp949')
        print(f"크기: {df.shape[0]}행 x {df.shape[1]}열")
        print(f"컬럼: {df.columns.tolist()}")
        print(df.head(3))
        print()
    else:
        print(f"[!] {f} 파일을 찾을 수 없습니다. 파일명을 확인하세요.")
        print()