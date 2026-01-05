import requests
from bs4 import BeautifulSoup
import re
import json
import time
import random


# 1. 목록 페이지에서 첫 번째 숫자만 추출 (중복 제거)
base_list_url = "http://18children.president.pa.go.kr/mobile/our_space/fairy_tales.php?srh%5Bcategory%5D=07&srh%5Bpage%5D={}"
pattern = re.compile(r'board\.goDetail\((\d+),\s*(\d+)\)')


coords_set = set()


for page in range(1, 21):
    url = base_list_url.format(page)
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            match = pattern.search(a_tag['href'])
            if match:
                num1, _ = match.groups()
                coords_set.add(int(num1))
    else:
        print(f"Page {page} 요청 실패: {response.status_code}")
    


coords_list = sorted(coords_set)


# 2. 상세 페이지에서 제목과 문단 추출
base_detail_url = "http://18children.president.pa.go.kr/mobile/our_space/fairy_tales.php?srh%5Bcategory%5D=07&srh%5Bpage%5D=1&srh%5Bview_mode%5D=detail&srh%5Bseq%5D={}"


result_data = {}


for seq in coords_list:
    detail_url = base_detail_url.format(seq)
    response = requests.get(detail_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 제목 추출
        title_tag = soup.find('h3', class_='title1')
        title_text = title_tag.get_text(strip=True) if title_tag else f"SEQ {seq}"
        
        # 문단 추출: style 속성에 'text-align'이 포함된 p 태그 모두
        p_tags = soup.find_all('p', style=lambda value: value and 'text-align' in value)
        pages_dict = {}
        for idx, p in enumerate(p_tags, start=1):
            text = p.get_text(strip=True)  # span 내부까지 포함해서 텍스트 추출
            if text:
                pages_dict[idx] = text
        
        result_data[seq] = {
            "title": title_text,
            "pages": pages_dict
        }
    else:
        print(f"상세 페이지 {seq} 요청 실패: {response.status_code}")
    


# 3. JSON 파일 저장
with open("fairy_tales.json", "w", encoding="utf-8") as f:
    json.dump(result_data, f, ensure_ascii=False, indent=4)


print("fairy_tales.json 저장 완료")