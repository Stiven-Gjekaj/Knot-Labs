#!/usr/bin/env python3
"""
Build a curated, general + inclusive 1000-category master label list.

Output file: examples/mastercategories.txt

Rules:
- Construct >=1000 raw candidates across domains.
- Normalize: lowercase, no punctuation, replace '&' with 'and'.
- Deduplicate: fuzzy match with rapidfuzz.token_set_ratio > 93.
- Guarantee essentials across domains and minimum per-domain coverage (>=10).
- Deterministic (seed=42).
- Final 1000 sorted by domain then alphabetical.
- Each line format:
    a video about <category> | a photo of <category>

This script is self-contained and uses rapidfuzz if available; otherwise it
falls back to a simple token-set similarity that approximates token_set_ratio.
"""
from __future__ import annotations

import os
import re
import random
from typing import Dict, List, Tuple, Iterable, Set

try:
    from rapidfuzz.fuzz import token_set_ratio  # type: ignore
except Exception:  # pragma: no cover - fallback when not installed
    def token_set_ratio(a: str, b: str) -> float:
        at = set(a.split())
        bt = set(b.split())
        if not at or not bt:
            return 0.0
        inter = len(at & bt)
        score = 100.0 * (2 * inter) / (len(at) + len(bt))
        return float(score)


SEED = 42
random.seed(SEED)

TARGET_COUNT = 1000


def normalize(text: str) -> str:
    """Lowercase, replace & with 'and', remove punctuation except spaces.

    Also squashes repeated whitespace.
    """
    t = text.lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def unique_dedup(cands: Iterable[Tuple[str, str]], threshold: float = 93.0) -> List[Tuple[str, str]]:
    """Deduplicate by fuzzy token-set ratio on normalized values.

    cands: iterable of (domain, normalized_category)
    Returns a filtered list preserving first occurrence per near-duplicate cluster.
    """
    keep: List[Tuple[str, str]] = []
    seen_norm: List[str] = []
    for dom, cat in cands:
        is_dup = False
        for prev in seen_norm:
            if token_set_ratio(cat, prev) > threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append((dom, cat))
            seen_norm.append(cat)
    return keep


