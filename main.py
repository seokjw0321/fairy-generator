import os
import json
import time
import subprocess
from dotenv import load_dotenv

# 각 모듈에서 핵심 함수들 임포트
# (주의: 아래 파일들이 같은 폴더에 있어야 합니다)
try:
    from story_processor import process_crawled_data
    from tts_generator import generate_tts_for_story
    from image_generator import generate_images_for_story
    from video_generator import create_video_for_story # ★ 추가됨
except ImportError as e:
    print(f"❌ 필수 모듈을 찾을 수 없습니다: {e}")
    print("crawl.py, story_processor.py, tts_generator.py, image_generator.py 파일이 모두 있는지 확인해주세요.")
    exit()

# 환경변수 로드
load_dotenv()

def run_pipeline(limit=None):
    print("="*60)
    print(f"🚀 전래동화 유튜브 자동 제작 파이프라인 가동 (Limit: {limit if limit else 'All'})")
    print("="*60)

    # ---------------------------------------------------------
    # [Step 1] 크롤링 (Data Crawling)
    # ---------------------------------------------------------
    print("\n[Step 1/3] 동화 데이터 크롤링 시작...")
    
    # crawl.py는 함수가 아니라 스크립트 형태이므로 subprocess로 실행
    try:
        if os.path.exists("fairy_tales.json"):
            print("   👉 기존 'fairy_tales.json' 파일이 있어 크롤링을 건너뜁니다. (새로 하려면 파일 삭제)")
        else:
            subprocess.run(["python", "crawl.py"], check=True)
            print("   ✅ 크롤링 완료!")
    except subprocess.CalledProcessError as e:
        print(f"   ❌ 크롤링 중 에러 발생: {e}")
        return

    # ---------------------------------------------------------
    # [Step 2] GPT-5 시나리오 분석 (Scenario Processing)
    # ---------------------------------------------------------
    print("\n[Step 2/3] GPT-5 시나리오 각색 시작...")
    
    input_crawl_file = "fairy_tales.json"
    output_processed_file = "processed_stories.json"

    # story_processor 모듈의 함수 호출
    process_crawled_data(input_crawl_file, output_processed_file, limit=limit)

    # ---------------------------------------------------------
    # [Step 3] 자산 생성 (TTS & Image Generation)
    # ---------------------------------------------------------
    print("\n[Step 3/3] 미디어 자산(음성/이미지) 생성 시작...")

    if not os.path.exists(output_processed_file):
        print(f"❌ {output_processed_file} 파일이 없어 중단합니다.")
        return

    with open(output_processed_file, 'r', encoding='utf-8') as f:
        stories = json.load(f)

    total_stories = len(stories)
    print(f"📚 총 {total_stories}편의 동화에 대해 자산 생성을 시작합니다.\n")

    for idx, story in enumerate(stories):
        title = story.get('title', 'Untitled')
        print(f"🎬 [{idx+1}/{total_stories}] '{title}' 제작 중...")

        # 3-1. TTS 생성 (Azure Speech)
        print(f"   🎙️ 음성(TTS) 생성 진입...")
        generate_tts_for_story(story)

        # 3-2. 이미지 생성 (DALL-E 3 / GPT-Image)
        print(f"   🎨 삽화(Image) 생성 진입...")
        generate_images_for_story(story)
        
        print(f"   ✨ '{title}' 자산 생성 완료!\n")
        
        # API 과부하 방지를 위한 쿨타임
        time.sleep(2)

    print("="*60)
    print("🎉 모든 작업이 성공적으로 완료되었습니다!")
    print(f"📂 결과물 위치: {os.path.abspath('output_assets')}")
    print("="*60)

    # ---------------------------------------------------------
    # [Step 4] 영상 편집 (Video Editing)
    # ---------------------------------------------------------
    # print("\n[Step 4/4] 최종 동영상 편집 시작...")
    
    # for idx, story in enumerate(stories):
    #     title = story.get('title', 'Untitled')
    #     # 4-1. 비디오 생성
    #     create_video_for_story(story)
        
    #     print(f"   ✨ '{title}' 모든 작업 완료!")
    #     time.sleep(1)

    print("="*60)
    print("🎉 대장정 종료! output_assets 폴더를 확인하세요.")

if __name__ == "__main__":
    # 테스트를 위해 1개만 실행하려면 숫자를 넣으세요 (예: run_pipeline(limit=1))
    # 전체를 다 하려면 run_pipeline() 또는 run_pipeline(limit=None)
    run_pipeline(limit=None)