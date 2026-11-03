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

# 🎙️ 검증된 안정적인 목소리 후보 딕셔너리
FEMALE_VOICES = {
    "SunHi (안정적이고 또박또박한 톤)": "ko-KR-SunHiNeural",
    "JiMin (부드럽고 자연스러운 톤)": "ko-KR-JiMinNeural",
}

MALE_VOICES = {
    "InJoon (신뢰감 있고 묵직한 톤)": "ko-KR-InJoonNeural",
    "HyunSu (차분하고 깔끔한 톤)": "ko-KR-HyunSuNeural",
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
    text = re.sub(r"\\((가|나|다|라|마|바|사|아)\\)", r"\1번, ", text)

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
st.write("AI가 정제해준 대본을 붙여넣거나, 소방 PDF를 올리면 성우처럼 매끄러운 MP3 오디오북을 만들어 드립니다.")

tab_text, tab_pdf = st.tabs(["대본 텍스트 붙여넣기", "PDF 파일 직접 업로드"])

final_text = ""

with tab_text:
    pasted_text = st.text_area(
        "낭독용 대본을 여기에 붙여넣으세요 (남녀 교대 시 [여성] / [남성] 태그 포함):",
        height=280,
        placeholder="[여성] 소화기구 및 자동소화장치의 화재안전기술기준 낭독을 시작합니다...\n\n[남성] 네, 주요 용어를 살펴보겠습니다."
    )
    if pasted_text.strip():
        final_text = pasted_text.strip()

with tab_pdf:
    uploaded_pdf = st.file_uploader("오디오북으로 만들 PDF 파일:", type=["pdf"])
    if uploaded_pdf is not None:
        if st.button("PDF에서 대본 추출하기"):
            with st.spinner("PDF 텍스트 추출 중..."):
                st.session_state["pdf_extracted_text"] = extract_clean_text_from_pdf(uploaded_pdf)
                st.success("PDF 대본 추출 완료!")

        if "pdf_extracted_text" in st.session_state:
            final_text = st.session_state["pdf_extracted_text"]
            with st.expander("추출된 대본 확인하기"):
                st.write(final_text[:1000] + ("..." if len(final_text) > 1000 else ""))

# --- 옵션 설정 영역 ---
st.write("---")
st.subheader("목소리 및 재생 설정")

mode_choice = st.radio(
    "재생 모드 선택:",
    ["여성 단독 낭독", "남성 단독 낭독", "남녀 교대 대화"],
    horizontal=True,
)

selected_female_voice = "ko-KR-SunHiNeural"
selected_male_voice = "ko-KR-InJoonNeural"

if mode_choice == "여성 단독 낭독":
    f_choice_name = st.selectbox("여성 목소리 선택", list(FEMALE_VOICES.keys()))
    selected_female_voice = FEMALE_VOICES[f_choice_name]

elif mode_choice == "남성 단독 낭독":
    m_choice_name = st.selectbox("남성 목소리 선택", list(MALE_VOICES.keys()))
    selected_male_voice = MALE_VOICES[m_choice_name]

else:
    st.markdown("💡 **남녀 교대 모드**입니다. 대본 내에 `[여성]` 또는 `[남성]` 태그가 포함되어 있어야 각각의 목소리로 교대 낭독됩니다.")
    col_f, col_m = st.columns(2)
    with col_f:
        f_choice_name = st.selectbox("여성 성우", list(FEMALE_VOICES.keys()))
        selected_female_voice = FEMALE_VOICES[f_choice_name]
    with col_m:
        m_choice_name = st.selectbox("남성 성우", list(MALE_VOICES.keys()))
        selected_male_voice = MALE_VOICES[m_choice_name]

speed_choice = st.select_slider(
    "낭독 속도:",
    options=["-10%", "-5%", "-3%", "+0%", "+5%"],
    value="-3%",
)

# MP3 생성 버튼
if st.button("고품질 오디오북 MP3 생성하기", type="primary"):
    if not final_text:
        st.warning("텍스트를 입력하거나 PDF를 먼저 올려주세요!")
    else:
        with st.spinner("오디오북 생성 중..."):
            output_mp3 = "audiobook.mp3"

            try:
                if mode_choice == "여성 단독 낭독":
                    run_generate_tts(final_text, selected_female_voice, speed_choice, output_mp3)

                elif mode_choice == "남성 단독 낭독":
                    run_generate_tts(final_text, selected_male_voice, speed_choice, output_mp3)

                else:
                    pattern = re.compile(r"\[(남성|여성|남|여)\]\s*(.*?)(?=\[(?:남성|여성|남|여)\]|$)", re.DOTALL)
                    matches = pattern.findall(final_text)

                    if not matches:
                        run_generate_tts(final_text, selected_female_voice, speed_choice, output_mp3)
                    else:
                        temp_files = []
                        success_gen = True
                        import tempfile

                        for speaker, text_block in matches:
                            text_block = text_block.strip()
                            if not text_block:
                                continue

                            v_choice = selected_male_voice if speaker in ["남성", "남"] else selected_female_voice

                            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
                            os.close(tmp_fd)
                            temp_files.append(tmp_path)

                            try:
                                run_generate_tts(text_block, v_choice, speed_choice, tmp_path)
                            except Exception as e:
                                success_gen = False
                                st.error(f"음성 조각 생성 오류: {e}")
                                break

                        if success_gen and len(temp_files) > 0:
                            list_file_path = "filelist.txt"
                            with open(list_file_path, "w", encoding="utf-8") as lf:
                                for tp in temp_files:
                                    escaped_path = tp.replace("\\", "/")
                                    lf.write(f"file '{escaped_path}'\n")

                            cmd = [
                                "ffmpeg",
                                "-y",
                                "-f",
                                "concat",
                                "-safe",
                                "0",
                                "-i",
                                list_file_path,
                                "-c",
                                "copy",
                                output_mp3,
                            ]
                            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                            if os.path.exists(list_file_path):
                                os.remove(list_file_path)

                        for tp in temp_files:
                            if os.path.exists(tp):
                                try:
                                    os.remove(tp)
                                except:
                                    pass

                st.success("오디오북 생성 완료!")

                with open(output_mp3, "rb") as f:
                    mp3_bytes = f.read()

                st.audio(mp3_bytes, format="audio/mp3")

                st.download_button(
                    label="MP3 다운로드",
                    data=mp3_bytes,
                    file_name="audiobook.mp3",
                    mime="audio/mp3",
                )
            except Exception as e:
                st.error(f"오류 발생: {e}")
