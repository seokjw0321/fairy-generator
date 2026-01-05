import json
import os
import glob
import numpy as np
import multiprocessing
import azure.cognitiveservices.speech as speechsdk
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# -------------------------------------------------------------------------
# [초기 설정] 환경변수 및 폰트 로드
# -------------------------------------------------------------------------
load_dotenv()

# ★ 폰트 경로 설정 (Windows: 맑은 고딕 / Mac: AppleSDGothicNeo 등)
# 파일이 실제로 존재하는지 꼭 확인하세요!
FONT_PATH = "C:/Windows/Fonts/malgun.ttf"  
# FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc" # Mac 예시

# 자막 디자인 설정
SUBTITLE_FONT_SIZE = 45
TITLE_FONT_SIZE = 80
SUBTITLE_COLOR = "white"
SUBTITLE_BG_COLOR = (0, 0, 0, 160) # 반투명 검정 박스 (R, G, B, Alpha)

# 한 화면에 보여줄 최대 글자 수 (이걸 넘으면 다음 자막으로 분할)
MAX_CHARS_PER_SCREEN = 40  

# Azure Speech API 키
SPEECH_KEY = os.getenv("SPEECH_KEY")
SPEECH_REGION = os.getenv("SPEECH_REGION")

# -------------------------------------------------------------------------
# [함수 1] PIL을 이용한 텍스트 이미지 생성 (정렬/줄바꿈 완벽 해결)
# -------------------------------------------------------------------------
def create_text_clip_pil(text, font_path, font_size, color, bg_color=None, duration=1, size=(1792, 1024), pos='center'):
    """
    MoviePy TextClip 대신 PIL로 텍스트 이미지를 그려서 반환합니다.
    - 중앙 정렬 완벽 지원
    - 배경 박스 자동 크기 조절
    - 글자 테두리(Stroke) 지원
    """
    W, H = size
    
    # 1. 폰트 로드
    try:
        font = ImageFont.truetype(font_path, font_size)
    except OSError:
        print(f"⚠️ 폰트 로드 실패({font_path}). 기본 폰트를 사용합니다.")
        font = ImageFont.load_default()
    
    # 빈 투명 이미지 생성
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 2. 시각적 줄바꿈 (화면 너비 85% 넘어가면 강제 개행)
    max_width_px = W * 0.85
    visual_lines = []
    
    # 입력된 텍스트가 이미 줄바꿈이 되어 있을 수도 있으므로 split('\n') 처리
    for paragraph in text.split('\n'):
        words = paragraph.split()
        current_line = []
        
        for word in words:
            # "현재 줄 + 새 단어" 길이를 미리 측정
            test_line = " ".join(current_line + [word])
            line_w = font.getbbox(test_line)[2] # getbbox의 3번째 값이 width
            
            if line_w <= max_width_px:
                current_line.append(word)
            else:
                # 넘치면 현재 줄 저장하고 다음 줄로 이동
                visual_lines.append(" ".join(current_line))
                current_line = [word]
        
        if current_line:
            visual_lines.append(" ".join(current_line))

    # 3. 텍스트 전체 높이 및 좌표 계산
    # 한 줄 높이 계산 (한글 기준)
    ascent, descent = font.getmetrics()
    line_height = ascent + descent + 10 # 여유분 10px
    total_text_h = line_height * len(visual_lines)
    
    # Y 좌표 결정
    if pos == 'center':
        y = (H - total_text_h) / 2
    elif pos == 'bottom':
        y = H - total_text_h - 100 # 바닥에서 100px 위
    else:
        y = 100

    # 4. 배경 박스 그리기 (텍스트가 있을 경우만)
    if bg_color and text.strip():
        max_line_w = 0
        for line in visual_lines:
            w = font.getbbox(line)[2]
            if w > max_line_w: max_line_w = w
            
        padding = 20
        # 박스 좌표 계산 (중앙 정렬 기준)
        bx1 = (W - max_line_w) / 2 - padding
        by1 = y - padding
        bx2 = (W + max_line_w) / 2 + padding
        by2 = y + total_text_h + padding - 5
        
        draw.rectangle([bx1, by1, bx2, by2], fill=bg_color)

    # 5. 텍스트 그리기 (테두리 포함)
    cur_y = y
    for line in visual_lines:
        w = font.getbbox(line)[2]
        x = (W - w) / 2 # ★ 수동 중앙 정렬 계산
        
        # 검은색 테두리 (Stroke) 효과 - 4방향으로 그려서 구현
        stroke_width = 2
        for off_x in range(-stroke_width, stroke_width+1):
            for off_y in range(-stroke_width, stroke_width+1):
                 draw.text((x+off_x, cur_y+off_y), line, font=font, fill="black")
        
        # 메인 텍스트
        draw.text((x, cur_y), line, font=font, fill=color)
        cur_y += line_height

    # 6. Numpy 배열로 변환하여 ImageClip 생성
    return ImageClip(np.array(img)).set_duration(duration)

