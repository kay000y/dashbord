import plotly.graph_objects as go
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 스타일 정의
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="우리 동네 인구 피라미드", page_icon="👨‍👩‍👧‍👦", layout="centered"
)

# 따뜻하고 친근한 분위기를 위한 타이틀
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
# 0세부터 99세까지 + 100세 이상 순서대로 나이 라벨 리스트 생성
age_labels = [f"{i}세" for i in range(100)] + ["100세 이상"]

male_counts = []
female_counts = []

# 각 연령대별 대표 나이 값 (평균 연령 계산용, 100세 이상은 100세로 계산)
age_values = list(range(100)) + [100]

total_population = 0  # 총인구
weighted_age_sum = 0  # (나이 * 인구수) 누적합 (평균 연령 계산용)
elderly_population = 0  # 65세 이상 인구
youth_population = 0  # 14세 이하 인구 (어린이 인구)

for idx, age in enumerate(age_labels):
    male_col = f"남_{age}"
    female_col = f"여_{age}"

    m_val = int(target_row.get(male_col, 0))
    f_val = int(target_row.get(female_col, 0))
    pop_at_age = m_val + f_val  # 해당 나이의 남녀 총 인구수

    # 지표 산출용 통계 누적
    total_population += pop_at_age
    weighted_age_sum += age_values[idx] * pop_at_age

    # 65세 이상 어르신 인구 집계
    if age_values[idx] >= 65:
        elderly_population += pop_at_age

    # 14세 이하 어린이/청소년 인구 집계
    if age_values[idx] <= 14:
        youth_population += pop_at_age

    # 피라미드 그래프용 (남자는 왼쪽에 둘 것이므로 음수 값 처리)
    male_counts.append(-abs(m_val))
    female_counts.append(f_val)

# 지표 계산 (0으로 나누는 예외 방지)
mean_age = (
    weighted_age_sum / total_population if total_population > 0 else 0.0
)
elderly_ratio = (
    (elderly_population / total_population) * 100
    if total_population > 0
    else 0.0
)
youth_ratio = (
    (youth_population / total_population) * 100
    if total_population > 0
    else 0.0
)


# -----------------------------------------------------------------------------
# 5. 상단 주요 지표 카드 (st.metric)
# -----------------------------------------------------------------------------
st.write("---")
m_col1, m_col2, m_col3 = st.columns(3)

with m_col1:
    st.metric(label="👥 총인구", value=f"{total_population:,} 명")

with m_col2:
    st.metric(label="🎂 평균연령", value=f"{mean_age:.1f} 세")

with m_col3:
    # 고령화율 20% 이상인 초고령사회 지역이면 주의 경고 표시 붙임
    if elderly_ratio >= 20.0:
        st.metric(
            label="👵 고령화율 (65세+)",
            value=f"{elderly_ratio:.1f} %",
            delta="⚠️ 초고령사회 (20% 이상)",
            delta_color="inverse",
        )
    else:
        st.metric(
            label="👵 고령화율 (65세+)",
            value=f"{elderly_ratio:.1f} %",
        )

st.write("---")


# -----------------------------------------------------------------------------
# 6. Plotly 가로 막대그래프(인구 피라미드) 생성
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
# 7. 세로축(나이) 순서 고정 및 레이아웃 설정
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
    height=800,  # 0~100세 이상까지 잘 보이도록 높이 설정
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5
    ),
    margin=dict(l=60, r=60, t=80, b=40),
    xaxis=dict(
        title="인구수 (명)",
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
        # ⭐ 나이 라벨을 0세(맨 아래) ~ 100세 이상(맨 위) 순서 그대로 고정
        categoryorder="array",
        categoryarray=age_labels,
    ),
    paper_bgcolor="white",
    plot_bgcolor="#F9F9F9",
)

# 스트림릿 화면에 차트 출력
st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
# 8. 동네 특성 자동 한 줄 진단 안내 문구
# -----------------------------------------------------------------------------
# 14세 이하 비율과 65세 이상 비율을 비교하여 진단 문구 생성
if youth_ratio > elderly_ratio:
    analysis_text = f"🎈 **{selected_dong}**은(는) 어르신 비율({elderly_ratio:.1f}%)보다 **유아·청소년 비율({youth_ratio:.1f}%)이 더 높아 아이들이 상대적으로 많은 활기찬 동네**입니다."
elif elderly_ratio >= 20.0:
    analysis_text = f"🌾 **{selected_dong}**은(는) 고령화율이 **{elderly_ratio:.1f}%**로 **65세 이상 어르신 비중이 높은 편**입니다."
else:
    analysis_text = f"🏡 **{selected_dong}**은(는) 유아·청소년 비율({youth_ratio:.1f}%)과 어르신 비율({elderly_ratio:.1f}%)이 **균형을 이루고 있는 동네**입니다."

st.info(analysis_text)
