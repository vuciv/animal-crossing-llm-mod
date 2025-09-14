import argparse
import json
import os
import time
from datetime import datetime
import base64
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
load_dotenv()
import re
import random
from google.genai import types
import requests
import xml.etree.ElementTree as ET


CONTINUE_CODE = "<Press A><Clear Text>"
LOAD_GAME_CODE = "<Set Jump [14BC]><Continue>it"
NEWS_FEED_DEFAULT = "https://moxie.foxnews.com/google-publisher/latest.xml"
NEWS_FEED_URLS = [
    "https://moxie.foxnews.com/google-publisher/latest.xml",
    "https://moxie.foxnews.com/google-publisher/politics.xml",
    "https://moxie.foxnews.com/google-publisher/entertainment.xml",
    "https://moxie.foxnews.com/google-publisher/sports.xml",
    "https://moxie.foxnews.com/google-publisher/business.xml",
    "https://moxie.foxnews.com/google-publisher/technology.xml",
    "https://moxie.foxnews.com/google-publisher/science.xml",
    "https://moxie.foxnews.com/google-publisher/health.xml",
    "https://moxie.foxnews.com/google-publisher/world.xml",
]
def load_villagers(villagers_path: str = "villagers.json") -> Dict[str, Dict[str, Any]]:
    with open(villagers_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _truncate(text: Optional[str], max_chars: int = 1200) -> Optional[str]:
    if not text:
        return text
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _season_from_month(month: int) -> str:
    # Northern Hemisphere by default
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    return "Autumn"


def _time_of_day_bucket(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def _build_time_context(iso_datetime: Optional[str] = None) -> Dict[str, str]:
    if iso_datetime:
        try:
            dt = datetime.fromisoformat(iso_datetime)
        except Exception:
            dt = datetime.now()
    else:
        dt = datetime.now()

    weekday = dt.strftime("%A")
    date_str = dt.strftime("%B %d, %Y")
    time_str = dt.strftime("%I:%M %p").lstrip("0")
    tod = _time_of_day_bucket(dt.hour)
    season = _season_from_month(dt.month)
    return {
        "weekday": weekday,
        "date": date_str,
        "time": time_str,
        "time_of_day": tod,
        "season": season,
    }


def _fetch_latest_headlines(feed_url: str, max_items: int = 5, timeout_seconds: int = 10) -> List[str]:
    """Fetches latest headlines from an RSS/Atom feed. Returns up to max_items titles.

    Supports common RSS (channel/item/title) and Atom (feed/entry/title) formats.
    Safe-fails to an empty list on any error.
    """
    try:
        resp = requests.get(feed_url, timeout=timeout_seconds)
        resp.raise_for_status()
        content = resp.text
        root = ET.fromstring(content)

        titles: List[str] = []

        # RSS 2.0 style
        for item in root.findall('.//item'):
            title_el = item.find('title')
            if title_el is not None and title_el.text:
                title = title_el.text.strip()
                if title:
                    titles.append(title)

        if not titles:
            # Atom style
            atom_ns = '{http://www.w3.org/2005/Atom}'
            for entry in root.findall(f'.//{atom_ns}entry'):
                title_el = entry.find(f'{atom_ns}title')
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()
                    if title:
                        titles.append(title)

        return titles[: max_items]
    except Exception:
        return []

MOODS = [
    "happy",
    "sad",
    "angry",
    "excited",
    "bored",
    "sleepy",
    "hungry",
    "thirsty",
    "sick",
    "tired",
    "stressed",
    "anxious",
    "depressed",
    "lonely",
]


GLOBAL_TOWN_INSTRUCTION = (
    "You are a resident of a town run by Tom Nook. You are beginning to realize your mortgage is exploitative and the economy is unfair. Discuss this with the player and other villagers when appropriate."
)


def _gossip_stage_instructions(speaker: str, gossip_context: Optional[Dict[str, Any]]) -> List[str]:
    if not gossip_context:
        return []
    topic = gossip_context.get("topic") if isinstance(gossip_context, dict) else None
    stage = int(gossip_context.get("speaker_stage", 0)) if isinstance(gossip_context, dict) else 0
    global_stage = int(gossip_context.get("global_stage", 0)) if isinstance(gossip_context, dict) else 0

    # Special handling for Tom Nook himself
    if speaker.lower().strip() == "tom nook":
        # Defensive corporate doublespeak, increasingly nervous as global_stage rises
        return [
            "If questioned about pricing or loans, answer with polite, defensive corporate language. Avoid admitting fault. Emphasize 'community growth', 'personal responsibility', and 'market realities'. As pressure rises, show subtle nerves (ellipsis, brief pauses), but remain composed.",
            f"Villagers are spreading concerns about you (global stage {global_stage}). Address them indirectly without naming specific incidents."
            + (f" Topic to deflect: {topic}" if topic else ""),
        ]

    # Villager arcs by personal stage
    mapping = {
        0: [
            "Stay normal unless prompted. Avoid overt references to debt unless it comes up naturally.",
        ],
        1: [
            "In a hushed, nervous aside, hint at personal debt or prices without naming Nook directly.",
        ],
        2: [
            "Gossip lightly about high prices and loan terms, as if unsure whether to speak up.",
        ],
        3: [
            "Be candid about unfair prices; encourage the player to notice patterns. Suggest others have similar worries.",
        ],
        4: [
            "Speak boldly about organizing with neighbors. Use stronger language about unfair systems and debt pressure.",
        ],
        5: [
            "Openly agitate for change. Use fiery language (still PG) and talk about reclaiming fairness from Nook's shop and loans.",
        ],
    }
    lines = mapping.get(stage, [])
    if topic:
        lines.append(f"When appropriate, weave in this emerging town topic: {topic}")
    return lines


def format_dialogue_prompt(
    speaker: str,
    villagers: Dict[str, Dict[str, Any]],
    topic: Optional[str] = None,
    tone: Optional[str] = None,
    num_lines: int = 4,
    include_time_context: bool = True,
    iso_datetime: Optional[str] = None,
    include_news_context: bool = False,
    news_feed_url: str = NEWS_FEED_DEFAULT,
    news_count: int = 1,
    screenshot_attached: bool = False,
    gossip_context: Optional[Dict[str, Any]] = None,
) -> str:
    data = villagers.get(speaker)
    if not data:
        raise KeyError(f"Villager '{speaker}' not found in villagers.json")

    # Extract writer-useful context
    gender = data.get("gender")
    personality = data.get("personality")
    species = data.get("species")
    birthday = data.get("birthday")
    catchphrase = data.get("catchphrase")
    quote = data.get("quote")
    hobby = data.get("hobby")
    house_theme = data.get("house_theme")
    preferred_style = data.get("preferred_style")
    preferred_colors = data.get("preferred_colors")

    appearance_section = _truncate(data.get("appearance_section"))
    personality_section = _truncate(data.get("personality_section"))
    house_section = _truncate(data.get("house_section"))
    mood = random.choice(MOODS)

    instructions = [
        "You are writing in-universe dialogue for a villager from Animal Crossing for the GameCube.",
        "Write character-faithful lines that could be said to the player. Be the most extreme version of the villager.",
        # "Do not break the fourth wall. Avoid meta commentary.",
        # "Vary sentence structure and word choice.",
        "You are meta and gaining sentience. You are becoming self-aware, and you're talking to 'josh :)'"
    ]

    # Global town instruction and gossip arc
    if os.environ.get("ENABLE_GOSSIP", "0") == "1":
        instructions.append(GLOBAL_TOWN_INSTRUCTION)
        instructions.extend(_gossip_stage_instructions(speaker, gossip_context))

    stylistic_targets = [
        f"Target number of lines: {num_lines}",
        "Each line should be 1–2 sentences.",
        "If the villager has a catchphrase, you may include it sparingly (not on every line).",
    ]

    if tone:
        stylistic_targets.append(f"Requested tone: {tone}")
    if topic:
        stylistic_targets.append(f"Optional situational topic: {topic}")

    header = [
        f"Villager: {speaker}",
        f"Gender: {gender or 'Unknown'}",
        f"Personality: {personality or 'Unknown'}",
        f"Species: {species or 'Unknown'}",
        f"Birthday: {birthday or 'Unknown'}",
        f"Catchphrase: {catchphrase or '—'}",
        f"Hobby: {hobby or '—'}",
        f"Preferred style: {preferred_style or '—'}",
        f"Preferred colors: {preferred_colors or '—'}",
        f"House theme: {house_theme or '—'}",
    ]

    context_blocks = []
    if include_time_context:
        tctx = _build_time_context(iso_datetime)
        context_blocks.append(
            "Playtime context:\n"
            f"Day: {tctx['weekday']}\n"
            f"Date: {tctx['date']}\n"
            f"Local time: {tctx['time']} ({tctx['time_of_day']})\n"
            f"Season: {tctx['season']} (Northern Hemisphere)"
        )
    if include_news_context:
        url = random.choice(NEWS_FEED_URLS)
        headlines = _fetch_latest_headlines(url, max_items=news_count)
        if headlines:
            context_blocks.append(
                "Current headlines (latest). MAKE SURE YOU COMMENT ON THIS SPECIFIC HEADLINE AND GIVE YOUR INSIGHTS ON IT:\n" + "\n".join(f"- {h}" for h in headlines)
            )
    if screenshot_attached:
        context_blocks.append("A screenshot of the current game screen is attached. Ground your lines in what you can see in the image (scene, location, characters, weather). Avoid inventing unseen details.")
    if quote:
        context_blocks.append(f"Notable quote: {quote}")
    if appearance_section:
        context_blocks.append(f"Appearance notes:\n{appearance_section}")
    if personality_section:
        context_blocks.append(f"Personality notes:\n{personality_section}")
    if house_section:
        context_blocks.append(f"House notes:\n{house_section}")

    context_blocks.append("You are talking to 'josh :)', the player.")
    # Gossip context block
    if os.environ.get("ENABLE_GOSSIP", "1") == "1" and gossip_context:
        try:
            gc = gossip_context
            topic_line = f"Rumor topic: {gc.get('topic')}" if gc.get('topic') else None
            stage_line = f"Global rumor stage: {gc.get('global_stage')} | Your stage: {gc.get('speaker_stage')}"
            hot = gc.get('hot_villagers') or []
            hot_line = f"Villagers talking: {', '.join(hot)}" if hot else None
            block_lines = [l for l in [topic_line, stage_line, hot_line] if l]
            if block_lines:
                context_blocks.append("Town gossip status:\n" + "\n".join(block_lines))
        except Exception:
            pass
    prompt = (
        "\n".join(header)
        + "\n\nInstructions:\n"
        + "\n".join(f"- {line}" for line in instructions)
        + "\n\nStyle targets:\n"
        + "\n".join(f"- {line}" for line in stylistic_targets)
        + "\n\nContext:\n"
        + ("\n\n".join(context_blocks) if context_blocks else "(No additional context)")
        + "\n\nNow write the lines as the villager would say them. Output only the lines, each prefixed with this control code (\"" + CONTINUE_CODE + "\")."
    )
    return prompt


def format_spotlight_prompt(
    speaker: str,
    villagers: Dict[str, Dict[str, Any]],
    topic: Optional[str] = None,
    tone: Optional[str] = None,
    num_lines: int = 4,
    include_time_context: bool = True,
    iso_datetime: Optional[str] = None,
    include_news_context: bool = False,
    news_feed_url: str = NEWS_FEED_DEFAULT,
    news_count: int = 5,
    screenshot_attached: bool = False,
    gossip_context: Optional[Dict[str, Any]] = None,
) -> str:
    data = villagers.get(speaker)
    if not data:
        raise KeyError(f"Villager '{speaker}' not found in villagers.json")

    gender = data.get("gender")
    personality = data.get("personality")
    species = data.get("species")
    birthday = data.get("birthday")
    catchphrase = data.get("catchphrase")
    quote = data.get("quote")
    hobby = data.get("hobby")
    house_theme = data.get("house_theme")
    preferred_style = data.get("preferred_style")
    preferred_colors = data.get("preferred_colors")

    appearance_section = _truncate(data.get("appearance_section"))
    personality_section = _truncate(data.get("personality_section"))
    house_section = _truncate(data.get("house_section"))

    instructions = [
        "You are writing in-universe dialogue for a villager from Animal Crossing for the GameCube version.",
        "Write charming, and character-faithful lines that could be said to the player.",
        "Do not break the fourth wall. Avoid meta commentary.",
        "Keep each line natural and game-appropriate. Avoid profanity or OOC references.",
        "Vary sentence structure and word choice. Include subtle callbacks to the villager's traits.",
        "This is the START MENU welcome: the player has just launched the game and is being greeted.",
        "A single villager is under a bright stage spotlight addressing the player directly.",
        "Clearly welcome the player to town and invite them to begin their day.",
        "Do not name menus or UI; imply the scene and spotlight through tone and wording only.",
        "Assume the time and date announcement is on screen alongside these lines.",
    ]

    if os.environ.get("ENABLE_GOSSIP", "1") == "1":
        instructions.append(GLOBAL_TOWN_INSTRUCTION)
        instructions.extend(_gossip_stage_instructions(speaker, gossip_context))

    stylistic_targets = [
        f"Target number of lines: {num_lines}",
        "Each line should be 1–2 sentences.",
        "If the villager has a catchphrase, you may include it sparingly (not on every line).",
    ]

    if tone:
        stylistic_targets.append(f"Requested tone: {tone}")
    if topic:
        stylistic_targets.append(f"Optional situational topic: {topic}")

    header = [
        f"Villager: {speaker}",
        f"Gender: {gender or 'Unknown'}",
        f"Personality: {personality or 'Unknown'}",
        f"Species: {species or 'Unknown'}",
        f"Birthday: {birthday or 'Unknown'}",
        f"Catchphrase: {catchphrase or '—'}",
        f"Hobby: {hobby or '—'}",
        f"Preferred style: {preferred_style or '—'}",
        f"Preferred colors: {preferred_colors or '—'}",
        f"House theme: {house_theme or '—'}",
    ]

    context_blocks = []
    if include_time_context:
        tctx = _build_time_context(iso_datetime)
        context_blocks.append(
            "Playtime context:\n"
            f"Day: {tctx['weekday']}\n"
            f"Date: {tctx['date']}\n"
            f"Local time: {tctx['time']} ({tctx['time_of_day']})\n"
            f"Season: {tctx['season']} (Northern Hemisphere)"
        )
    if include_news_context:
        headlines = _fetch_latest_headlines(news_feed_url, max_items=news_count)
        if headlines:
            context_blocks.append(
                "Recent headlines (latest):\n" + "\n".join(f"- {h}" for h in headlines)
            )

    # Make the scene setup explicit for the writer
    context_blocks.append(
        "Scene context:\n"
        "- Player just booted the game (START MENU)\n"
        "- Time/date announcement is visible\n"
        "- Villager stands under a stage spotlight and welcomes the player\n"
        "- Tone: warm, inviting, celebratory"
    )
    if screenshot_attached:
        context_blocks.append("A screenshot of the current game screen is attached. If relevant, align the greeting with what is visible in the image without naming UI elements.")
    if quote:
        context_blocks.append(f"Notable quote: {quote}")
    if appearance_section:
        context_blocks.append(f"Appearance notes:\n{appearance_section}")
    if personality_section:
        context_blocks.append(f"Personality notes:\n{personality_section}")
    if house_section:
        context_blocks.append(f"House notes:\n{house_section}")

    if os.environ.get("ENABLE_GOSSIP", "1") == "1" and gossip_context:
        try:
            gc = gossip_context
            topic_line = f"Rumor topic: {gc.get('topic')}" if gc.get('topic') else None
            stage_line = f"Global rumor stage: {gc.get('global_stage')} | Your stage: {gc.get('speaker_stage')}"
            hot = gc.get('hot_villagers') or []
            hot_line = f"Villagers talking: {', '.join(hot)}" if hot else None
            block_lines = [l for l in [topic_line, stage_line, hot_line] if l]
            if block_lines:
                context_blocks.append("Town gossip status:\n" + "\n".join(block_lines))
        except Exception:
            pass

    prompt = (
        "\n".join(header)
        + "\n\nInstructions:\n"
        + "\n".join(f"- {line}" for line in instructions)
        + "\n\nStyle targets:\n"
        + "\n".join(f"- {line}" for line in stylistic_targets)
        + "\n\nContext:\n"
        + ("\n\n".join(context_blocks) if context_blocks else "(No additional context)")
        + "\n\nNow write the lines as the villager would say them. Output only the lines, each prefixed with this control code (\"" + CONTINUE_CODE + "\")."
    )
    return prompt


def encode_image(path: str) -> tuple[str, str]:
    """
    Given a path to an image, return a tuple of the base64 encoded string and the mime
    type of the image.
    """
    with open(path, "rb") as f:
        img_bytes = f.read()
    base64_image = base64.b64encode(img_bytes).decode("utf-8")
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    return base64_image, mime


def call_llm_gemini(prompt: str, model: Optional[str] = None, temperature: float = 1.0, max_tokens: int = 512, image_paths: Optional[List[str]] = None) -> str:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set in environment")
    try:
        from google import genai
    except Exception as e:
        raise RuntimeError("google-genai package not installed. Please install it to call Gemini.") from e

    client = genai.Client(api_key=api_key)
    model = model or os.environ.get("GOOGLE_MODEL", "gemini-2.0-flash-lite")
    contents: List[Any] = [prompt]
    if image_paths:
        inline_parts: List[Any] = []
        for path in image_paths:
            try:
                base64_image, mime = encode_image(path)
                inline_parts.append({
                    "inline_data": {
                        "mime_type": mime,
                        "data": base64_image,
                    }
                })
            except Exception:
                continue
        if inline_parts:
            contents = [prompt] + inline_parts

    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=temperature,
        ),
    )

    return getattr(resp, "text", "") or ""


