import streamlit as st
import pdfplumber
import re
import asyncio
import edge_tts
import os

# 페이지 설정
st.set_page_config(
    page_title="🎧 자연스러운 PDF AI 오디오북 변환기",
    page_icon="📖",
    layout="centered"
)

# 1. pdfplumber 텍스트 구어체 정제 함수
def preprocess_pdf_text(raw_text):
    text = raw_text
    
    # 헤더/푸터 및 페이지 번호 제거 (- 1 -, Page 1 등)
    text = re.sub(r'-\s*\d+\s*-', '', text)
    text = re.sub(r'Page\s*\d+(\s*of\s*\d+)?', '', text, flags=re.IGNORECASE)
    
    # 문장 중간의 어색한 줄바꿈(\n) 잇기 (\cdot 이스케이프 수정 완료)
    text = re.sub(r'(?<![\.\?!\:\n])\n(?![\n\d·①-⑩])', ' ', text)
    
    # 소방/기술 단위 및 원문자 기호의 구어체 한글화
    replacements = {
        '㎡': '제곱미터',
        'm²': '제곱미터',
        'dB': '데시벨',
        'MPa': '메가파스칼',
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
        
    # 불필요한 마크다운 및 다중 공백 단일화
    text = re.sub(r'[*\t#_]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# 2. pdfplumber extraction
def extract_clean_text_from_pdf(uploaded_file):
    full_text = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
    raw_full = "\n\n".join(full_text)
    return preprocess_pdf_text(raw_full)

# 3. Async edge-tts 생성 함수
async def generate_tts(text, voice, rate_str, output_file="audiobook.mp3"):
    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    await communicate.save(output_file)

# --- Streamlit UI ---
st.title("🎧 자연스러운 PDF AI 오디오북 변환기")
st.caption("pdfplumber + edge-tts 조합으로 어색한 줄바꿈과 기호를 다듬어 또박또박 낭독하는 오디오북을 만들어 드립니다.")

uploaded_pdf = st.file_uploader("📖 오디오북으로 제작할 PDF 파일을 올려주세요:", type=["pdf"])

col1, col2 = st.columns(2)
with col1:
    voice_choice = st.selectbox("🎙️ 목소리 선택:", ["여성 (SunHi - 추천)", "남성 (InJoon)"])
with col2:
    speed_choice = st.select_slider("⚡ 낭독 속도 (약간 천천히가 또박또박합니다):", options=["-10%", "-5%", "-3%", "0%", "+5%"], value="-3%")

voice_id = "ko-KR-SunHiNeural" if "여성" in voice_choice else "ko-KR-InJoonNeural"

if uploaded_pdf is not None:
    if st.button("🚀 오디오북 MP3 생성하기", type="primary"):
        with st.spinner("📖 PDF 텍스트 추출 및 구어체 정제 진행 중..."):
            clean_text = extract_clean_text_from_pdf(uploaded_pdf)
            
        if not clean_text:
            st.error("⚠️ PDF에서 텍스트를 추출하지 못했습니다. (이미지 스캔 형태의 PDF인지 확인해 주세요)")
        else:
            st.success(f"✅ 텍스트 정제 완료! (총 {len(clean_text):,} 글자)")
            with st.expander("🔍 정제된 텍스트 내용 미리보기"):
                st.write(clean_text[:1000] + ("..." if len(clean_text) > 1000 else ""))
                
            with st.spinner("🎧 신경망 음성 오디오북 생성 중... (분량에 따라 수초~수분이 걸릴 수 있습니다)"):
                output_mp3 = "audiobook.mp3"
                asyncio.run(generate_tts(clean_text, voice_id, speed_choice, output_mp3))
                
            st.success("🎉 오디오북 생성 완료!")
            
            with open(output_mp3, "rb") as f:
                mp3_bytes = f.read()
                
            st.audio(mp3_bytes, format="audio/mp3")
            
            st.download_button(
                label="📥 MP3 오디오북 다운로드",
                data=mp3_bytes,
                file_name=f"{uploaded_pdf.name.replace('.pdf', '')}_오디오북.mp3",
                mime="audio/mp3"
            )
