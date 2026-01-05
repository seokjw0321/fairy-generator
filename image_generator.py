import json
import os
import time
import base64
import requests
import random  # ★ 랜덤 선택을 위해 추가
from dotenv import load_dotenv

# 1. 환경변수 로드
load_dotenv()

API_KEY = os.getenv("AZURE_API_KEY")
ENDPOINT = os.getenv("AZURE_ENDPOINT")
DEPLOYMENT_NAME = os.getenv("AZURE_IMAGE_DEPLOYMENT_NAME", "gpt-image-1.5")
API_VERSION = "2024-02-15-preview" 

# -------------------------------------------------------------------------
# [설정] 다양한 아트 스타일 정의 (랜덤 선택용)
# -------------------------------------------------------------------------
STYLE_OPTIONS = {
    "Watercolor": (
        "A warm, gentle watercolor illustration for a children's book. "
        "Soft textures, pastel tones, dreamy atmosphere. "
    ),
    "Korean_Ink": (
        "Traditional Korean Ink wash painting style (Sumukhwa) on Hanji paper. "
        "Elegant brush strokes, oriental aesthetics, soft colors with black ink accents. "
    ),
    "Claymation": (
        "Cute 3D claymation style, isometric view, soft studio lighting. "
        "Looks like a handmade clay toy, rounded edges, vibrant and cute colors. "
    ),
    "Paper_Cutout": (
        "Layered paper cut craft style, depth of field, shadowbox effect. "
        "Intricate details, paper texture, warm lighting. "
    ),
    "Colored_Pencil": (
        "Soft colored pencil drawing, hand-drawn sketch texture. "
        "Warm and cozy feeling, sketchbook style. "
    )
}

# [공통] 글자 금지 및 품질 강화 프롬프트 (모든 스타일에 무조건 붙음)
COMMON_SUFFIX = (
    "Do not include any text, letters, words, or characters in the image. "
    "Pure illustration only. High quality, detailed."
)

# -------------------------------------------------------------------------
# [함수] 이미지 생성 (Raw API 사용)
# -------------------------------------------------------------------------
def generate_images_for_story(story_data, output_base_dir="output_assets"):
    title = story_data['title']
    safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '_')]).strip()
    
    save_dir = os.path.join(output_base_dir, safe_title, "images")
    os.makedirs(save_dir, exist_ok=True)
    
    # ★ 1. 동화별로 스타일 하나를 랜덤으로 뽑음 (여기서 뽑아야 동화 내내 통일됨)
    selected_style_name = random.choice(list(STYLE_OPTIONS.keys()))
    selected_style_prompt = STYLE_OPTIONS[selected_style_name]
    
    print(f"🎨 [이미지 생성 시작] '{title}'")
    print(f"✨ 이번 동화의 화풍: {selected_style_name}")  # 로그로 확인 가능
    
    scenes = story_data.get('scenes', [])
    total_scenes = len(scenes)
    
    # URL 조립
    base_url = ENDPOINT.rstrip('/')
    api_url = f"{base_url}/openai/deployments/{DEPLOYMENT_NAME}/images/generations?api-version={API_VERSION}"
    
    headers = {
        "api-key": API_KEY,
        "Content-Type": "application/json"
    }

    for scene in scenes:
        scene_num = scene['scene_num']
        visual_prompt = scene['visual_prompt']
        
        # ★ 2. 프롬프트 조합: [랜덤 스타일] + [장면 묘사] + [글자 금지 공통]
        full_prompt = f"{selected_style_prompt} {visual_prompt}. {COMMON_SUFFIX}"
        
        filename = f"S{scene_num:02d}.png"
        filepath = os.path.join(save_dir, filename)
        
        if os.path.exists(filepath):
            # print(f"  👉 [Skip] {filename}")
            continue

        print(f"  🖌️ [{selected_style_name}] 그리는 중... [장면 {scene_num}/{total_scenes}]")

        payload = {
            "prompt": full_prompt,
            "size": "1536x1024",
            "n": 1,
            "quality": "high"  
        }

        try:
            response = requests.post(api_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                print(f"  ❌ API 에러 (장면 {scene_num}): {response.text}")
                continue
                
            result = response.json()
            data_item = result['data'][0]
            
            if 'b64_json' in data_item and data_item['b64_json']:
                with open(filepath, 'wb') as f:
                    f.write(base64.b64decode(data_item['b64_json']))
                print(f"  ✅ 저장 완료: {filename}")
                
            elif 'url' in data_item and data_item['url']:
                img_res = requests.get(data_item['url'])
                with open(filepath, 'wb') as f:
                    f.write(img_res.content)
                print(f"  ✅ 저장 완료: {filename}")
                
            else:
                print(f"  ⚠️ 이미지 데이터 없음: {result}")

            time.sleep(5) # 쿨타임

        except Exception as e:
            print(f"  ❌ 에러: {e}")
            time.sleep(5)

    print(f"🎉 '{title}' 완료! (스타일: {selected_style_name})\n")

# --- 단독 실행 테스트용 ---
if __name__ == "__main__":
    if os.path.exists("processed_stories.json"):
        with open("processed_stories.json", 'r', encoding='utf-8') as f:
            stories = json.load(f)
            # 테스트로 1개만 돌려보기
            for story in stories[:1]:
                generate_images_for_story(story)