# -------------------------------------------------------------------------
# [함수 2] 자막 시간 분배 로직 (어절 단위 분할)
# -------------------------------------------------------------------------
def split_subtitle_chunks(text, total_duration, max_chars=40):
    """
    긴 문장을 어절 단위로 끊어서 max_chars를 넘지 않게 덩어리로 나눔.
    시간은 글자 수에 비례하여 배분.
    """
    words = text.split()
    chunks = []
    
    current_chunk_words = []
    current_len = 0
    
    # 1. 텍스트 덩어리 나누기
    for word in words:
        word_len = len(word)
        if current_len + word_len + 1 <= max_chars:
            current_chunk_words.append(word)
            current_len += word_len + 1
        else:
            if current_chunk_words:
                chunks.append(" ".join(current_chunk_words))
            current_chunk_words = [word]
            current_len = word_len + 1
            
    if current_chunk_words:
        chunks.append(" ".join(current_chunk_words))
    
    if not chunks:
        return []

    # 2. 시간 배분 (글자 수 비례)
    total_char_count = sum(len(c.replace(" ", "")) for c in chunks)
    if total_char_count == 0: total_char_count = 1
    
    result = []
    for chunk_text in chunks:
        chunk_len = len(chunk_text.replace(" ", ""))
        chunk_duration = total_duration * (chunk_len / total_char_count)
        
        # 너무 짧은 자막 방지 (최소 1초 보장, 단 전체 길이가 충분할 때)
        if chunk_duration < 1.0 and total_duration > len(chunks):
             chunk_duration = 1.0
             
        result.append({'text': chunk_text, 'duration': chunk_duration})
        
    # 마지막 자막 시간 보정 (오차 수정)
    calc_total = sum(r['duration'] for r in result)
    if result:
        result[-1]['duration'] += (total_duration - calc_total)
        
    return result

# -------------------------------------------------------------------------
# [함수 3] 제목 오디오 생성 (Azure TTS)
# -------------------------------------------------------------------------
def generate_title_audio(text, output_path):
    if os.path.exists(output_path): return True
    try:
        speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
        speech_config.speech_synthesis_voice_name = "ko-KR-HyunsuMultilingualNeural" # 해설자 톤
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = synthesizer.speak_text_async(text).get()
        return result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted
    except Exception as e:
        print(f"❌ 제목 TTS 에러: {e}")
        return False

