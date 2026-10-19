import asyncio
import os
import re
import edge_tts
import pdfplumber
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="🎧 소방 특화 PDF/대본 AI 오디오북 변환기",
    page_icon="📖",
    layout="centered",
)


# 1. 소방/법령/기출 특화 대본 정제 알고리즘
def preprocess_pdf_text(raw_text):
  text = raw_text

  # ① 시험지/법령 불필요 헤더, 푸터 및 쪽 번호 제거
  text = re.sub(r'한국산업인력공단|청렴\s*한\s*세상|안전\s*한\s*세상', '', text)
  text = re.sub(r'-\s*\d+\s*-', '', text)
  text = re.sub(
      r'Page\s*\d+(\s*of\s*\d+)?', '', text, flags=re.IGNORECASE
  )
  text = re.sub(r'\\(\s*\d+\s*-\s*\d+\s*\\)', '', text)

  # ② 법령 공고문, 개정 이력, 부칙 행정 문구 제거
  text = re.sub(r'\\[시행\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\\]', '', text)
  text = re.sub(r'\\[국립소방연구원공고[^\\]]*\]', '', text)
  text = re.sub(
      r'<\s*개정\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*>', '', text
  )
  text = re.sub(
      r'<\s*신설\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*>', '', text
  )

  # ③ 문제 번호 및 항목 기호 구어체 가공
  text = re.sub(r'【\s*문제\s*(\d+)\s*】', r'문제 \1번.', text)
  text = re.sub(r'\\((가|나|다|라|마|바|사|아)\\)', r'\1번, ', text)

  # ④ 소방 기술 단위 및 원문자 구어체 한글화
  replacements = {
      'm³': '세제곱미터',
      'm3': '세제곱미터',
      '㎡': '제곱미터',
      'm2': '제곱미터',
      'kPa': '킬로파스칼',
      'MPa': '메가파스칼',
      'ℓ': '리터',
      'dB': '데시벨',
      '℃': '섭씨',
      '~': '에서 ',
      '①': '첫째, ',
      '②': '둘째, ',
      '③': '셋째, ',
      '④': '넷째, ',
      '⑤': '다섯째, ',
      '⑥': '여섯째, ',
      '⑦': '일곱째, ',
      '⑧': '여덟째, ',
      '⑨': '아홉째, ',
      '⑩': '열째, ',
  }
  for orig, rep in replacements.items():
    text = text.replace(orig, rep)

  # ⑤ 문장 중간의 어색한 줄바꿈(\n) 잇기
  text = re.sub(r'(?<![\.\?!\:\n])\n(?![\n\d·①-⑩])', ' ', text)

  # ⑥ 불필요한 기호 및 다중 공백 정리
  text = re.sub(r'[*\t#_]', ' ', text)
  text = re.sub(r'\s+', ' ', text).strip()

  return text


# 2. pdfplumber 텍스트 추출
def extract_clean_text_from_pdf(uploaded_file):
  full_text = []
  with pdfplumber.open(uploaded_file) as pdf:
    for page in pdf.pages:
      text = page.extract_text()
      if text:
        full_text.append(text)
  raw_full = '\n\n'.join(full_text)
  return preprocess_pdf_text(raw_full)


# 3. Async edge-tts 음성 생성
async def generate_tts(text, voice, rate_str, output_file='audiobook.mp3'):
  communicate = edge_tts.Communicate(text, voice, rate=rate_str)
  await communicate.save(output_file)


# --- Streamlit UI ---
st.title('🎧 소방 특화 AI 오디오북 변환기')
st.caption(
    'AI가 정제해준 대본을 붙여넣거나, 소방 PDF를 올리면 성우처럼 매끄러운'
    ' MP3 오디오북을 만들어 드립니다.'
)

# 탭을 통해 두 가지 입력 방식 제공
tab_text, tab_pdf = st.tabs(
    ['✍️ 대본 텍스트 붙여넣기 (추천)', '📄 PDF 파일 직접 업로드']
)

final_text = ''

with tab_text:
  pasted_text = st.text_area(
      '📋 AI가 가공해준 낭독용 대본을 여기에 붙여넣으세요:',
      height=280,
      placeholder=(
          '소화기구 및 자동소화장치의 화재안전기술기준 낭독을 시작합니다...\n\n제1장.'
          ' 주요 용어의 정의...'
      ),
  )
  if pasted_text.strip():
    final_text = pasted_text.strip()

with tab_pdf:
  uploaded_pdf = st.file_uploader(
      '📖 오디오북으로 만들 PDF 파일:', type=['pdf']
  )
  if uploaded_pdf is not None:
    if st.button('🔍 PDF에서 대본 추출하기'):
      with st.spinner('PDF 텍스트 추출 및 구어체 정제 중...'):
        st.session_state['pdf_extracted_text'] = extract_clean_text_from_pdf(
            uploaded_pdf
        )
        st.success('PDF 대본 추출 완료!')

    if 'pdf_extracted_text' in st.session_state:
      final_text = st.session_state['pdf_extracted_text']
      with st.expander('🔍 추출된 대본 확인하기'):
        st.write(
            final_text[:1000] + ('...' if len(final_text) > 1000 else '')
        )

# 옵션 설정
st.write('---')
col1, col2 = st.columns(2)
with col1:
  voice_choice = st.selectbox(
      '🎙️ 목소리 선택:', ['여성 (SunHi - 추천)', '남성 (InJoon)']
  )
with col2:
  speed_choice = st.select_slider(
      '⚡ 낭독 속도 (약간 천천히가 또박또박합니다):',
      options=['-10%', '-5%', '-3%', '0%', '+5%'],
      value='-3%',
  )

voice_id = (
    'ko-KR-SunHiNeural' if '여성' in voice_choice else 'ko-KR-InJoonNeural'
)

# MP3 생성 버튼
if st.button('🚀 고품질 오디오북 MP3 생성하기', type='primary'):
  if not final_text:
    st.warning(
        '⚠️ 텍스트 입력창에 대본을 붙여넣거나 PDF 파일에서 대본을 추출해'
        ' 주세요!'
    )
  else:
    with st.spinner(
        '🎧 신경망 음성 오디오북 생성 중... (분량에 따라 수초~수분이 걸릴 수'
        ' 있습니다)'
    ):
      output_mp3 = 'audiobook.mp3'
      asyncio.run(generate_tts(final_text, voice_id, speed_choice, output_mp3))

    st.success('🎉 고품질 오디오북 생성 완료!')

    with open(output_mp3, 'rb') as f:
      mp3_bytes = f.read()

    st.audio(mp3_bytes, format='audio/mp3')

    st.download_button(
        label='📥 MP3 오디오북 다운로드',
        data=mp3_bytes,
        file_name='소방시설관리사_오디오북.mp3',
        mime='audio/mp3',
    )
