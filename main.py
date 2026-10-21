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
df_map = pd.merge(df_geo, df_grouped, on="시군구코드", how="left")
df_map["풀시군구명"] = df_map["시도"] + " " + df_map["시군구"]

# 데이터 매칭 실패 지역(미매칭/옛 행정구역 코드 등) 확인
unmatched_regions = df_map[df_map["총인구"].isna()]["풀시군구명"].tolist()

# 선택된 시도 필터링
if selected_sido != "전국":
    df_display = df_map[df_map["시도"] == selected_sido].copy()
else:
    df_display = df_map.copy()

# 지표별 변수 세팅
if "고령화율" in indicator:
    val_col = "고령화율"
    val_label = "고령화율(%)"

    # 구간 정의: 19%, 23%, 28%, 38%
    bins = [-np.inf, 19, 23, 28, 38, np.inf]
    labels = [
        "19% 미만",
        "19% 이상 ~ 23% 미만",
        "23% 이상 ~ 28% 미만",
        "28% 이상 ~ 38% 미만",
        "38% 이상",
    ]
    color_discrete_map = {
        "19% 미만": "#fee5d9",
        "19% 이상 ~ 23% 미만": "#fcae91",
        "23% 이상 ~ 28% 미만": "#fb6a4a",
        "28% 이상 ~ 38% 미만": "#de2d26",
        "38% 이상": "#a50f15",
        "데이터 없음": "#d9d9d9",
    }
else:
    val_col = "유소년비율"
    val_label = "유소년 비율(%)"

    # 유소년 비율 구간 정의 (8%, 10%, 12%, 14%)
    bins = [-np.inf, 8, 10, 12, 14, np.inf]
    labels = [
        "8% 미만",
        "8% 이상 ~ 10% 미만",
        "10% 이상 ~ 12% 미만",
        "12% 이상 ~ 14% 미만",
        "14% 이상",
    ]
    color_discrete_map = {
        "8% 미만": "#eff3ff",
        "8% 이상 ~ 10% 미만": "#bdd7e7",
        "10% 이상 ~ 12% 미만": "#6baed6",
        "12% 이상 ~ 14% 미만": "#3182bd",
        "14% 이상": "#08519c",
        "데이터 없음": "#d9d9d9",
    }

# 범주형 구간 컬럼 생성
df_display["구간"] = pd.cut(
    df_display[val_col], bins=bins, labels=labels
).astype(str)
df_display["구간"] = df_display["구간"].replace("nan", "데이터 없음")


# -----------------------------------------------------------------------------
# 지표 카드 (Metric) 세 장 출력
# -----------------------------------------------------------------------------
valid_data = df_display.dropna(subset=[val_col])

col1, col2, col3 = st.columns(3)

if not valid_data.empty:
    # 1. 전국/선택시도 총합 기반 비율 계산
    total_pop = valid_data["총인구"].sum()
    if "고령화율" in indicator:
        target_pop = valid_data["65세이상인구"].sum()
    else:
        target_pop = valid_data["0_14세인구"].sum()

    overall_rate = (target_pop / total_pop * 100) if total_pop > 0 else 0

    # 2. 최고 / 최저 지역
    max_row = valid_data.loc[valid_data[val_col].idxmax()]
    min_row = valid_data.loc[valid_data[val_col].idxmin()]

    area_prefix = f"[{selected_sido}] " if selected_sido != "전국" else ""

    with col1:
        st.metric(
            f"{area_prefix}전체 평균 {val_label.split('(')[0]}",
            f"{overall_rate:.2f}%",
        )
    with col2:
        st.metric(
            "가장 높은 시군구",
            f"{max_row['풀시군구명']}",
            f"{max_row[val_col]:.2f}%",
        )
    with col3:
        st.metric(
            "가장 낮은 시군구",
            f"{min_row['풀시군구명']}",
            f"{min_row[val_col]:.2f}%",
        )
else:
    st.info("해당 조건의 데이터가 존재하지 않습니다.")

st.markdown("---")

# -----------------------------------------------------------------------------
# Plotly Choropleth 생성
# -----------------------------------------------------------------------------
fig = px.choropleth(
    df_display,
    geojson=geojson_kr,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="구간",
    category_orders={"구간": labels + ["데이터 없음"]},
    color_discrete_map=color_discrete_map,
    hover_name="풀시군구명",
    hover_data={
        "시군구코드": False,
        "구간": False,
        val_col: ":.2f%",
    },
    labels={val_col: val_label, "구간": "구간"},
)

# 배경 지도 숨김 및 선택한 지역 중심으로 확대
fig.update_geos(fitbounds="locations", visible=False)

fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    height=720,
    legend_title_text=f"{val_label.split('(')[0]} 범주",
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 하단 안내 문구
# -----------------------------------------------------------------------------
if unmatched_regions:
    st.caption(
        f"⚠️ **데이터 미표시 지역 안내 ({len(unmatched_regions)}곳):** "
        f"{', '.join(unmatched_regions)} 은(는) 선택하신 {selected_year}년 기준 행정구역 코드 미비 또는 개편으로 인해 지도의 경계 데이터와 일치하지 않아 회색으로 표시되었습니다."
    )