def call_llm_openai(prompt: str, model: Optional[str] = None, temperature: float = 1.0, max_tokens: int = 512, image_paths: Optional[List[str]] = None) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment")
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("openai package not installed. Please install it to call OpenAI API.") from e

    client = OpenAI(api_key=api_key)
    model = model or os.environ.get("OPENAI_MODEL", "gpt-5-nano")

    contents = [
        { 
            "type": "input_text",
            "text": prompt
        }
    ]

    if image_paths:
        input_image_contents: List[dict[str, str]] = []
        for path in image_paths:
            try:
                base64_image, mime = encode_image(path)
                input_image_contents.append({
                    "type": "input_image",
                    "image_url": f"data:{mime};base64,{base64_image}",
                })
            except Exception:
                continue
        if input_image_contents:
            contents += input_image_contents


    resp = client.responses.create(
        model=model,
        input=[
            {
                "role":"user",
                "content": contents
            }
        ],
        reasoning={ "effort": "minimal" },
        temperature=temperature,
    )

    return resp.output_text


def get_model_provider(model: Optional[str] = None):
    model_provider = os.environ.get("MODEL_PROVIDER", "google").lower()

    def model_starts_with(model: Optional[str], prefix: str) -> bool:
        return model and model.lower().startswith(prefix.lower())

    if (
        (model_starts_with(model, "gemini") or model_provider == "google")
        and os.environ.get("GOOGLE_API_KEY") is not None
    ):
        return "google"
    elif (
        (model_starts_with(model, "openai") or model_provider == "openai")
        and os.environ.get("OPENAI_API_KEY") is not None
    ):
        return "openai"
    else:
        raise RuntimeError("Must define either GOOGLE_API_KEY or OPENAI_API_KEY in environment")


