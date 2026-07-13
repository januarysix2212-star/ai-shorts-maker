import streamlit as st
from google import genai
from moviepy.editor import VideoFileClip
import os
import json
import re

# --- 웹 페이지 설정 ---
st.set_page_config(page_title="AI 유튜브 쇼츠 메이커", page_icon="🎬", layout="wide")

with st.sidebar:
    st.header("⚙️ 기본 설정")
    api_key = st.text_input("Gemini API 키를 입력하세요:", type="password")
    st.markdown("[🔑 구글 AI 스튜디오에서 키 발급받기](https://aistudio.google.com/)")

st.title("🎬 AI 쇼츠 메이커 (파일 업로드 버전)")
st.markdown("직접 다운로드한 **영상 파일**을 올리면, AI가 하이라이트 컷편집과 다국어 자막(.srt)을 만들어 줍니다!")
st.divider()

# --- 자막 시간 변환 함수 ---
def format_time_srt(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds * 1000) % 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

# --- 자막 파일 생성 함수 ---
def create_srt_file(subtitles_data, filename, lang="ko"):
    srt_content = ""
    for i, sub in enumerate(subtitles_data):
        start_time = format_time_srt(sub["start"])
        end_time = format_time_srt(sub["end"])
        text = sub["ko_text"] if lang == "ko" else sub["ja_text"]
        srt_content += f"{i+1}\n{start_time} --> {end_time}\n{text}\n\n"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(srt_content)
    return filename

# --- 메인 실행 화면 (파일 업로드 방식) ---
uploaded_video = st.file_uploader("쇼츠로 만들 영상 파일(.mp4)을 업로드해 주세요:", type=["mp4", "mov"])

if st.button("🚀 전체 자동화 시작!"):
    if not api_key:
        st.error("앗! 왼쪽 사이드바에 Gemini API 키를 먼저 입력해 주세요.")
    elif not uploaded_video:
        st.error("영상 파일을 먼저 업로드해 주세요!")
    else:
        try:
            status_text = st.empty()
            
            # 1. 업로드된 파일을 서버에 임시 저장
            status_text.info("1/3: 업로드하신 영상을 준비하는 중입니다... 📥")
            video_file_path = "temp_video.mp4"
            with open(video_file_path, "wb") as f:
                f.write(uploaded_video.read())
            
            # 2. 제미나이 AI 분석 (최신 SDK 적용)
            status_text.info("2/3: 제미나이 AI가 영상을 분석하고 기획안을 작성 중입니다... 🧠 (최대 2~3분 소요)")
            
            client = genai.Client(api_key=api_key)
            uploaded_file_ai = client.files.upload(file=video_file_path)
            
            prompt = """
            당신은 천재적인 쇼츠 기획자입니다. 첨부된 영상을 보고 가장 웃기거나 흥미로운 30초~1분 사이의 하이라이트 구간 1개를 찾아주세요.
            반드시 아래의 JSON 형식으로만 답변을 출력해야 합니다. 마크다운이나 다른 텍스트는 절대 넣지 마세요.
            {
                "start_time": 구간시작초(숫자, 예: 12),
                "end_time": 구간종료초(숫자, 예: 45),
                "titles": ["후킹제목1", "후킹제목2", "후킹제목3"],
                "direction": "이 구간을 어떻게 편집하면 좋을지 재밌는 연출 아이디어",
                "subtitles": [
                    {"start": 0, "end": 4, "ko_text": "첫 번째 한국어 대본", "ja_text": "첫 번째 일본어 대본"}
                ]
            }
            주의: subtitles의 start와 end는 원본 영상 기준이 아니라 '잘라낸 쇼츠 영상' 기준(0초부터 시작)으로 작성하세요. 4초 간격으로 나눠주세요.
            """
            
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=[uploaded_file_ai, prompt]
            )
            client.files.delete(name=uploaded_file_ai.name)
            
            # 3. AI 결과물 해석 및 컷편집
            status_text.info("3/3: AI 기획안을 바탕으로 영상을 컷편집 중입니다... ✂️")
            raw_text = response.text
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                ai_data = json.loads(json_match.group(0))
            else:
                raise ValueError("AI가 올바른 형식으로 응답하지 않았습니다. 다시 시도해주세요.")

            start_t = ai_data["start_time"]
            end_t = ai_data["end_time"]
            
            final_video_name = "shorts_final.mp4"
            with VideoFileClip(video_file_path) as video:
                shorts_clip = video.subclip(start_t, end_t)
                shorts_clip.write_videofile(final_video_name, codec="libx264", audio_codec="aac", temp_audiofile="temp-audio.m4a", remove_temp=True, logger=None)
            
            # 4. 자막 파일 생성
            ko_srt = create_srt_file(ai_data["subtitles"], "korean_sub.srt", "ko")
            ja_srt = create_srt_file(ai_data["subtitles"], "japanese_sub.srt", "ja")
            
            # --- 결과 화면 출력 ---
            status_text.empty()
            st.success("🎉 모든 작업이 완료되었습니다! 아래에서 결과를 확인하고 다운로드하세요.")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("💡 AI 쇼츠 기획안")
                st.write("**🔥 추천 후킹 제목:**")
                for t in ai_data["titles"]:
                    st.write(f"- {t}")
                st.write(f"**🎬 연출 아이디어:** {ai_data['direction']}")
                
            with col2:
                st.subheader("📥 파일 다운로드")
                with open(final_video_name, "rb") as v_file:
                    st.download_button("🎥 쇼츠 영상 다운로드", data=v_file, file_name="shorts_video.mp4", mime="video/mp4")
                with open(ko_srt, "rb") as k_file:
                    st.download_button("🇰🇷 한국어 자막 다운로드 (.srt)", data=k_file, file_name="korean_subtitles.srt", mime="text/plain")
                with open(ja_srt, "rb") as j_file:
                    st.download_button("🇯🇵 일본어 자막 다운로드 (.srt)", data=j_file, file_name="japanese_subtitles.srt", mime="text/plain")

            # 임시 파일 삭제
            if os.path.exists(video_file_path):
                os.remove(video_file_path)

        except Exception as e:
            st.error(f"실행 중 오류가 발생했습니다: {e}")