# -------------------------------------------------------------------------
# [메인 로직] 비디오 생성
# -------------------------------------------------------------------------
def create_video_for_story(story_data, base_dir="output_assets"):
    title = story_data['title']
    safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '_')]).strip()
    
    story_dir = os.path.join(base_dir, safe_title)
    audio_dir = os.path.join(story_dir, "audio")
    image_dir = os.path.join(story_dir, "images")
    output_video_path = os.path.join(story_dir, f"{safe_title}_final.mp4")
    
    # 해상도 설정 (이미지 생성 사이즈와 동일하게 맞춤)
    VIDEO_SIZE = (1536, 1024) 

    print(f"🎬 [영상 편집 시작] '{title}'")

    if not os.path.exists(audio_dir) or not os.path.exists(image_dir):
        print(f"  ❌ 자산 폴더가 없어 건너뜁니다.")
        return

    final_clips = []

    # ==========================================
    # 1. 인트로 (Intro) 제작
    # ==========================================
    title_audio_path = os.path.join(audio_dir, "00_intro_title.mp3")
    
    # 제목 오디오 생성 시도
    has_intro_audio = generate_title_audio(title, title_audio_path)
    
    if has_intro_audio:
        title_audio = AudioFileClip(title_audio_path)
        intro_dur = title_audio.duration + 2.0 # 여유 시간 2초
        
        # 제목 자막 (중앙 정렬, 페이드인 효과)
        title_clip = create_text_clip_pil(
            title, FONT_PATH, TITLE_FONT_SIZE, "white", 
            duration=intro_dur, size=VIDEO_SIZE, pos='center'
        )
        
        # 검은 배경
        bg_clip = ColorClip(size=VIDEO_SIZE, color=(0,0,0), duration=intro_dur)
        
        # 합성
        intro_video = CompositeVideoClip([bg_clip, title_clip]).set_audio(title_audio).fadein(1.5)
        final_clips.append(intro_video)
        print("  ✅ 인트로 생성 완료")

    # ==========================================
    # 2. 본문 씬(Scene) 루프
    # ==========================================
    scenes = story_data.get('scenes', [])
    for scene in scenes:
        scene_num = scene['scene_num']
        scripts = scene['scripts']
        
        print(f"  🎞️ 장면 {scene_num} 구성 중...")

        # 이미지 로드
        img_filename = f"S{scene_num:02d}.png"
        img_path = os.path.join(image_dir, img_filename)
        if not os.path.exists(img_path):
            print(f"    ⚠️ 이미지 없음: {img_filename}")
            continue

        scene_audio_clips = []
        scene_subtitle_clips = []
        current_time = 0 
        
        # 스크립트(대사) 루프
        for idx, script in enumerate(scripts):
            role = script['role']
            text = script['text']
            
            # 오디오 파일 찾기 (파일명 패턴 매칭)
            pattern = os.path.join(audio_dir, f"S{scene_num:02d}_{idx:03d}_{role}_*.mp3")
            matches = glob.glob(pattern)
            
            if not matches: continue
            
            audio_path = matches[0]
            try:
                audio_clip = AudioFileClip(audio_path)
                total_duration = audio_clip.duration
                scene_audio_clips.append(audio_clip)
                
                # ★ 자막 분할 및 생성 (핵심 로직)
                subtitle_chunks = split_subtitle_chunks(text, total_duration, MAX_CHARS_PER_SCREEN)
                
                for chunk in subtitle_chunks:
                    chunk_text = chunk['text']
                    chunk_dur = chunk['duration']
                    
                    # PIL로 자막 이미지 생성 (하단 정렬)
                    txt_clip = create_text_clip_pil(
                        chunk_text, FONT_PATH, SUBTITLE_FONT_SIZE, SUBTITLE_COLOR, 
                        bg_color=SUBTITLE_BG_COLOR, 
                        duration=chunk_dur, 
                        size=VIDEO_SIZE, 
                        pos='bottom'
                    )
                    
                    # 시작 시간 설정 후 리스트 추가
                    txt_clip = txt_clip.set_start(current_time)
                    scene_subtitle_clips.append(txt_clip)
                    
                    current_time += chunk_dur
                
            except Exception as e:
                print(f"    ❌ 클립 처리 에러: {e}")

        if not scene_audio_clips: continue

        # 씬 합성 (오디오 연결 + 이미지 배경 + 자막들)
        combined_audio = concatenate_audioclips(scene_audio_clips)
        total_dur = combined_audio.duration + 0.5 # 0.5초 여유
        
        # 배경 이미지 (크로스페이드 효과 추가)
        base_img = ImageClip(img_path).set_duration(total_dur).crossfadein(0.5)
        
        # CompositeVideoClip은 [배경, 자막1, 자막2...] 순서로 넣어야 함
        final_scene = CompositeVideoClip([base_img] + scene_subtitle_clips).set_audio(combined_audio)
        final_clips.append(final_scene)

    # ==========================================
    # 3. 최종 렌더링 (고속 모드)
    # ==========================================
    if final_clips:
        print(f"  💾 렌더링 시작... (설정: Ultrafast, Threads=Max)")
        final_video = concatenate_videoclips(final_clips, method="compose")
        
        # CPU 코어 수 확인
        cpu_count = multiprocessing.cpu_count()
        
        try:
            final_video.write_videofile(
                output_video_path, 
                fps=24, 
                codec='libx264', 
                audio_codec='aac',
                threads=cpu_count,     # 멀티쓰레딩
                preset='ultrafast',    # 속도 최우선
                ffmpeg_params=['-tune', 'stillimage'] # 정지 영상 최적화
            )
            print(f"🎉 영상 제작 성공! \n📁 위치: {output_video_path}\n")
        except Exception as e:
            print(f"❌ 렌더링 실패: {e}")
    else:
        print("❌ 생성할 클립이 없습니다.")

def main(input_file):
    if os.path.exists(input_file):
        with open(input_file, 'r', encoding='utf-8') as f:
            for story in json.load(f):
                create_video_for_story(story)

if __name__ == "__main__":
    main("processed_stories.json")