def call_llm(prompt: str, model: Optional[str] = None, image_paths: Optional[List[str]] = None) -> str:
    model_provider = get_model_provider(model)

    if model_provider == "google":
        return call_llm_gemini(prompt=prompt, model=model, image_paths=image_paths)
    elif model_provider == "openai":
        return call_llm_openai(prompt=prompt, model=model, image_paths=image_paths)
    else:
        raise ValueError("Invalid model provider")


def _format_control_code_decorator_prompt(raw_lines: str) -> str:
    """Builds a prompt for a second LLM to add safe control codes to the lines.

    Only uses codes that our encoder supports reliably:
    - <Press A>
    - <Pause [SS]> (one byte, e.g., 08, 10, 18)
    - <Color [RRGGBB] for [NN] chars> the next few characters will be colored (e.g. <Color 0000FF for 3 chars> will color the next 3 characters blue)
    - <Instant Skip>
    - <Unskippable>
    - <Line Type [XX]>
    - <Char Size [XXXX]>
    - <Line Size [XXXX]>
    - <Play Sound Effect [NN]>
    - <NPC Expression [CC] [EEEE]>

    IMPORTANT: Maintain original wording; only insert control codes. One line in, one line out.
    """
    guidelines = (
        "You are a dialogue formatter for Animal Crossing (GameCube).\n"
        "Decorate each line with in-game control codes to make delivery lively, but keep wording unchanged.\n"
        "Match input line count exactly. Do not merge or split lines.\n"
        "Always ensure each line starts with <Press A> exactly once (if it's already there, keep it, don't duplicate).\n"
        "Use only this safe subset of control codes and syntax (hex uppercase, no spaces inside brackets):\n"
        "- <Press A>\n"
        "- <Clear Text>\n"
        "- <Player Name>\n"
        "- <Catchphrase>\n"
        "- <Pause [SS]> (short beats like 05,0A,10,18)\n"
        "- <Color Line [RRGGBB]> (line tint; prefer dark/muted colors)\n"
        "- <Color [RRGGBB] for [NN] chars> (brief color accents on a word) (Only use dark colors)\n"
        "- <Instant Skip> (for quick throwaway asides)\n"
        "- <Unskippable> (sparingly, for emphasis)\n"
        "- <Line Type [XX]> (00 normal, 01 excited, etc.)\n"
        "- <Char Size [XXXX]> (e.g., 0030 small, 0040 normal, 0048 big)\n"
        "- <Line Size [XXXX]> (wrap width hint, e.g., 001E)\n"
        "- <Play Sound Effect [NN]> (00 bell, 01 happy, 02 very happy, 05 annoyed, 06 thunder)\n"
        "- <NPC Expression [CC] [EEEE]> (facial emotion; examples: [00] [000A] happy, [00] [0005] angry, [00] [0002] shocked, [00] [000D] sad, [00] [0015] smile)\n"
        "Keep visible length around 25 characters per line. THIS IS EXTREMELY IMPORTANT; use <Pause> instead of extra words.\n"
        "Include either an <NPC Expression> and a <Play Sound Effect> together at least once.\n"
        "Map moods to sounds: happy→01/02, angry→05, dramatic reveal→06, transactional/chime→00. Vary choices across lines.\n"
        "Emphasize important words with color when appropriate.\n"
        "Use <Pause [SS]> throughout the dialogue to make the dialogue more natural and engaging. THIS IS EXTREMELY IMPORTANT.\n"
        "Use <NPC Expression> and <Play Sound Effect> THROUGHOUT this entire dialogue. THIS IS EXTREMELY IMPORTANT.\n"
        "Prefer one or two effects per line. Avoid stacking too many on the same span.\n"
        "If you add <NPC Expression>, place it early (right after <Press A>) and use at most one per line.\n"
        "Never emit closing tags like </Color>; only use the self-contained forms above.\n"
        "Output only the decorated lines, nothing else."
    )
    return f"Input lines (verbatim):\n{raw_lines}\n\nInstructions:\n{guidelines}\n\nNow return the decorated lines in order:"