def build_candidates() -> Dict[str, List[str]]:
    """Return raw candidate categories per domain (>=1000 total across domains).

    The lists intentionally include some overlaps and near-duplicates; the
    dedup step will consolidate them.
    """
    # For geographic and culture coverage, mix global terms; avoid brand names.
    people = [
        "children", "teenagers", "adults", "seniors", "parents", "families",
        "students", "teachers", "scientists", "engineers", "nurses", "doctors",
        "farmers", "artists", "musicians", "actors", "athletes", "coaches",
        "activists", "volunteers", "leaders", "entrepreneurs", "refugees",
        "immigrants", "indigenous peoples", "people with disabilities",
        "community workers", "craftspeople", "photographers", "chefs",
        "journalists", "programmers", "gamers", "streamers", "health workers",
        "researchers", "writers", "poets", "dancers", "pilots", "drivers",
        "construction workers", "mechanics", "electricians", "plumbers",
        "tailors", "designers", "barbers", "bakers", "cooks", "caregivers",
        "firefighters", "paramedics", "police officers", "postal workers",
        "market vendors", "street performers", "tour guides", "monastics",
        "clergy", "sailors", "fisherfolk", "miners", "foresters",
    ]

    activities = [
        "cooking", "baking", "grilling", "barbecue", "reading", "writing",
        "painting", "drawing", "sewing", "knitting", "weaving", "gardening",
        "farming", "meditation", "yoga", "pilates", "cycling", "running",
        "walking", "hiking", "camping", "fishing", "swimming", "diving",
        "photography", "videography", "blogging", "vlogging", "podcasting",
        "coding", "robotics", "woodworking", "metalworking", "ceramics",
        "calligraphy", "origami", "birdwatching", "stargazing", "volunteering",
        "recycling", "upcycling", "thrifting", "shopping", "travel planning",
        "language learning", "chess", "board gaming", "card playing",
        "tabletop roleplaying", "speedrunning",
    ]

    sports = [
        "football (soccer)", "american football", "basketball", "baseball",
        "cricket", "rugby", "tennis", "table tennis", "badminton", "volleyball",
        "golf", "swimming", "track and field", "boxing", "kickboxing",
        "judo", "karate", "taekwondo", "mma", "wrestling", "gymnastics",
        "ice hockey", "field hockey", "handball", "water polo", "surfing",
        "skateboarding", "snowboarding", "skiing", "cross country skiing",
        "biathlon", "cycling road", "mountain biking", "bmx", "climbing",
        "bouldering", "equestrian", "sailing", "rowing", "canoe sprint",
        "kayaking", "dragon boat", "fencing", "archery", "snooker", "darts",
        "pickleball", "padel", "ultimate frisbee", "disc golf",
        "figure skating", "speed skating", "triathlon", "duathlon",
    ]

    arts = [
        "painting", "sculpture", "photography", "film", "theater", "ballet",
        "opera", "street art", "graffiti", "calligraphy", "ceramics",
        "printmaking", "illustration", "design", "architecture",
        "fashion design", "interior design", "industrial design", "poetry",
        "novels", "short stories", "comics", "animation", "3d modeling",
        "digital art", "tattoo art", "installation art", "performance art",
    ]

    music = [
        "classical music", "jazz", "blues", "rock", "pop", "hip hop", "rap",
        "r and b", "soul", "reggae", "ska", "punk", "metal", "country",
        "folk", "electronic", "edm", "house", "techno", "trance",
        "drum and bass", "dubstep", "ambient", "soundtracks", "world music",
        "latin music", "k pop", "afrobeats", "gospel", "choir", "orchestra",
        "band", "dj", "singing", "songwriting", "music production",
        "live concert", "music festival",
    ]

    gaming = [
        "action games", "adventure games", "role playing games", "mmorpgs",
        "moba", "first person shooters", "third person shooters",
        "strategy games", "real time strategy", "turn based strategy",
        "simulation games", "sports games", "racing games", "fighting games",
        "platformers", "puzzle games", "indie games", "retro gaming",
        "speedrunning", "esports", "game streaming", "vr gaming",
        "mobile gaming", "board games", "card games", "tabletop rpgs",
        "dungeons and dragons",
    ]

    tech = [
        "smartphones", "computers", "laptops", "tablets", "wearables",
        "smart home", "internet of things", "robotics", "artificial intelligence",
        "machine learning", "data science", "programming", "cybersecurity",
        "cloud computing", "devops", "blockchain", "cryptocurrency",
        "augmented reality", "virtual reality", "3d printing", "drones",
        "space technology", "biotechnology", "medical technology", "green tech",
        "electric vehicles", "autonomous vehicles", "renewable energy",
        "edge computing", "computer vision", "natural language processing",
    ]

    science = [
        "astronomy", "astrophysics", "physics", "chemistry", "biology",
        "ecology", "geology", "meteorology", "oceanography", "paleontology",
        "psychology", "neuroscience", "genetics", "microbiology", "botany",
        "zoology", "anthropology", "archaeology", "sociology", "mathematics",
        "statistics", "climate science", "environmental science",
        "space exploration", "quantum science",
    ]

    health = [
        "nutrition", "healthy eating", "mental health", "wellness", "fitness",
        "workouts", "strength training", "cardio", "yoga", "meditation",
        "mindfulness", "sleep health", "public health", "epidemiology",
        "medicine", "disease prevention", "first aid", "pharmacy", "nursing",
        "pregnancy", "parenting health", "elder care", "disability support",
        "therapy", "addiction recovery", "physiotherapy", "dental care",
    ]

    food = [
        "breakfast", "lunch", "dinner", "desserts", "baking", "grilling",
        "barbecue", "vegan cooking", "vegetarian cooking",
        "gluten free cooking", "seafood", "poultry", "beef dishes",
        "pork dishes", "soups", "stews", "salads", "sandwiches", "pasta",
        "pizza", "sushi", "noodles", "rice dishes", "curries", "street food",
        "snacks", "beverages", "coffee", "tea", "juices", "smoothies",
        "cocktails", "wine", "beer", "fermented foods", "spices", "herbs",
        "bread baking", "cakes", "cookies", "chocolate", "ice cream",
    ]

    fashion = [
        "streetwear", "couture", "vintage fashion", "sustainable fashion",
        "handmade fashion", "ethical fashion", "men fashion", "women fashion",
        "kids fashion", "plus size fashion", "modest fashion", "accessories",
        "shoes", "sneakers", "jewelry", "watches", "fashion shows", "runway",
        "makeup", "hairstyles", "skincare", "nail art",
    ]

    lifestyle = [
        "home decor", "minimalism", "organization", "productivity", "self care",
        "mindfulness", "travel", "budgeting", "personal finance", "parenting",
        "relationships", "pet care", "sustainability", "diy projects",
        "crafts", "hobbies", "photography", "videography", "vlogging",
        "podcasting", "motivation", "inspiration", "wellbeing",
    ]

    nature = [
        "forests", "mountains", "deserts", "beaches", "oceans", "rivers",
        "lakes", "waterfalls", "glaciers", "volcanoes", "caves", "savannas",
        "tundra", "wetlands", "rainforests", "coral reefs", "meadows",
        "prairies", "islands", "reefs",
    ]

    animals = [
        "dogs", "cats", "horses", "cattle", "sheep", "goats", "pigs",
        "chickens", "ducks", "geese", "turkeys", "rabbits", "hamsters",
        "guinea pigs", "parrots", "songbirds", "eagles", "owls", "hawks",
        "falcons", "penguins", "seals", "whales", "dolphins", "sharks",
        "rays", "turtles", "snakes", "lizards", "frogs", "toads",
        "butterflies", "bees", "ants", "spiders", "beetles", "wolves",
        "foxes", "bears", "lions", "tigers", "leopards", "cheetahs",
        "hyenas", "giraffes", "zebras", "hippos", "rhinos", "elephants",
        "kangaroos", "koalas", "pandas", "monkeys", "gorillas",
        "chimpanzees", "orangutans", "camels", "llamas", "alpacas",
        "crocodiles", "alligators",
    ]

    vehicles = [
        "cars", "trucks", "buses", "motorcycles", "bicycles", "scooters",
        "skateboards", "trains", "subways", "trams", "airplanes",
        "helicopters", "drones", "ships", "boats", "sailboats", "yachts",
        "submarines", "rockets", "spacecraft", "electric cars", "hybrid cars",
        "autonomous cars", "off road vehicles", "construction vehicles",
        "farm machinery",
    ]

    places_core = [
        "cities", "villages", "towns", "parks", "museums", "libraries",
        "schools", "universities", "hospitals", "temples", "churches",
        "mosques", "synagogues", "markets", "restaurants", "cafes",
        "theaters", "stadiums", "airports", "train stations", "castles",
        "palaces", "monuments", "landmarks", "national parks",
    ]

    # Add a diverse set of city and country names to push candidate count > 800
    cities = [
        "new york city", "los angeles", "chicago", "houston", "miami",
        "toronto", "vancouver", "mexico city", "sao paulo", "rio de janeiro",
        "buenos aires", "lima", "bogota", "santiago", "london", "manchester",
        "birmingham", "paris", "marseille", "berlin", "munich", "frankfurt",
        "hamburg", "rome", "milan", "naples", "madrid", "barcelona",
        "valencia", "lisbon", "porto", "amsterdam", "rotterdam", "brussels",
        "vienna", "zurich", "geneva", "stockholm", "oslo", "copenhagen",
        "helsinki", "prague", "warsaw", "budapest", "athens", "istanbul",
        "ankara", "moscow", "st petersburg", "kyiv", "tel aviv", "jerusalem",
        "cairo", "alexandria", "lagos", "nairobi", "addis ababa", "johannesburg",
        "capetown", "casablanca", "marrakesh", "algiers", "tunis",
        "doha", "dubai", "abu dhabi", "riyadh", "jeddah", "tehran",
        "karachi", "lahore", "mumbai", "delhi", "bangalore", "chennai",
        "kolkata", "dhaka", "jakarta", "bangkok", "kuala lumpur", "singapore",
        "manila", "hanoi", "ho chi minh city", "phnom penh", "vientiane",
        "hong kong", "taipei", "tokyo", "osaka", "kyoto", "seoul",
        "sapporo", "beijing", "shanghai", "guangzhou", "shenzhen", "chengdu",
        "wuhan", "xi an", "sydney", "melbourne", "brisbane", "auckland",
    ]

    events = [
        "weddings", "birthdays", "funerals", "festivals", "concerts",
        "parades", "protests", "ceremonies", "conferences", "workshops",
        "competitions", "tournaments", "fairs", "exhibitions", "graduations",
        "awards", "holidays", "new year", "carnival", "marathons",
        "hackathons", "lan parties", "cultural celebrations", "religious holidays",
    ]

    objects = [
        "smartphone", "laptop", "tablet", "camera", "drone", "television",
        "monitor", "keyboard", "mouse", "printer", "bottle", "cup", "glass",
        "mug", "plate", "bowl", "spoon", "fork", "knife", "chair", "table",
        "sofa", "bed", "lamp", "clock", "watch", "wallet", "bag",
        "backpack", "umbrella", "book", "notebook", "pen", "pencil",
        "marker", "paintbrush", "scissors", "toolbox", "hammer", "screwdriver",
        "wrench", "saw", "drill", "helmet", "goggles", "mask",
    ]

    weather = [
        "sunny", "cloudy", "rainy", "stormy", "snowy", "windy", "foggy",
        "hazy", "thunderstorms", "lightning", "rainbow", "hail", "blizzard",
        "heatwave", "cold snap", "drought", "flooding", "tornado", "hurricane",
        "typhoon",
    ]

    emotions = [
        "happiness", "joy", "sadness", "anger", "fear", "surprise",
        "disgust", "love", "affection", "pride", "shame", "guilt",
        "anxiety", "calm", "relief", "excitement", "boredom", "curiosity",
        "nostalgia", "hope", "frustration", "confidence", "embarrassment",
        "loneliness", "friendliness", "kindness", "empathy",
    ]

    culture = [
        "literature", "philosophy", "religion", "spirituality", "mythology",
        "folklore", "languages", "linguistics", "dance", "cuisine",
        "traditions", "rituals", "festivals", "film culture", "pop culture",
        "counterculture", "heritage", "museums", "fine arts", "crafts",
        "calligraphy", "traditional dress", "kimono", "sari", "hanbok",
    ]

    content_formats = [
        "tutorials", "reviews", "unboxings", "walkthroughs", "documentaries",
        "vlogs", "news reports", "interviews", "podcasts", "live streams",
        "shorts", "trailers", "behind the scenes", "timelapses", "asmr",
        "memes", "parodies", "challenges", "pranks", "how to", "explainers",
        "listicles", "top ten", "highlights", "montages", "comparisons",
        "debates", "roundtables", "panel discussions", "lectures", "lessons",
    ]

    adjectives = [
        "ancient", "modern", "rustic", "futuristic", "minimalist",
        "ornate", "metallic", "wooden", "colorful", "translucent",
    ]
    base_objects = [
        "bridge", "building", "car", "castle", "ship", "village",
        "garden", "robot", "statue", "festival", "library", "market",
        "museum", "park", "tower", "train", "computer", "phone",
        "instrument", "vehicle",
    ]
    styled_objects = [f"{adj} {obj}" for adj in adjectives for obj in base_objects]

    # Expand places by appending the word 'city' to city names to avoid conflict
    # with other contexts and to increase candidates.
    places = places_core + [f"{c} city" for c in cities]

    # Ensure each list is reasonably sized; total across domains should exceed 1000
    domain_map: Dict[str, List[str]] = {
        "PEOPLE": people,
        "ACTIVITIES": activities,
        "SPORTS": sports,
        "ARTS": arts,
        "MUSIC": music,
        "GAMING": gaming,
        "TECH": tech,
        "SCIENCE": science,
        "HEALTH": health,
        "FOOD": food,
        "FASHION": fashion,
        "LIFESTYLE": lifestyle,
        "NATURE": nature,
        "ANIMALS": animals,
        "VEHICLES": vehicles,
        "PLACES": places,
        "EVENTS": events,
        "OBJECTS": objects,
        "STYLED_OBJECTS": styled_objects,
        "WEATHER": weather,
        "EMOTIONS": emotions,
        "CULTURE": culture,
        "FORMATS": content_formats,
    }
    return domain_map


