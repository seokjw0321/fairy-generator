import json
import os
import time
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# 1. 환경변수 로드
load_dotenv()

SPEECH_KEY = os.getenv("SPEECH_KEY")
SPEECH_REGION = os.getenv("SPEECH_REGION")

# -------------------------------------------------------------------------
# [설정] 화자(Role) <-> Azure AI Speech 보이스 매핑 (이미지 기반 최적화)
# -------------------------------------------------------------------------
VOICE_MAPPING = {
    # 1. 해설 (Narrator): 지식 전달에 능한 현수 멀티링구얼
    "해설": "ko-KR-HyunsuMultilingualNeural",
    
    # 2. 아동 캐릭터 (Kids)
    # 서현(SeoHyeon)은 실제 어린이 목소리라 소녀 역할에 완벽합니다.
    "여자아이": "ko-KR-SeoHyeonNeural",
    "소녀": "ko-KR-SeoHyeonNeural",
    
    # 인준(InJoon)은 친근한 톤이라 소년 역할로 잘 어울립니다.
    "남자아이": "ko-KR-InJoonNeural", 
    "소년": "ko-KR-InJoonNeural",
    
    # 3. 성인 여성 (Adult Female)
    # 유진(YuJin)은 밝고 젊은 톤 (주인공 처녀)
    "처녀": "ko-KR-YuJinNeural",
    
    # 지민(JiMin)은 부드러운 톤 (차분한 어머니/아주머니)
    "아주머니": "ko-KR-JiMinNeural",
    
    # 4. 성인 남성 (Adult Male)
    # 국민(GookMin)을 청년 역할로 배정하여 다양성 확보
    "청년": "ko-KR-GookMinNeural",
    
    # 5. 노인 및 특수 배역 (Elderly & Special)
    # 순복(SoonBok)은 생동감(Animated)이 있어 할머니 연기에 적합
    "할머니": "ko-KR-SoonBokNeural",
    
    # 봉진(BongJin)은 목소리가 굵고 중후하여 할아버지나 악당에 제격
    "할아버지": "ko-KR-BongJinNeural",
    "악당": "ko-KR-BongJinNeural",
    
    # 선희(SunHi)는 차분하고 위로가 되는(Soothing) 톤이라 신요정 역할
    "신요정": "ko-KR-SunHiNeural", # (Dragon HD 퀄리티 대응)
    "동물": "ko-KR-InJoonNeural"    # 동물은 편안한 톤으로 설정 (필요 시 피치 조절)
}

DEFAULT_VOICE = "ko-KR-SunHiNeural" # 기본값

# -------------------------------------------------------------------------
# [함수] TTS 생성 및 파일 저장 (Azure Speech SDK 사용)
# -------------------------------------------------------------------------
def generate_tts_for_story(story_data, output_base_dir="output_assets"):
    title = story_data['title']
    safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '_')]).strip()
    
    save_dir = os.path.join(output_base_dir, safe_title, "audio")
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"🎙️ [TTS 시작] '{title}' 오디오 생성 중...")
    
    if not SPEECH_KEY or not SPEECH_REGION:
        print("❌ 오류: .env 파일에 SPEECH_KEY 또는 SPEECH_REGION이 없습니다.")
        return

    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    
    scenes = story_data.get('scenes', [])
    total_scripts = sum(len(scene['scripts']) for scene in scenes)
    current_count = 0

    for scene in scenes:
        scene_num = scene['scene_num']
        
        for idx, script in enumerate(scene['scripts']):
            role = script['role']
            text = script['text']
            
            # 1. 보이스 선택
            voice_name = VOICE_MAPPING.get(role, DEFAULT_VOICE)
            
            # 2. 파일명 규칙
            filename = f"S{scene_num:02d}_{idx:03d}_{role}_{voice_name}.mp3"
            filepath = os.path.join(save_dir, filename)
            
            if os.path.exists(filepath):
                current_count += 1
                continue

            try:
                # 3. Azure Speech SDK 설정
                speech_config.speech_synthesis_voice_name = voice_name
                audio_config = speechsdk.audio.AudioOutputConfig(filename=filepath)
                
                # 합성기 생성
                synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
                
                # 4. 합성 실행
                result = synthesizer.speak_text_async(text).get()

                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    current_count += 1
                    print(f"  ✅ [{current_count}/{total_scripts}] {filename} ({role})")
                elif result.reason == speechsdk.ResultReason.Canceled:
                    details = result.cancellation_details
                    print(f"  ❌ 취소됨: {filename} - {details.reason}")
                    if details.reason == speechsdk.CancellationReason.Error:
                        print(f"     에러 상세: {details.error_details}")

            except Exception as e:
                print(f"  ❌ 예외 발생: {filename} - {e}")
                time.sleep(1)

    print(f"🎉 '{title}' 오디오 생성 완료! 위치: {save_dir}\n")

# -------------------------------------------------------------------------
# [메인] 실행 로직
# -------------------------------------------------------------------------
def main(input_json_file):
    if not os.path.exists(input_json_file):
        print("❌ JSON 파일이 없습니다.")
        return

    with open(input_json_file, 'r', encoding='utf-8') as f:
        stories = json.load(f)

    print(f"📚 총 {len(stories)}편의 동화 오디오를 생성합니다.")
    print(f"✨ 적용된 주요 성우: 서현(아역), 순복(할머니), 현수멀티(해설), 봉진(악당) 등")

    for story in stories:
        generate_tts_for_story(story)

if __name__ == "__main__":
    INPUT_FILE = "processed_stories.json"
    main(INPUT_FILE)