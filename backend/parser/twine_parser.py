from bs4 import BeautifulSoup
import re
import json

def parse_passage(passage):
    scene_id = passage["name"]
    raw_text = passage.text.strip()

    # Автопереход
    match_autonext = re.search(r'^\s*->\s*(\w+)\s*$', raw_text, re.MULTILINE)
    autonext = match_autonext.group(1) if match_autonext else None

    # Background
    match_background = re.search(r'\[background:(.*?)\]', raw_text)
    background = match_background.group(1).strip() if match_background else None

    # Character
    match_character = re.search(r'\[character:(.*?),\s*name:(.*?)\]', raw_text)
    character = {
        "image": match_character.group(1).strip(),
        "name": match_character.group(2).strip(),
        "position": "center"
    } if match_character else None

    # Удаление артефактов и управляющих инструкций
    raw_text = re.sub(r'\[background:.*?\]', '', raw_text)
    raw_text = re.sub(r'\[character:.*?,\s*name:.*?\]', '', raw_text)
    if autonext:
        raw_text = re.sub(r'^\s*->\s*\w+\s*$', '', raw_text, flags=re.MULTILINE)

    # Парсинг выборов: [[Text->scene, cost:n, stat:statname]]
    pattern = r'\[\[(.*?)\-\>(.*?)(?:,\s*cost:(\d+))?(?:,\s*stat:(\w+))?\]\]'
    choices_raw = re.findall(pattern, raw_text)
    parsed_choices = []
    for text, target, cost, stat in choices_raw:
        choice = {
            "text": text.strip(),
            "target": target.strip()
        }
        if cost:
            choice["cost"] = int(cost)
        if stat:
            choice["stat"] = stat
        parsed_choices.append(choice)

    # Удалить все [[...]] из текста
    raw_text = re.sub(r'\[\[.*?\-\>.*?\]\]', '', raw_text).strip()

    # Сборка результата
    scene = {
        "scene_id": scene_id,
        "text": raw_text,
        "autonext": autonext,
        "choices": parsed_choices
    }
    if background:
        scene["background"] = background
    if character:
        scene["character"] = character

    return scene

def parse_twine_html(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    passages = soup.find_all("tw-passagedata")
    story = {}

    for passage in passages:
        parsed = parse_passage(passage)
        story[parsed["scene_id"]] = parsed

    return story

if __name__ == "__main__":
    story = parse_twine_html("private_club_demo_150725.html")
    with open("passages.json", "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=2)