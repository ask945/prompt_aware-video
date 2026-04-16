import re
import spacy

nlp = spacy.load("en_core_web_sm")

# ============================================================
# INTENT RULES
# Keywords here use LEMMA form — matched against token.lemma_
# so "falls", "falling", "fell" all match lemma "fall"
# Multi-word phrases are still matched against raw query string
# ============================================================

# Lemma-based keywords (single words — matched via spaCy lemma)
EVENT_LEMMAS = {
    "fall", "enter", "leave", "run", "jump", "sit", "stand",
    "fight", "crash", "stop", "cross", "climb", "push", "pull",
    "kick", "throw", "hit", "drop", "slip", "trip", "collide",
    "arrive", "depart", "open", "close",
    "break", "explode", "catch", "grab", "pick", "place", "walk",
    "move", "turn", "spin", "flip", "slide", "roll", "bounce",
    "lift", "carry", "drag", "swing",
    # NOTE: "appear"/"disappear" intentionally excluded —
    # they indicate temporal search scope, not action events
}

INTENT_RULES = {
    "event": {
        "keywords": [],  # handled via lemma matching below
        "phrases": [],   # multi-word phrases matched against raw query
        "priority": 8,
    },
    "counting": {
        "keywords": [],
        "phrases": [
            "how many", "count", "number of", "total number",
            "how much", "quantity",
        ],
        "priority": 7,
    },
    "ocr": {
        "keywords": ["ocr"],
        "phrases": [
            "extract text", "what does it say",
            "what is written", "what text",
        ],
        "lemmas": {"write", "read"},
        "nouns": {"text", "sign", "board", "display", "letter", "word", "writing"},
        "priority": 6,
    },
    "scene": {
        "keywords": [],
        "phrases": [
            "what is happening", "what's happening",
            "what do you see", "tell me about",
            "explain the video", "what is going on",
            "what's going on", "describe the video",
        ],
        "lemmas": {"describe", "summarize", "explain", "overview"},
        "nouns": {"scene", "summary", "overview"},
        "priority": 5,
    },
    "object": {
        "keywords": [],
        "phrases": [
            "is there", "look for", "can you see",
            "do you see", "where is",
        ],
        "lemmas": {"find", "detect", "search", "locate", "spot", "identify", "show"},
        "priority": 2,
    },
    # "object_color" and "color" resolved dynamically
    # based on presence of target + color — not keyword based
}


# ============================================================
# TEMPORAL SCOPE RULES — HOW to traverse the video
# Extracted INDEPENDENTLY from intent
# ============================================================

SCOPE_SEARCH_KEYWORDS = [
    "first appear", "last appear", "first seen", "last seen",
    "first time", "last time", "when does", "when did",
    "when is", "appear first", "appear last", "show up",
]


# ============================================================
# COLOR VOCABULARY
# ============================================================

COLORS = {
    "red", "blue", "green", "yellow", "orange", "purple", "violet",
    "pink", "black", "white", "brown", "grey", "gray", "cyan",
    "magenta", "maroon", "navy", "teal", "beige", "golden", "silver",
}


# ============================================================
# YOLO SUPPORTED CLASSES (COCO 80 + common aliases)
# ============================================================

YOLO_CLASSES = {
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
    # Common aliases
    "man", "woman", "people", "child", "kid", "baby", "vehicle",
    "animal", "phone", "mobile", "sofa", "table", "monitor", "screen",
}

TARGET_ALIASES = {
    "man": "person", "woman": "person", "people": "person",
    "child": "person", "kid": "person", "baby": "person",
    "vehicle": "car", "phone": "cell phone", "mobile": "cell phone",
    "sofa": "couch", "monitor": "tv", "screen": "tv",
    "ball": "sports ball",
}

# Nouns to ignore — not visual targets
IGNORE_NOUNS = {
    "video", "frame", "time", "scene", "text", "moment",
    "clip", "footage", "recording", "part", "section",
    "number", "amount", "total", "sum", "count",
    "type", "kind", "sort", "group", "lot", "bunch",
    "object", "thing", "stuff", "item", "something", "anything",
    "one", "ones", "everything", "anyone", "someone",
}


# ============================================================
# EXTRACTION FUNCTIONS
# ============================================================

def extract_timestamp(query_lower: str) -> float | None:
    """Extract timestamp in seconds. Independent of intent."""

    # MM:SS format
    match = re.search(r"(\d{1,2}):(\d{2})", query_lower)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))

    # X min format
    match = re.search(r"(\d+)\s*min", query_lower)
    if match:
        return int(match.group(1)) * 60

    # X sec/second format
    match = re.search(r"(\d+)\s*sec", query_lower)
    if match:
        return float(match.group(1))

    return None