def guarantee_essentials(domains: Dict[str, List[str]]) -> Set[Tuple[str, str]]:
    """Return a set of (domain, normalized_category) for must-have items."""
    essentials: List[Tuple[str, str]] = [
        ("SPORTS", "football (soccer)"),
        ("SPORTS", "american football"),
        ("ANIMALS", "cats"),
        ("ANIMALS", "dogs"),
        ("PLACES", "new york city city"),  # normalized target in PLACES list
        ("PLACES", "tokyo city"),
        ("FOOD", "pizza"),
        ("FOOD", "sushi"),
        ("FORMATS", "tutorials"),
        ("FORMATS", "news reports"),
        ("EMOTIONS", "happiness"),
        ("EMOTIONS", "sadness"),
    ]
    out: Set[Tuple[str, str]] = set()
    for dom, cat in essentials:
        out.add((dom, normalize(cat)))
    return out


def build_final(target_count: int = TARGET_COUNT) -> List[Tuple[str, str]]:
    domains = build_candidates()

    # Normalize and tag by domain
    tagged: List[Tuple[str, str]] = []
    for dom, items in domains.items():
        for it in items:
            tagged.append((dom, normalize(it)))

    # Deduplicate across all using fuzzy token-set ratio
    deduped = unique_dedup(tagged, threshold=93.0)

    # Partition by domain after dedup
    by_dom: Dict[str, List[str]] = {}
    for dom, cat in deduped:
        by_dom.setdefault(dom, []).append(cat)

    # Shuffle deterministically within domains to avoid bias
    rng = random.Random(SEED)
    for cats in by_dom.values():
        rng.shuffle(cats)

    # Ensure minimum coverage per domain (>=10). Then fill remaining slots.
    final: List[Tuple[str, str]] = []
    required_min = 10
    must_have = guarantee_essentials(domains)
    included: Set[str] = set()

    # Add essentials first
    for dom, cat in must_have:
        if cat in by_dom.get(dom, []) and cat not in included:
            final.append((dom, cat))
            included.add(cat)

    # Ensure per-domain minimums
    for dom, cats in by_dom.items():
        count = 0
        for c in cats:
            if c in included:
                continue
            final.append((dom, c))
            included.add(c)
            count += 1
            if count >= required_min:
                break

    # Fill remaining up to target_count by round-robin across domains
    domain_keys = list(by_dom.keys())
    idx_map = {d: 0 for d in domain_keys}
    # Move indices past already used items
    for d in domain_keys:
        used = set(c for (dd, c) in final if dd == d)
        base = by_dom[d]
        i = 0
        while i < len(base) and base[i] in used:
            i += 1
        idx_map[d] = i

    while len(final) < target_count:
        progressed = False
        for d in domain_keys:
            cats = by_dom[d]
            i = idx_map[d]
            while i < len(cats) and cats[i] in included:
                i += 1
            if i < len(cats):
                final.append((d, cats[i]))
                included.add(cats[i])
                idx_map[d] = i + 1
                progressed = True
                if len(final) >= target_count:
                    break
        if not progressed:
            break  # no more candidates

    # If we somehow exceed (should not), truncate deterministically
    final = final[:target_count]

    # Sort by domain, then alphabetical within domain
    final.sort(key=lambda x: (x[0], x[1]))
    return final


def write_master(lines: List[Tuple[str, str]], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        for dom, cat in lines:
            f.write(f"a video about {cat} | a photo of {cat}\n")


def main() -> None:
    domains = build_candidates()
    raw_count = sum(len(v) for v in domains.values())

    # Normalize + dedup once for stats
    tagged: List[Tuple[str, str]] = []
    for dom, items in domains.items():
        for it in items:
            tagged.append((dom, normalize(it)))
    deduped = unique_dedup(tagged)

    final = build_final(TARGET_COUNT)

    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "examples"))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "mastercategories.txt")
    out_path = os.path.abspath(out_path)
    write_master(final, out_path)

    print(f"Candidates: {raw_count}")
    print(f"Unique (post-normalize+dedup): {len(deduped)}")
    print(f"Final: {len(final)} (expected {TARGET_COUNT})")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
