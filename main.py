import json
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="전국 시군구 고령화 단계구분도", layout="wide")

st.title("📊 2026년 전국 시군구별 고령화율 단계구분도")
st.markdown(
    "행정안전부 주민등록인구 데이터를 바탕으로 시군구별 65세 이상 인구 비율(%)을 시각화합니다."
)


@st.cache_data
def load_data():
    # 1. 인구 데이터 불러오기 (압축 CSV 파일)
    pop_url = "https://raw.githubusercontent.com/kay000y/dashbord//main/population_ts_yearly_gender.zip"
    df = pd.read_csv(pop_url, compression="zip")

    # 2026년 데이터만 필터링
    df_2026 = df[df["연도"] == 2026].copy()

    # 행정동 코드를 5자리 시군구 코드로 변환 (문자열 처리)
    df_2026["시군구코드"] = (
        df_2026["코드"].astype(str).str.zfill(8).str[:5]
    )

    # 계 열만 선별
    total_cols = [c for c in df_2026.columns if c.startswith("계_")]

    # 65세 이상 열 선별 ('계_65세' ~ '계_100세 이상')
    col_65_plus = []
    for c in total_cols:
        age_str = c.replace("계_", "").replace("세", "").replace(" 이상", "")
        try:
            if int(age_str) >= 65:
                col_65_plus.append(c)
        except ValueError:
            pass

    # 시군구별 총인구 및 65세 이상 인구 합계 계산
    df_2026["총인구"] = df_2026[total_cols].sum(axis=1)
    df_2026["65세이상인구"] = df_2026[col_65_plus].sum(axis=1)

    grouped = (
        df_2026.groupby("시군구코드")[["총인구", "65세이상인구"]]
        .sum()
        .reset_index()
    )

    # 고령화율(%) 계산
    grouped["고령화율"] = np.where(
        grouped["총인구"] > 0,
        (grouped["65세이상인구"] / grouped["총인구"]) * 100,
        0,
    )
    grouped["고령화율"] = grouped["고령화율"].round(2)

    # 2. 시군구 경계 GeoJSON 불러오기
    geojson_url = "https://raw.githubusercontent.com/kay000y/dashbord//main/sigungu_kr.geojson"
    res = requests.get(geojson_url)
    geojson_data = res.json()

    # GeoJSON property 정보와 매핑용 데이터 프레임 생성
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
    df_geo_info = pd.DataFrame(geo_info)

    # 고령화율 데이터와 GeoJSON 속성 결합
    final_df = pd.merge(df_geo_info, grouped, on="시군구코드", how="left")
    final_df["고령화율"] = final_df["고령화율"].fillna(0)
    final_df["풀시군구명"] = final_df["시도"] + " " + final_df["시군구"]

    return final_df, geojson_data


with st.spinner("데이터를 읽어오는 중입니다..."):
    df_result, geojson_kr = load_data()

# 3. Plotly 단계구분도(Choropleth) 생성
fig = px.choropleth(
    df_result,
    geojson=geojson_kr,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="고령화율",
    color_continuous_scale="Reds",  # 고령화율이 높을수록 진해지는 붉은색 스케일
    hover_name="풀시군구명",
    hover_data={"시군구코드": False, "고령화율": ":.2f%"},
    labels={"고령화율": "고령화율(%)"},
)

# 배경 지도(타일)를 없애고 경계선만 깔끔하게 그리기
fig.update_geos(fitbounds="locations", visible=False)

fig.update_layout(
    margin={"r": 0, "t": 40, "l": 0, "b": 0},
    height=750,
)

# 4. 스트림릿 화면 출력
st.plotly_chart(fig, use_container_width=True)

# 주요 요약 정보 표시
col1, col2, col3 = st.columns(3)
with col1:
    max_row = df_result.loc[df_result["고령화율"].idxmax()]
    st.metric(
        "최고 고령화 지역",
        f"{max_row['풀시군구명']}",
        f"{max_row['고령화율']:.2f}%",
    )
with col2:
    min_row = df_result.loc[df_result["고령화율"].idxmin()]
    st.metric(
        "최저 고령화 지역",
        f"{min_row['풀시군구명']}",
        f"{min_row['고령화율']:.2f}%",
    )
with col3:
    avg_rate = df_result["고령화율"].mean()
    st.metric("시군구 평균 고령화율", f"{avg_rate:.2f}%")
