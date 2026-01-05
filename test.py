import os
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# 1. .env 파일 로드 (키 보안)
load_dotenv()

def text_to_speech_hyunsu(text, output_filename):
    # .env에서 키와 리전 가져오기
    # (Azure Portal > Speech 서비스 > 키 및 엔드포인트에서 확인 가능)
    speech_key = os.getenv("SPEECH_KEY")      # 예: 3948...
    service_region = os.getenv("SPEECH_REGION") # 예: koreacentral

    if not speech_key or not service_region:
        print("❌ .env 파일에 SPEECH_KEY 또는 SPEECH_REGION이 없습니다.")
        return

    # 2. 스피치 설정
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    
    # ★ 핵심: 목소리를 '현수'로 설정
    # 현수는 차분한 남성 톤이라 내레이션(해설)에 아주 적합해
    speech_config.speech_synthesis_voice_name = "ko-KR-HyunsuNeural" 

    # 3. 오디오 출력 설정 (스피커가 아니라 파일로 저장!)
    # 이걸 안 하면 그냥 컴퓨터 스피커로 말하고 끝남
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_filename)

    # 4. 합성기 생성
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    print(f"🎙️ '현수'가 녹음을 시작합니다: {output_filename}")

    # 5. 텍스트 -> 음성 변환 (비동기 호출 후 대기)
    result = speech_synthesizer.speak_text_async(text).get()

    # 6. 결과 확인
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print(f"✅ 녹음 성공! 파일 저장됨: [{output_filename}]")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"❌ 취소됨: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print(f"❌ 에러 상세: {cancellation_details.error_details}")

# --- 실행 ---
if __name__ == "__main__":
    # 테스트 멘트
    test_text = "안녕하세요? 저는 전래동화를 읽어주는 현수입니다. 흥부와 놀부 이야기를 들려드릴게요."
    
    text_to_speech_hyunsu(test_text, "output_hyunsu.mp3")