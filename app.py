import asyncio
import os
import re
import edge_tts
import pdfplumber
import streamlit as st

# 페이지 설정
st.set_page_config(
    page_title="🎧 소방 특화 PDF AI 오디오북 변환기",
    page_icon="📖",
    layout="centered",
)


# 1. 소방/법령/기출 특화 대본 정제 알고리즘
def preprocess_pdf_text(raw_text):
  text = raw_text

  # ① 시험지/법령 불필요 헤더, 푸터 및 쪽 번호 제거
  text = re.sub(r'한국산업인력공단|청렴\s*한\s*세상|안전\s*한\s*세상', '', text)
  text = re.sub(
      r'-\s*\d+\s*-', '', text
  )  # - 1 - 형태의 페이지 번호
  text = re.sub(
      r'Page\s*\d+(\s*of\s*\d+)?', '', text, flags=re.IGNORECASE
  )
  text = re.sub(
      r'\\(\s*\d+\s*-\s*\d+\s*\\)', '', text
  )  # ( 6-1 ), ( 6-2 ) 형태 시험지 번호

  # ② 법령 공고문, 개정 이력, 부칙 행정 문구 제거
  text = re.sub(r'\\[시행\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\\]', '', text)
  text = re.sub(r'\\[국립소방연구원공고\s*제\d{4}-\d+호[^\\]]*\]', '', text)
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
st.title('🎧 소방 특화 PDF AI 오디오북 변환기')
st.caption(
    '법령 공고문, 개정 이력, 단위(m³, kPa) 및 문장 줄바꿈을 깔끔하게 정제하여'
    ' 성우처럼 자연스럽게 낭독합니다.'
)

uploaded_pdf = st.file_uploader(
    '📖 오디오북으로 제작할 PDF 파일을 올려주세요:', type=['pdf']
)

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

if uploaded_pdf is not None:
  if st.button('🚀 고품질 오디오북 MP3 생성하기', type='primary'):
    with st.spinner(
        '📖 PDF 텍스트 추출 및 대본 정제 진행 중 (법령/기초 단위 한글화)...'
    ):
      clean_text = extract_clean_text_from_pdf(uploaded_pdf)

    if not clean_text:
      st.error(
          '⚠️ PDF에서 텍스트를 추출하지 못했습니다. (스캔된 이미지형'
          ' PDF인지 확인해 주세요)'
      )
    else:
      st.success(f'✅ 대본 정제 완료! (총 {len(clean_text):,} 글자)')
      with st.expander('🔍 정제된 오디오북 대본 미리보기'):
        st.write(
            clean_text[:1200] + ('...' if len(clean_text) > 1200 else '')
        )

      with st.spinner(
          '🎧 신경망 음성 오디오북 생성 중... (분량에 따라 수초~수분이 걸릴 수'
          ' 있습니다)'
      ):
        output_mp3 = 'audiobook.mp3'
        asyncio.run(
            generate_tts(clean_text, voice_id, speed_choice, output_mp3)
        )

      st.success('🎉 고품질 오디오북 생성 완료!')

      with open(output_mp3, 'rb') as f:
        mp3_bytes = f.read()

      st.audio(mp3_bytes, format='audio/mp3')

      st.download_button(
          label='📥 MP3 오디오북 다운로드',
          data=mp3_bytes,
          file_name=f"{uploaded_pdf.name.replace('.pdf', '')}_소방오디오북.mp3",
          mime='audio/mp3',
      )