def extract_temporal_scope(query_lower: str, timestamp: float | None) -> str:
    """
    Determine HOW to traverse the video.
    Completely independent of intent.

    Returns:
        "specific" — jump to exact timestamp
        "search"   — find first/last occurrence (binary search)
        "full"     — scan entire video
    """
    if timestamp is not None:
        return "specific"

    for keyword in SCOPE_SEARCH_KEYWORDS:
        if keyword in query_lower:
            return "search"

    return "full"


def extract_color(doc) -> str | None:
    """Extract color attribute from spaCy doc."""
    for token in doc:
        if token.text.lower() in COLORS:
            return token.text.lower()
    return None


def _is_ignored(token) -> bool:
    """Check if a token should be ignored as a target (by text or lemma)."""
    return token.text.lower() in IGNORE_NOUNS or token.lemma_ in IGNORE_NOUNS


def extract_target(doc) -> str | None:
    """
    Extract target object using 3-layer strategy:
    1. Match against known YOLO classes
    2. Use spaCy dependency parsing (dobj, pobj, nsubj)
    3. Fallback to any noun
    """
    target = None

    # Layer 1: Direct YOLO class match
    for token in doc:
        word = token.text.lower()
        if word in YOLO_CLASSES and word not in COLORS and not _is_ignored(token):
            target = word
            break

    # Layer 2: Dependency parsing
    if not target:
        for token in doc:
            if token.dep_ in ("dobj", "pobj", "nsubj", "attr") and token.pos_ in ("NOUN", "PROPN"):
                if not _is_ignored(token) and token.text.lower() not in COLORS:
                    target = token.text.lower()
                    break

    # Layer 3: Any noun fallback
    if not target:
        for token in doc:
            if token.pos_ == "NOUN":
                if not _is_ignored(token) and token.text.lower() not in COLORS:
                    target = token.text.lower()
                    break

    # Normalize aliases
    if target and target in TARGET_ALIASES:
        target = TARGET_ALIASES[target]

    return target


def classify_intent(query_lower: str, doc, target: str | None, color: str | None) -> str:
    """
    Classify WHAT to analyze.
    Uses 4 matching strategies in order:
      1. Multi-word phrase match against raw query
      2. Lemma match against spaCy tokens
      3. Intent-specific noun match
      4. Verb POS fallback for event detection
    Does NOT consider temporal scope — that's a separate axis.
    """
    # Collect lemmas and nouns from spaCy doc
    doc_lemmas = {token.lemma_ for token in doc}
    doc_nouns = {token.text.lower() for token in doc if token.pos_ == "NOUN"}
    doc_verbs = {token.lemma_ for token in doc if token.pos_ == "VERB"}

    scored = []

    for intent_name, rule in INTENT_RULES.items():
        matched = False

        # Strategy 1: exact keyword match in raw query
        for kw in rule.get("keywords", []):
            if kw in query_lower:
                matched = True
                break

        # Strategy 2: multi-word phrase match in raw query
        if not matched:
            for phrase in rule.get("phrases", []):
                if phrase in query_lower:
                    matched = True
                    break

        # Strategy 3: lemma match (covers all tenses automatically)
        if not matched:
            rule_lemmas = rule.get("lemmas", set())
            if rule_lemmas & doc_lemmas:
                matched = True

        # Strategy 4: intent-specific noun match
        if not matched:
            rule_nouns = rule.get("nouns", set())
            if rule_nouns & doc_nouns:
                matched = True

        if matched:
            scored.append((intent_name, rule["priority"]))

    # Strategy 5: event lemma fallback
    # Check ALL token lemmas (not just POS=VERB) because spaCy small model
    # sometimes tags action words as NOUN (e.g. "bounce" in "does the ball bounce?")
    if not any(s[0] == "event" for s in scored):
        if doc_lemmas & EVENT_LEMMAS:
            scored.append(("event", INTENT_RULES["event"]["priority"]))

    scored.sort(key=lambda x: x[1], reverse=True)

    if scored:
        best = scored[0][0]

        # Upgrade object → object_color if both target and color exist
        if best == "object" and color and target:
            return "object_color"

        # Downgrade object → color if color exists but no concrete target
        # e.g. "Find red objects" → target is None (generic noun), color is "red"
        if best == "object" and color and not target:
            return "color"

        return best

    # No match at all — resolve from entities
    if color and target:
        return "object_color"
    if color and not target:
        return "color"
    if target:
        return "object"

    return "scene"


