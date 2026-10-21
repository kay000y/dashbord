import json
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="전국 인구지표 단계구분도", layout="wide")

st.title("📊 전국 시군구별 인구지표 단계구분도")
st.markdown(
    "행정안전부 주민등록인구 데이터를 바탕으로 연도별·지역별 고령화율 및 유소년 비율을 시각화합니다."
)


@st.cache_data
def load_base_data():
    # 1. 인구 데이터 불러오기 (압축 CSV 파일)
    pop_url = "https://raw.githubusercontent.com/kay000y/dashbord//main/population_ts_yearly_gender.zip"
    df = pd.read_csv(pop_url, compression="zip")

    # 2. GeoJSON 불러오기
    geojson_url = "https://raw.githubusercontent.com/kay000y/dashbord//main/sigungu_kr.geojson"
    res = requests.get(geojson_url)
    geojson_data = res.json()

    # GeoJSON property 정보 추출 및 데이터프레임 생성
    geo_info = []
    for feature in geojson_data["features"]:
        props = feature["properties"]
        geo_info.append(
            {
                "시군구코드": str(props["코드"]),
                "시도": props.get("시도", ""),
                "시군구": props.get("시군구", ""),
            }
        )
    df_geo = pd.DataFrame(geo_info)

    return df, df_geo, geojson_data


with st.spinner("데이터를 로딩 중입니다..."):
    df_raw, df_geo, geojson_kr = load_base_data()

# -----------------------------------------------------------------------------
# 사이드바 컨트롤러
# -----------------------------------------------------------------------------
st.sidebar.header("🎛️ 설정")

# 1. 연도 선택 슬라이더 (데이터에 존재하는 연도 추출)
available_years = sorted(df_raw["연도"].unique())
selected_year = st.sidebar.slider(
    "연도 선택",
    min_value=int(min(available_years)),
    max_value=int(max(available_years)),
    value=int(max(available_years)),
    step=1,
)

# 2. 지표 선택
indicator = st.sidebar.radio(
    "조회 지표",
    ["65세 이상 비율(고령화율)", "0~14세 비율(유소년 비율)"],
)

# 3. 시도 선택 드롭다운
sido_list = ["전국"] + sorted(df_geo["시도"].unique().tolist())
selected_sido = st.sidebar.selectbox("시도 선택", sido_list)


# -----------------------------------------------------------------------------
# 데이터 전처리 및 연산
# -----------------------------------------------------------------------------
def process_year_data(df, year):
    df_yr = df[df["연도"] == year].copy()

    # 원본 코드 추출 (문자열 8자리 변환 후 앞 5자리)
    raw_code = df_yr["코드"].astype(str).str.zfill(8).str[:5]

    # 행정구역 개편 코드 매핑 규칙 적용
    # - 강원: 42xxx -> 51xxx
    # - 전북: 45xxx -> 52xxx
    # - 대구 군위군: 47720 -> 27720
    mapped_code = raw_code.copy()
    mapped_code = mapped_code.apply(
        lambda c: "27720" if c == "47720" else c
    )
    mapped_code = mapped_code.apply(
        lambda c: "51" + c[2:] if c.startswith("42") else c
    )
    mapped_code = mapped_code.apply(
        lambda c: "52" + c[2:] if c.startswith("45") else c
    )

    df_yr["시군구코드"] = mapped_code

    # 계_ 로 시작하는 열 목록
    total_cols = [c for c in df_yr.columns if c.startswith("계_")]

    col_65_plus = []
    col_0_14 = []

    for c in total_cols:
        age_str = c.replace("계_", "").replace("세", "").replace(" 이상", "")
        try:
            age = int(age_str)
            if age >= 65:
                col_65_plus.append(c)
            elif age <= 14:
                col_0_14.append(c)
        except ValueError:
            pass

    # 행별 합계 구하기
    df_yr["총인구"] = df_yr[total_cols].sum(axis=1)
    df_yr["65세이상인구"] = df_yr[col_65_plus].sum(axis=1)
    df_yr["0_14세인구"] = df_yr[col_0_14].sum(axis=1)

    # 시군구 단위 집계
    grouped = (
        df_yr.groupby("시군구코드")[
            ["총인구", "65세이상인구", "0_14세인구"]
        ]
        .sum()
        .reset_index()
    )

    # 비율 계산 (%)
    grouped["고령화율"] = np.where(
        grouped["총인구"] > 0,
        (grouped["65세이상인구"] / grouped["총인구"]) * 100,
        0,
    ).round(2)

    grouped["유소년비율"] = np.where(
        grouped["총인구"] > 0,
        (grouped["0_14세인구"] / grouped["총인구"]) * 100,
        0,
    ).round(2)

    return grouped


df_grouped = process_year_data(df_raw, selected_year)

# GeoJSON 기반 지도용 마스터 데이터프레임 구축 (Right Join 개념으로 GeoJSON 기준 유지)
df_map = pd.merge(df_geo, df_grouped)