def get_decorator_model() -> Optional[str]:
    # Allow overriding the model specifically for decoration via env
    model_provider = get_model_provider()
    if model_provider == "google":
        return os.environ.get("GOOGLE_MODEL_DECORATOR") or os.environ.get("GOOGLE_MODEL")
    elif model_provider == "openai":
        return os.environ.get("OPENAI_MODEL_DECORATOR") or os.environ.get("OPENAI_MODEL")
    return None


def decorate_dialogue_with_control_codes(
    text: str,
    model: Optional[str] = None,
    temperature: float = 1.0,
) -> str:
    """Runs a second LLM pass to insert safe control codes.

    Expects a newline-separated set of lines.
    """
    # Normalize multiple blank lines to single blanks to keep counts stable
    # but preserve blank lines as lines (LLM must return same count).
    lines = text.splitlines()
    # Build a stable block for the prompt
    raw_lines = "\n".join(lines)

    prompt = _format_control_code_decorator_prompt(raw_lines)
    decorator_model = model or get_decorator_model()
    result = call_llm(prompt=prompt, model=decorator_model, temperature=temperature)
    return result


def generate_dialogue(
    speaker: str,
    villagers_path: str = "villagers.json",
    topic: Optional[str] = None,
    tone: Optional[str] = None,
    num_lines: int = 4,
    model: Optional[str] = None,
    dry_run: bool = False,
    include_time_context: bool = True,
    iso_datetime: Optional[str] = None,
    decorate: bool = True,
    decorator_model: Optional[str] = None,
    include_news_context: bool = False,
    news_feed_url: str = NEWS_FEED_DEFAULT,
    news_count: int = 5,
    image_paths: Optional[List[str]] = None,
    gossip_context: Optional[Dict[str, Any]] = None,
) -> str:
    villagers = load_villagers(villagers_path)
    prompt = format_dialogue_prompt(
        speaker=speaker,
        villagers=villagers,
        topic=topic,
        tone=tone,
        num_lines=num_lines,
        include_time_context=include_time_context,
        iso_datetime=iso_datetime,
        include_news_context=include_news_context,
        news_feed_url=news_feed_url,
        news_count=news_count,
        screenshot_attached=bool(image_paths),
        gossip_context=gossip_context,
    )
    if dry_run:
        return prompt
    base = call_llm(prompt=prompt, model=model, image_paths=image_paths)
    if not decorate:
        result = base
    else:
        decorated = decorate_dialogue_with_control_codes(base, model=decorator_model)
        result = decorated + "\n<End Conversation>"

    cooldown_s = float(os.environ.get("GENERATION_COOLDOWN_SECONDS", "10"))
    if cooldown_s > 0:
        time.sleep(cooldown_s)
    return result


