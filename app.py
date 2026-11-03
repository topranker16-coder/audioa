import os
import re
import subprocess
import edge_tts
import pdfplumber
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="소방 특화 AI 오디오북 변환기",
    page_icon="📖",
    layout="centered",
)

# 사용 가능한 목소리 후보 딕셔너리
FEMALE_VOICES = {
    "SunHi (차분하고 안정적인 여성 톤)": "ko-KR-SunHiNeural",
    "JiMin (부드럽고 자연스러운 여성 톤)": "ko-KR-JiMinNeural",
    "SeoHyeon (밝고 친근한 여성 톤)": "ko-KR-SeoHyeonNeural",
}

MALE_VOICES = {
    "InJoon (신뢰감 있고 묵직한 남성 톤)": "ko-KR-InJoonNeural",
    "HyunSu (차분하고 깔끔한 남성 톤)": "ko-KR-HyunSuNeural",
}


# 1. 소방/법령/기출 특화 대본 정제 알고리즘
def preprocess_pdf_text(raw_text):
    text = raw_text
    text = re.sub(r"한국산업인력공단|청렴\s*한\s*세상|안전\s*한\s*세상", "", text)
    text = re.sub(r"-\s*\d+\s*-", "", text)
    text = re.sub(r"Page\s*\d+(\s*of\s*\d+)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\\(\s*\d+\s*-\s*\d+\s*\\)", "", text)
    text = re.sub(r"\\[시행\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\\]", "", text)
    text = re.sub(r"\\[국립소방연구원공고[^\\]]*\\]", "", text)
    text = re.sub(r"<\s*개정\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*>", "", text)
    text = re.sub(r"<\s*신설\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*>", "", text)
    text = re.sub(r"【\s*문제\s*(\d+)\s*】", r"문제 \1번.", text)
    text = re.sub(r"\\((가\vert{}나\vert{}다\vert{}라\vert{}마\vert{}바\vert{}사\vert{}아)\\)", r"\1번, ", text)

    replacements = {
        "m³": "세제곱미터",
        "m3": "세제곱미터",
        "㎡": "제곱미터",
        "m2": "제곱미터",
        "kPa": "킬로파스칼",
        "MPa": "메가파스칼",
        "ℓ": "리터",
        "dB": "데시벨",
        "℃": "섭씨",
        "~": "에서 ",
        "①": "첫째, ",
        "②": "둘째, ",
        "③": "셋째, ",
        "④": "넷째, ",
        "⑤": "다섯째, ",
        "⑥": "여섯째, ",
        "⑦": "일곱째, ",
        "⑧": "여덟째, ",
        "⑨": "아홉째, ",
        "⑩": "열째, ",
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)

    text = re.sub(r"(?<![\.\?!\:\n])\n(?![\n\d·①-⑩])", " ", text)
    text = re.sub(r"[*\t#_]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_clean_text_from_pdf(uploaded_file):
    full_text = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
    raw_full = "\n\n".join(full_text)
    return preprocess_pdf_text(raw_full)


# 2. 안전한 동기식 edge-tts 실행 함수 (재시도 로직 포함)
def run_generate_tts(text, voice, rate_str, output_file):
    import asyncio
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate_str)
            try:
                asyncio.run(communicate.save(output_file))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(communicate.save(output_file))
                loop.close()
            return
        except Exception as e:
            if attempt == 2:
                raise e
            import time
            time.sleep(1)


# --- Streamlit UI ---
st.title("소방 특화 AI 오디오북 변환기")
st.write(
    "AI가 정제해준 대본을 붙여넣거나, 소방 PDF를 올리면 성우처럼 매끄러운"
    " MP3 오디오북을 만들어 드립니다."
)

tab_text, tab_pdf = st.tabs(["대본 텍스트 붙여넣기 (추천)", "PDF 파일 직접 업로드"])

final_text = ""

with tab_text:
    pasted_text = st.text_area(
        "AI가 가공해준 낭독용 대본을 여기에 붙여넣으세요:",
        height=280,
        placeholder=(
            "[여성] 소화기구 및 자동소화장치의 화재안전기술기준 낭독을 시작합니다...\n\n[남성]"
            " 네, 제1장 주요 용어의 정의를 살펴보겠습니다."
        ),
    )
    if pasted_text.strip():
        final_text = pasted_text.strip()

with tab_pdf:
    uploaded_pdf = st.file_uploader(
        "오디오북으로 만들 PDF 파일:", type=["pdf"]
    )
    if uploaded_pdf is not None:
        if st.button("PDF에서 대본 추출하기"):
            with st.spinner("PDF 텍스트 추출 및 구어체 정제 중..."):
                st.session_state["pdf_extracted_text"] = (
                    extract_clean_text_from_pdf(uploaded_pdf)
                )
                st.success("PDF 대본 추출 완료!")

        if "pdf_extracted_text" in st.session_state:
            final_text = st.session_state["pdf_extracted_text"]
            with st.expander("추출된
