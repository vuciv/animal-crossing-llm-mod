#!/usr/bin/env python3
import argparse
import json
import os
from typing import Optional, Dict

from character_scraper import FandomVillagerScraper


def upsert_character(name: str, url: str, output_path: str) -> None:
    scraper = FandomVillagerScraper(delay_seconds=0.5, cache_dir=None)
    details = scraper.parse_villager_page(url)

    record: Dict[str, Optional[str]] = {
        "name": name,
        "url": url,
        "gender": details.get("gender"),
        "personality": details.get("personality"),
        "species": details.get("species"),
        "birthday": details.get("birthday"),
        "catchphrase": details.get("catchphrase"),
        "thumbnail_url": None,
        "image_url": details.get("image_url"),
        "quote": details.get("quote"),
        "hobby": details.get("hobby"),
        "house_theme": details.get("house_theme"),
        "preferred_style": details.get("preferred_style"),
        "preferred_colors": details.get("preferred_colors"),
        "appearance_section": details.get("appearance_section"),
        "personality_section": details.get("personality_section"),
        "house_section": details.get("house_section"),
        "trivia": details.get("trivia", []),
    }

    data: Dict[str, Dict] = {}
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    data[name] = record

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Upserted '{name}' into {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Add or update a single character in villagers.json from a Fandom URL.")
    parser.add_argument("--name", required=True, help="Character name to use as the key (e.g., 'Tom Nook')")
    parser.add_argument("--url", required=True, help="Fandom wiki URL for the character")
    parser.add_argument("--output", default="villagers.json", help="Path to villagers.json (default: villagers.json)")
    args = parser.parse_args()

    upsert_character(args.name, args.url, args.output)


if __name__ == "__main__":
    main()