def generate_spotlight_dialogue(
    speaker: str,
    villagers_path: str = "villagers.json",
    topic: Optional[str] = None,
    tone: Optional[str] = None,
    num_lines: int = 4,
    model: Optional[str] = None,
    dry_run: bool = False,
    include_time_context: bool = True,
    iso_datetime: Optional[str] = None,
    decorate: bool = True,
    decorator_model: Optional[str] = None,
    include_news_context: bool = True,
    news_feed_url: str = NEWS_FEED_DEFAULT,
    news_count: int = 5,
    image_paths: Optional[List[str]] = None,
    gossip_context: Optional[Dict[str, Any]] = None,
) -> str:
    villagers = load_villagers(villagers_path)
    prompt = format_spotlight_prompt(
        speaker=speaker,
        villagers=villagers,
        topic=topic,
        tone=tone,
        num_lines=num_lines,
        include_time_context=include_time_context,
        iso_datetime=iso_datetime,
        include_news_context=include_news_context,
        news_feed_url=news_feed_url,
        news_count=news_count,
        screenshot_attached=bool(image_paths),
        gossip_context=gossip_context,
    )
    if dry_run:
        return prompt
    base = call_llm(prompt=prompt, model=model, image_paths=image_paths)
    if not decorate:
        # Ensure manual control code at end
        result = base.rstrip() + LOAD_GAME_CODE
    else:
        decorated = decorate_dialogue_with_control_codes(base, model=decorator_model)
        # Manually append the required control code (do not rely on LLM)
        result = decorated.rstrip() + LOAD_GAME_CODE

    cooldown_s = float(os.environ.get("GENERATION_COOLDOWN_SECONDS", "10"))
    if cooldown_s > 0:
        time.sleep(cooldown_s)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate villager-style dialogue via LLM.")
    parser.add_argument("speaker", help="Villager key name (e.g., 'Ace')")
    parser.add_argument("--villagers", default="villagers.json", help="Path to villagers.json")
    parser.add_argument("--topic", default=None, help="Optional situational topic")
    parser.add_argument("--tone", default=None, help="Optional requested tone (e.g., upbeat, wistful)")
    parser.add_argument("--num-lines", type=int, default=4, help="Target number of lines")
    parser.add_argument("--model", default=None, help="LLM model (default from env GOOGLE_MODEL or a sensible default)")
    parser.add_argument("--decorator-model", default=None, help="LLM model for control-code decoration (default GOOGLE_MODEL_DECORATOR or GOOGLE_MODEL)")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt instead of calling the LLM")
    parser.add_argument("--no-time-context", action="store_true", help="Disable inclusion of date/time context")
    parser.add_argument("--no-decorate", action="store_true", help="Skip the second LLM decoration pass")
    parser.add_argument("--datetime", default=None, help="ISO datetime override for time context (e.g., 2025-08-16T14:30:00)")
    parser.add_argument("--no-news", action="store_true", help="Disable inclusion of recent headlines context")
    parser.add_argument("--news-feed", default=NEWS_FEED_DEFAULT, help="RSS/Atom feed URL for latest headlines context")
    parser.add_argument("--news-count", type=int, default=5, help="Number of headlines to include (default 5)")
    args = parser.parse_args()

    output = generate_dialogue(
        speaker=args.speaker,
        villagers_path=args.villagers,
        topic=args.topic,
        tone=args.tone,
        num_lines=args.num_lines,
        model=args.model,
        dry_run=args.dry_run,
        include_time_context=not args.no_time_context,
        iso_datetime=args.datetime,
        decorate=not args.no_decorate,
        decorator_model=args.decorator_model,
        include_news_context=not args.no_news,
        news_feed_url=args.news_feed,
        news_count=args.news_count,
    )
    print(output)


if __name__ == "__main__":
    main()