def calculate_confidence(intent: str, temporal_scope: str, target: str | None, color: str | None) -> float:
    """Confidence based on how much structured info was extracted."""
    if intent == "object_color" and target and color:
        return 0.95
    if intent == "object" and target:
        return 0.90 if temporal_scope == "full" else 0.95
    if intent == "counting" and target:
        return 0.90
    if intent == "event":
        return 0.85 if target else 0.75
    if intent == "color" and color:
        return 0.85
    if intent in ("ocr", "scene"):
        return 0.80
    return 0.60


# ============================================================
# MAIN PARSE FUNCTION
# ============================================================

def parse(query: str) -> dict:
    """
    Main entry point. Parse a natural language query.

    Returns:
        dict with keys:
            intent         — WHAT to analyze (independent axis 1)
            target         — object to look for (nullable)
            attribute      — color or modifier (nullable)
            temporal_scope — HOW to traverse video (independent axis 2)
            timestamp      — specific time in seconds (nullable)
            raw_query      — original query string
            confidence     — parse confidence score
    """
    query_lower = query.lower().strip()
    doc = nlp(query_lower)

    # All extractions are independent of each other
    target = extract_target(doc)
    color = extract_color(doc)
    timestamp = extract_timestamp(query_lower)

    # Axis 1: WHAT to analyze (independent of scope)
    intent = classify_intent(query_lower, doc, target, color)

    # Axis 2: HOW to traverse (independent of intent)
    temporal_scope = extract_temporal_scope(query_lower, timestamp)

    # Special cases
    if intent == "ocr":
        target = target or "text"
    if intent == "scene":
        target = None

    confidence = calculate_confidence(intent, temporal_scope, target, color)

    return {
        "intent": intent,
        "target": target,
        "attribute": color,
        "temporal_scope": temporal_scope,
        "timestamp": timestamp,
        "raw_query": query,
        "confidence": confidence,
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    test_queries = [
        # Same intent (object), different scopes — proves independence
        ("Is there a car?",                    "object",       "full"),
        ("Is there a car at 2:30?",            "object",       "specific"),
        ("When does the car first appear?",    "object",       "search"),

        # Same intent (object_color), different scopes
        ("Is there a red car?",                "object_color", "full"),
        ("Is there a red car at 1:45?",        "object_color", "specific"),
        ("When does the red car first appear?","object_color", "search"),
        ("when does white car appear first?",  "object_color", "search"),
        ("when does red car appear?",          "object_color", "search"),

        # Same intent (counting), different scopes
        ("How many people are there?",         "counting",     "full"),
        ("How many dogs at 1:00?",             "counting",     "specific"),

        # Same intent (event), different scopes
        ("Does anyone fall?",                  "event",        "full"),
        ("When does a person fall?",           "event",        "search"),

        # Lemma-based event detection (no exact keyword match needed)
        ("When does the ball bounce?",         "event",        "search"),
        ("Does anyone climb the wall?",        "event",        "full"),
        ("The person slipped",                 "event",        "full"),
        ("When did the car explode?",          "event",        "search"),

        # Other intents
        ("Find red objects",                   "color",        "full"),
        ("What text is on the screen?",        "ocr",          "full"),
        ("Read the sign at 0:30",              "ocr",          "specific"),
        ("Describe the video",                 "scene",        "full"),

        # Edge cases
        ("red",                                "color",        "full"),
        ("car",                                "object",       "full"),
        ("hello",                              "scene",        "full"),
    ]

    print(f"\n{'='*110}")
    print(f"{'QUERY':<45} {'EXPECTED INTENT':<16} {'EXPECTED SCOPE':<12} {'GOT INTENT':<16} {'GOT SCOPE':<12} {'PASS'}")
    print(f"{'='*110}")

    passed = 0
    failed = 0

    for q, expected_intent, expected_scope in test_queries:
        r = parse(q)
        intent_ok = r["intent"] == expected_intent
        scope_ok = r["temporal_scope"] == expected_scope
        ok = intent_ok and scope_ok

        if ok:
            passed += 1
        else:
            failed += 1

        print(
            f"{q:<45} "
            f"{expected_intent:<16} "
            f"{expected_scope:<12} "
            f"{r['intent']:<16} "
            f"{r['temporal_scope']:<12} "
            f"{'PASS' if ok else 'FAIL <<<'}"
        )

    print(f"{'='*110}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")

    # Independence proof
    print("\n--- Independence Proof ---")
    print("Same intent, different scopes:\n")

    proofs = [
        "Is there a car?",
        "Is there a car at 2:30?",
        "When does the car first appear?",
    ]
    for q in proofs:
        r = parse(q)
        print(f"  \"{q}\"")
        print(f"  → intent: {r['intent']}, temporal_scope: {r['temporal_scope']}\n")