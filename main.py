import plotly.graph_objects as go
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 스타일 정의
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="우리 동네 인구 피라미드", page_icon="👨‍👩‍👧‍👦", layout="centered"
)

# 따뜻하고 친근한 분위기를 위한 간단한 설명
st.title("👨‍👩‍👧‍👦 우리 동네 인구 피라미드")
st.write(
    "원하는 **시도, 시군구, 동**을 선택해서 연령별 남녀 인구 구성을 확인해보세요!"
)


# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 (캐싱 적용으로 속도 향상)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    """Github에서 인구 데이터 CSV(zip 압축)를 읽어와 가장 최신 연도 데이터만 반환합니다."""
    url = "https://raw.githubusercontent.com/kay000y/dashbord/main/population_ts_yearly_gender.zip"

    # pandas는 zip 파일 안의 csv를 자동으로 압축 해제하여 읽습니다.
    df = pd.read_csv(url)

    # 데이터에 존재하는 가장 최신 연도 추출
    latest_year = df["연도"].max()

    # 최신 연도 데이터만 필터링
    df_latest = df[df["연도"] == latest_year].copy()
    return df_latest, latest_year


# 데이터 로딩 스피너
with st.spinner("데이터를 불러오는 중입니다... 잠시만 기다려주세요."):
    df, latest_year = load_data()

st.caption(f"💡 현재 데이터 기준 연도: **{latest_year}년**")


# -----------------------------------------------------------------------------
# 3. 드롭다운(시도 -> 시군구 -> 동) 선택 UI
# -----------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df["시도"].dropna().unique())
    selected_sido = st.selectbox("1. 시·도 선택", sido_list)

# 선택된 시도에 해당하는 시군구 목록 추출
df_sido = df[df["시도"] == selected_sido]

with col2:
    sigungu_list = sorted(df_sido["시군구"].dropna().unique())
    selected_sigungu = st.selectbox("2. 시·군·구 선택", sigungu_list)

# 선택된 시군구에 해당하는 동 목록 추출
df_sigungu = df_sido[df_sido["시군구"] == selected_sigungu]

with col3:
    dong_list = sorted(df_sigungu["동"].dropna().unique())
    selected_dong = st.selectbox("3. 읍·면·동 선택", dong_list)

# 최종 선택된 동네 1개 행 추출
target_row = df_sigungu[df_sigungu["동"] == selected_dong].iloc[0]


# -----------------------------------------------------------------------------
# 4. 나이 순서 정렬 및 데이터 가공
# -----------------------------------------------------------------------------
# 0세부터 99세까지 + 100세 이상 순서대로 나이 라벨 리스트 생성 (아래에서 위로 올라가는 축 기준)
age_labels = [f"{i}세" for i in range(100)] + ["100세 이상"]

male_counts = []
female_counts = []

# 설정한 나이 순서대로 남/여 인구수 데이터 수집
for age in age_labels:
    male_col = f"남_{age}"
    female_col = f"여_{age}"

    # 남자는 왼쪽에 위치해야 하므로 음수(-) 값으로 변환
    male_val = -abs(int(target_row.get(male_col, 0)))
    female_val = int(target_row.get(female_col, 0))

    male_counts.append(male_val)
    female_counts.append(female_val)


# -----------------------------------------------------------------------------
# 5. Plotly 가로 막대그래프(인구 피라미드) 생성
# -----------------------------------------------------------------------------
fig = go.Figure()

# (1) 남자 막대그래프 (왼쪽, 따뜻한 코랄/오렌지계열 색상)
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=male_counts,
        name="남자",
        orientation="h",
        marker=dict(color="#FF8A65"),  # 따뜻한 코랄 오렌지
        hoverinfo="text",
        # 마우스 호버 시 음수(- ) 대신 양수 값으로 보기 좋게 표시
        hovertext=[
            f"<b>{age}</b> (남)<br>인구수: {abs(val):,}명"
            for age, val in zip(age_labels, male_counts)
        ],
    )
)

# (2) 여자 막대그래프 (오른쪽, 따뜻한 핑크/로즈계열 색상)
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=female_counts,
        name="여자",
        orientation="h",
        marker=dict(color="#EC407A"),  # 따뜻한 딥 핑크
        hoverinfo="text",
        hovertext=[
            f"<b>{age}</b> (여)<br>인구수: {val:,}명"
            for age, val in zip(age_labels, female_counts)
        ],
    )
)

# -----------------------------------------------------------------------------
# 6. 세로축(나이) 순서 고정 및 레이아웃 설정
# -----------------------------------------------------------------------------
fig.update_layout(
    title=dict(
        text=f"<b>{selected_sido} {selected_sigungu} {selected_dong}</b> 인구 피라미드",
        x=0.5,
        xanchor="center",
        font=dict(size=18),
    ),
    barmode="overlay",  # 남/여 막대가 중앙(0) 기준으로 양쪽으로 펼쳐지도록 설정
    bargap=0.1,  # 막대 간격
    height=800,  # 0~100세 이상까지 잘 보이도록 높이 충분히 지정
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5
    ),
    margin=dict(l=60, r=60, t=80, b=40),
    xaxis=dict(
        title="인구수 (명)",
        # 가로축 눈금에 음수 기호(-) 대신 절댓값(양수)으로 표시
        tickvals=[
            -10000,
            -5000,
            -2000,
            -1000,
            -500,
            0,
            500,
            1000,
            2000,
            5000,
            10000,
        ],
        ticktext=[
            "10,000",
            "5,000",
            "2,000",
            "1,000",
            "500",
            "0",
            "500",
            "1,000",
            "2,000",
            "5,000",
            "10,000",
        ],
        zeroline=True,
        zerolinecolor="#757575",
        zerolinewidth=1.5,
    ),
    yaxis=dict(
        title="연령",
        type="category",
        # ⭐ 핵심: 나이 라벨을 0세(맨 아래) ~ 100세 이상(맨 위) 순서 그대로 명시적 고정
        categoryorder="array",
        categoryarray=age_labels,
    ),
    paper_bgcolor="white",
    plot_bgcolor="#F9F9F9",
)

# 스트림릿 화면에 차트 출력
st.plotly_chart(fig, use_container_width=True)
