import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="👨‍👩‍👧‍👦",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 함수 (캐싱 처리로 속도 최적화)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/kay000y/blobs/main/population_ts_yearly_gender (1).zip"
    # 판다스는 zip 압축 파일 URL을 직접 읽을 수 있습니다.
    df = pd.read_csv(url)
    
    # 데이터를 최신 연도로 필터링
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    return df_latest, latest_year

# 데이터 로딩 실행
with st.spinner("데이터를 불러오는 중입니다..."):
    df, latest_year = load_data()

# -----------------------------------------------------------------------------
# 3. 화면 타이틀 및 안내 문구
# -----------------------------------------------------------------------------
st.title("👨‍👩‍👧‍👦 우리 동네 인구 피라미드")
st.caption(f"기준 연도: {latest_year}년 데이터 (출처: 행정안전부 주민등록 인구통계)")
st.write("지역을 선택하시면 해당 동네의 나이별 남녀 인구 피라미드 그래프를 확인하실 수 있습니다.")

st.divider()

# -----------------------------------------------------------------------------
# 4. 필터링 드롭다운 (시도 -> 시군구 -> 동)
# -----------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df['시도'].dropna().unique())
    selected_sido = st.selectbox("1. 시·도 선택", sido_list)

# 선택한 시도에 해당하는 시군구 목록 추출
filtered_sido = df[df['시도'] == selected_sido]

with col2:
    sigungu_list = sorted(filtered_sido['시군구'].dropna().unique())
    selected_sigungu = st.selectbox("2. 시·군·구 선택", sigungu_list)

# 선택한 시군구에 해당하는 동 목록 추출
filtered_sigungu = filtered_sido[filtered_sido['시군구'] == selected_sigungu]

with col3:
    dong_list = sorted(filtered_sigungu['동'].dropna().unique())
    selected_dong = st.selectbox("3. 읍·면·동 선택", dong_list)

# 최종 선택된 1개 행 추출
selected_row = filtered_sigungu[filtered_sigungu['동'] == selected_dong].iloc[0]

# -----------------------------------------------------------------------------
# 5. 인구 피라미드용 데이터 가공
# -----------------------------------------------------------------------------
# 0세부터 100세 이상까지의 연령 라벨 리스트 작성 (순서 고정용)
age_categories = [f"{i}세" for i in range(101)] + ["100세 이상"]
# 100세만 표기 방식에 맞춰 변경 ("100세" -> "100세 이상" 또는 데이터셋 컬럼명 일치)
# 데이터셋의 컬럼명 규격: '남_0세' ~ '남_100세 이상'
age_labels = [f"{i}세" for i in range(100)] + ["100세 이상"]

male_pop = []
female_pop = []

for age in age_labels:
    male_col = f"남_{age}"
    female_col = f"여_{age}"
    
    # 데이터가 없으면 0으로 처리
    m_val = selected_row.get(male_col, 0)
    f_val = selected_row.get(female_col, 0)
    
    male_pop.append(m_val)
    female_pop.append(f_val)

# 남성 인구수는 좌측 배치를 위해 음수로 변환
male_pop_neg = [-val for val in male_pop]

# -----------------------------------------------------------------------------
# 6. Plotly 시각화 (인구 피라미드)
# -----------------------------------------------------------------------------
fig = go.Figure()

# 남성 막대 (왼쪽, 음수 값) - 따뜻한 블루 계열
fig.add_trace(go.Bar(
    y=age_labels,
    x=male_pop_neg,
    name='남자',
    orientation='h',
    customdata=male_pop,  # 툴팁에 양수 표기를 위한 실제값 전달
    hovertemplate='<b>%{y}</b><br>남자 인구: %{customdata:,}명<extra></extra>',
    marker=dict(color='#5B82A6')
))

# 여성 막대 (오른쪽, 양수 값) - 따뜻한 코랄/핑크 계열
fig.add_trace(go.Bar(
    y=age_labels,
    x=female_pop,
    name='여자',
    orientation='h',
    hovertemplate='<b>%{y}</b><br>여자 인구: %{x:,}명<extra></extra>',
    marker=dict(color='#E88A8A')
))

# -----------------------------------------------------------------------------
# 7. 레이아웃 및 세로축 순서 고정 설정
# -----------------------------------------------------------------------------
# X축 최소/최대 범위를 대칭으로 맞추기 위한 계산
max_val = max(max(male_pop), max(female_pop)) * 1.1

fig.update_layout(
    title={
        'text': f"<b>{selected_sido} {selected_sigungu} {selected_dong}</b> 인구 피라미드",
        'font': {'size': 20}
    },
    barmode='overlay', # 남녀 막대 포개기 설정
    bargap=0.1,        # 막대 간격
    xaxis=dict(
        title='인구수 (명)',
        # X축 눈금을 양수로 표시하기 위한 설정
        tickvals=[-int(max_val*0.8), -int(max_val*0.4), 0, int(max_val*0.4), int(max_val*0.8)],
        ticktext=[f"{abs(int(max_val*0.8)):,}", f"{abs(int(max_val*0.4)):,}", "0", f"{int(max_val*0.4):,}", f"{int(max_val*0.8):,}"],
        range=[-max_val, max_val]
    ),
    yaxis=dict(
        title='연령 (세)',
        type='category',              # 카테고리 형태 축으로 지정
        categoryorder='array',        # 축 순서를 우리가 지정한 배열 순서대로 설정
        categoryarray=age_labels,     # 0세가 맨 아래, 100세 이상이 맨 위로 가도록 순서 리스트 전달
        dtick=5                        # 5세 단위로 Y축 눈금 표시
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    ),
    height=800,
    margin=dict(l=60, r=40, t=80, b=40)
)

# Streamlit 화면에 Plotly 그래프 출력
st.plotly_chart(fig, use_container_width=True)
