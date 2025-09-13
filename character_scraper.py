import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, Tag


BASE_URL = "https://animalcrossing.fandom.com"
VILLAGER_LIST_URL = f"{BASE_URL}/wiki/Villager_list_(Animal_Crossing)"


@dataclass
class VillagerContext:
    name: str
    url: str
    gender: Optional[str] = None
    personality: Optional[str] = None
    species: Optional[str] = None
    birthday: Optional[str] = None
    catchphrase: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_url: Optional[str] = None

    quote: Optional[str] = None
    summary: Optional[str] = None
    hobby: Optional[str] = None
    house_theme: Optional[str] = None
    preferred_style: Optional[str] = None
    preferred_colors: Optional[str] = None

    appearance_section: Optional[str] = None
    personality_section: Optional[str] = None
    house_section: Optional[str] = None
    pocket_camp_profile: Optional[str] = None
    trivia: List[str] = field(default_factory=list)
    quick_answers: List[str] = field(default_factory=list)
    aliases: Dict[str, str] = field(default_factory=dict)


class FandomVillagerScraper:
    def __init__(
        self,
        delay_seconds: float = 0.8,
        timeout_seconds: float = 20.0,
        cache_dir: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36 (AC-Decomp VM scraper for research)"
                )
            }
        )
        self.cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        self.max_pages = max_pages

    # ----------------------------- HTTP helpers ------------------------------
    def _cache_path(self, key: str) -> Optional[str]:
        if not self.cache_dir:
            return None
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", key)
        safe = safe.rstrip(".")
        return os.path.join(self.cache_dir, safe)

    def _get(self, url: str) -> str:
        cache_path = self._cache_path(url)
        if cache_path and os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()

        for attempt in range(5):
            try:
                resp = self.session.get(url, timeout=self.timeout_seconds)
                if resp.status_code == 200:
                    html = resp.text
                    if cache_path:
                        with open(cache_path, "w", encoding="utf-8") as f:
                            f.write(html)
                    # politeness delay
                    time.sleep(self.delay_seconds)
                    return html
                # Backoff on non-200
                time.sleep(self.delay_seconds * (attempt + 1))
            except requests.RequestException:
                time.sleep(self.delay_seconds * (attempt + 1))

        raise RuntimeError(f"Failed to GET {url}")

    # ----------------------------- Parse helpers -----------------------------
    @staticmethod
    def _text(el: Optional[Tag]) -> str:
        if not el:
            return ""
        return el.get_text(separator=" ", strip=True)

    @staticmethod
    def _clean_quotes(text: str) -> str:
        return text.strip().strip("\"").strip("“").strip("”").strip()

    @staticmethod
    def _normalize_space(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _join_url(href: str) -> str:
        if href.startswith("http"):
            return href
        return BASE_URL + href

    # ----------------------------- Main list page ----------------------------
    def fetch_villager_list(self) -> List[VillagerContext]:
        html = self._get(VILLAGER_LIST_URL)
        soup = BeautifulSoup(html, "html.parser")

        villages: List[VillagerContext] = []

        # The list is inside one or more tables. We'll scan all table rows that
        # look like villager entries (have 5-6 tds and a link in first td).
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) < 5:
                    continue

                name_link = cols[0].find("a", href=True)
                if not name_link or not name_link.get("href", "").startswith("/wiki/"):
                    continue

                name = self._text(name_link)
                url = self._join_url(name_link["href"]) if name_link else None
                if not name or not url:
                    continue

                # Image (thumbnail)
                thumb_img = cols[1].find("img") if len(cols) > 1 else None
                thumbnail_url = thumb_img.get("src") if thumb_img else None

                # Personality + gender (symbol may be inside the same td)
                personality_td = cols[2] if len(cols) > 2 else None
                personality_link = personality_td.find("a") if personality_td else None
                personality = self._text(personality_link) if personality_link else None
                # Gender symbol parsing
                gender_symbol = None
                if personality_td:
                    text_in_cell = personality_td.get_text(" ", strip=True)
                    if "♂" in text_in_cell:
                        gender_symbol = "Male"
                    elif "♀" in text_in_cell:
                        gender_symbol = "Female"

                species_td = cols[3] if len(cols) > 3 else None
                species_link = species_td.find("a") if species_td else None
                species = self._text(species_link) if species_link else None

                birthday_td = cols[4] if len(cols) > 4 else None
                birthday = self._text(birthday_td) if birthday_td else None
                # Remove suffix like 11th
                birthday = re.sub(r"(st|nd|rd|th)", "", birthday or "").strip()

                catchphrase_td = cols[5] if len(cols) > 5 else None
                catchphrase = None
                if catchphrase_td:
                    italic = catchphrase_td.find("i")
                    catchphrase = self._clean_quotes(self._text(italic or catchphrase_td))

                villages.append(
                    VillagerContext(
                        name=name,
                        url=url,
                        gender=gender_symbol,
                        personality=personality,
                        species=species,
                        birthday=birthday,
                        catchphrase=catchphrase,
                        thumbnail_url=thumbnail_url,
                    )
                )

        # Some pages have multiple lists; dedupe by name and keep first
        dedup: Dict[str, VillagerContext] = {}
        for v in villages:
            if v.name not in dedup:
                dedup[v.name] = v

        result = list(dedup.values())
        if self.max_pages is not None:
            result = result[: self.max_pages]
        return result

    # ----------------------------- Villager page -----------------------------
    def _extract_infobox_fields(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        infobox = soup.find("aside", class_=re.compile(r"portable-infobox"))
        if not infobox:
            return None, None, None, None, None, None

        image_url = None
        fig = infobox.find("figure")
        if fig:
            img = fig.find("img")
            if img and img.get("src"):
                image_url = img["src"]

        quote = None
        figcaption = infobox.find("figcaption")
        if figcaption:
            quote = self._clean_quotes(self._text(figcaption))

        def find_value_by_source(source_name: str) -> Optional[str]:
            el = infobox.find(attrs={"data-source": source_name})
            if not el:
                return None
            return self._text(el.find(class_=re.compile(r"pi-data-value|pi-font")) or el)

        gender = find_value_by_source("Gender")
        personality = find_value_by_source("Personality")
        species = find_value_by_source("Species")
        birthday = find_value_by_source("Birthday")
        catchphrase = find_value_by_source("Catchphrase")

        return (
            image_url,
            quote,
            gender,
            personality,
            species,
            birthday or None if birthday else None,
            catchphrase,
        )

    def _extract_section_text(self, soup: BeautifulSoup, section_id: str) -> Optional[str]:
        header = soup.find(id=section_id)
        if not header:
            return None
        # Collect until next h2
        collected_parts: List[str] = []
        for sibling in header.parent.next_siblings:
            if isinstance(sibling, Tag) and sibling.name == "h2":
                break
            if isinstance(sibling, Tag) and sibling.name in {"p", "ul", "ol", "dl"}:
                collected_parts.append(self._normalize_space(self._text(sibling)))
        text = "\n".join([t for t in collected_parts if t])
        return text or None

    # Removed quick answers and aliases extraction per requirements

    def _extract_summary_hobby(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        # The first paragraph after the top tables often contains a summary and hobby
        content = soup.find("div", class_=re.compile(r"mw-parser-output"))
        if not content:
            return None, None
        paragraphs = [p for p in content.find_all("p", recursive=False) if self._text(p)]
        summary = None
        hobby = None
        if paragraphs:
            summary = self._normalize_space(self._text(paragraphs[0]))
            # Try to find 'hobby' mention anywhere in first two paragraphs
            joined = " ".join(self._normalize_space(self._text(p)) for p in paragraphs[:2])
            match = re.search(r"hobby\)?\s*(?:is|:)?\s*([A-Za-z\- ]+)\.", joined, flags=re.IGNORECASE)
            if match:
                hobby = match.group(1).strip()
        return summary, hobby

    def _extract_house_theme_prefs(self, house_text: Optional[str], trivia_list: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        house_theme = None
        preferred_style = None
        preferred_colors = None

        if house_text:
            # Look for 'theme' or notable descriptors
            for line in house_text.split("\n"):
                if "theme" in line.lower() or "style" in line.lower():
                    house_theme = (house_theme or "") + ("; " if house_theme else "") + line

        # Parse trivia for preferred style/colors
        for item in trivia_list:
            m_style = re.search(r"preferred style is ([^,]+)", item, flags=re.IGNORECASE)
            if m_style:
                preferred_style = m_style.group(1).strip()
            m_colors = re.search(r"preferred colors are ([^.]+)\.", item, flags=re.IGNORECASE)
            if m_colors:
                preferred_colors = m_colors.group(1).strip()

        return house_theme, preferred_style, preferred_colors

    def parse_villager_page(self, url: str) -> Dict:
        html = self._get(url)
        soup = BeautifulSoup(html, "html.parser")

        image_url, quote, gender, personality, species, birthday, infobox_catchphrase = self._extract_infobox_fields(soup)

        appearance = self._extract_section_text(soup, "Appearance")
        personality_section = self._extract_section_text(soup, "Personality")
        house = self._extract_section_text(soup, "House")

        # Pocket Camp profile intentionally omitted

        # Trivia list items
        trivia_items: List[str] = []
        trivia_header = soup.find(id="Trivia")
        if trivia_header:
            ul = trivia_header.find_next("ul")
            if ul:
                for li in ul.find_all("li", recursive=False):
                    text = self._normalize_space(self._text(li))
                    if text:
                        trivia_items.append(text)

        # Summary omitted; keep hobby only
        _summary, hobby = self._extract_summary_hobby(soup)
        house_theme, preferred_style, preferred_colors = self._extract_house_theme_prefs(house, trivia_items)

        return {
            "image_url": image_url,
            "quote": quote,
            "catchphrase": infobox_catchphrase,
            "appearance_section": appearance,
            "personality_section": personality_section,
            "house_section": house,
            "trivia": trivia_items,
            "hobby": hobby,
            "house_theme": house_theme,
            "preferred_style": preferred_style,
            "preferred_colors": preferred_colors,
            # Override-able fields if infobox provided newer values
            "gender": gender,
            "personality": personality,
            "species": species,
            "birthday": birthday,
        }

    # ----------------------------- Orchestration -----------------------------
    def scrape_all(self) -> Dict[str, Dict]:
        base_list = self.fetch_villager_list()
        villagers: Dict[str, Dict] = {}

        for index, base in enumerate(base_list, start=1):
            try:
                details = self.parse_villager_page(base.url)
            except Exception as e:
                # Continue on single failure
                details = {"error": str(e)}

            villager_record = {
                "name": base.name,
                "url": base.url,
                "gender": details.get("gender") or base.gender,
                "personality": details.get("personality") or base.personality,
                "species": details.get("species") or base.species,
                "birthday": details.get("birthday") or base.birthday,
                "catchphrase": details.get("catchphrase") or base.catchphrase,
                "thumbnail_url": base.thumbnail_url,
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

            villagers[base.name] = villager_record

        return villagers


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Scrape Animal Crossing villagers from Fandom into a structured JSON.")
    parser.add_argument("--output", "-o", default="villagers.json", help="Path to write JSON output.")
    parser.add_argument("--max", type=int, default=None, help="Limit number of villagers to scrape (for testing).")
    parser.add_argument("--delay", type=float, default=0.8, help="Delay between requests in seconds.")
    parser.add_argument("--cache", default=".cache/villagers", help="Directory to cache fetched HTML (speeds up dev runs). Use empty string to disable.")
    args = parser.parse_args(argv)

    cache_dir = args.cache if args.cache else None
    scraper = FandomVillagerScraper(delay_seconds=args.delay, cache_dir=cache_dir, max_pages=args.max)
    villagers = scraper.scrape_all()

    # Keyed by villager name already
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(villagers, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(villagers)} villagers to {args.output}")


if __name__ == "__main__":
    main()


