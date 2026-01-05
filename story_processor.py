import json
import os
import time
from openai import AzureOpenAI
from dotenv import load_dotenv

# 1. .env 파일 로드
load_dotenv()

# -------------------------------------------------------------------------
# [설정] Azure OpenAI API 정보
# -------------------------------------------------------------------------
client = AzureOpenAI(
    api_key=os.getenv("AZURE_API_KEY"),  
    api_version=os.getenv("AZURE_API_VERSION"), 
    azure_endpoint=os.getenv("AZURE_ENDPOINT")
)

# -------------------------------------------------------------------------
# [함수 1] GPT-5 시나리오 분석 (프롬프트 대폭 수정)
# -------------------------------------------------------------------------
def analyze_story_with_gpt(story_data):
    sorted_keys = sorted(story_data['pages'].keys(), key=int)
    full_text = " ".join([story_data['pages'][k] for k in sorted_keys])
    title = story_data['title']

    print(f"▶️ [분석 시작] '{title}' (텍스트 길이: {len(full_text)}자)")

    # ★ 핵심 수정: 화자 제한 및 해설 확장 지시 강화
    system_prompt = """
    당신은 어린이 유튜브 채널을 위한 '전래동화 시나리오 전문 각색가'입니다.
    제공된 동화를 바탕으로 영상 제작용 JSON 데이터를 생성하세요.

    [화자(Role) 선택 규칙 - 엄격 준수]
    대사의 화자(role)는 반드시 아래 목록 중에서만 선택해야 합니다. 목록에 없는 단어(예: 엄마, 행인, 호랑이)는 절대 사용하지 마세요.
    - 허용 목록: [해설, 남자아이, 여자아이, 소년, 소녀, 청년, 처녀, 할아버지, 할머니, 악당, 동물, 신/요정]
    
    [시나리오 작성 지침]
    1. **장면 구성**: 전체 이야기를 **6~10개의 핵심 장면(Scene)**으로 재구성하세요.
    2. **이미지 프롬프트(visual_prompt)**: 한국어로 구체적이고 서정적인 묘사 (예: 따뜻한 수채화풍, 지브리 스타일 등).
    3. **해설(해설 role)의 확장**: 원문의 단순한 서술을 **구연동화에 맞게 대폭 늘려서 각색**하세요. 
       - 상황 묘사, 등장인물의 감정, 배경 분위기 등을 풍부하게 덧붙여 문장을 길고 맛깔나게 만드세요.
       - 예: "흥부가 쫓겨났다" (X) -> "욕심쟁이 형 놀부에게 매몰차게 쫓겨난 흥부는, 쌀 한 톨 없이 빈손으로 터덜터덜 집을 나설 수밖에 없었답니다. 찬바람이 쌩쌩 부는 가을날이었지요." (O)
    4. **캐릭터 대사**: 등장인물의 대사는 원문의 맛을 살리되 자연스럽게 다듬어주세요.
    5. **JSON 포맷 엄수**: 오직 JSON 객체만 출력하세요.

    [JSON 예시]
    {
      "title": "흥부전",
      "scenes": [
        {
          "scene_num": 1,
          "visual_prompt": "가을바람이 부는 놀부네 기와집 대문 앞, 쫓겨나는 흥부 가족의 뒷모습. 쓸쓸하고 슬픈 분위기. 수채화풍.",
          "scripts": [
            {"role": "해설", "text": "옛날 어느 마을에 욕심 많은 형 놀부와 마음씨 착한 동생 흥부가 살고 있었어요. 어느 추운 겨울날, 놀부는 부모님이 물려주신 재산을 혼자 몽땅 차지하고는 가여운 흥부 가족을 빈손으로 내쫓아 버렸답니다."},
            {"role": "악당", "text": "썩 꺼지거라! 내 눈앞에 다시는 띄지 마!"},
            {"role": "소년", "text": "형님, 제발 저희 아이들을 봐서라도 조금만 도와주세요."}
          ]
        }
      ]
    }
    """

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_DEPLOYMENT_NAME"), 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"동화 내용:\n{full_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.7 # 창의적인 각색을 위해 온도를 약간 높게 유지
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ 오류 발생 ({title}): {e}")
        return None

# -------------------------------------------------------------------------
# [함수 2] 메인 실행
# -------------------------------------------------------------------------
def process_crawled_data(input_file, output_file, limit=None):
    if not os.path.exists(input_file):
        print("❌ 크롤링 된 json 파일을 찾을 수 없습니다.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        crawled_data = json.load(f) 

    # 딕셔너리 아이템을 리스트로 변환
    all_items = list(crawled_data.items())
    total_count = len(all_items)
    
    # limit 적용
    if limit is not None:
        target_items = all_items[:limit]
        print(f"📚 크롤링 데이터 로드 완료: 총 {total_count}개 중 {limit}개만 처리합니다.\n")
    else:
        target_items = all_items
        print(f"📚 크롤링 데이터 로드 완료: 총 {total_count}개 전체를 처리합니다.\n")
    
    final_results = []

    # 순회 및 처리
    for index, (seq_id, story_content) in enumerate(target_items):
        print(f"[{index+1}/{len(target_items)}] 처리 중...")
        
        analyzed = analyze_story_with_gpt(story_content)
        
        if analyzed:
            analyzed['original_seq'] = seq_id 
            final_results.append(analyzed)
            print(f"✅ '{analyzed['title']}' 처리 완료!\n")
        
        time.sleep(1) 

    # 결과 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    
    print(f"🎉 작업 완료! 결과 파일: {output_file}")

# --- 실행 ---
if __name__ == "__main__":
    # 테스트를 위해 2개만 실행
    process_crawled_data("fairy_tales.json", "processed_stories.json", limit=2)