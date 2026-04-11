"""
Strategy Selector Module

Takes two independent axes from prompt_interpreter:
  - intent: WHAT to analyze
  - temporal_scope: HOW to traverse video

Returns a complete strategy config:
  - strategy: sampling method
  - modules: which CV modules to activate
  - sample_rate: frames per second to sample
  - early_stop: whether to stop on confident result
  - confidence_threshold: minimum confidence to trigger early stop

Strategy = f(intent, temporal_scope)
"""


# ============================================================
# MODULE MAPPING — intent → which CV modules to activate
# ============================================================

INTENT_TO_MODULES = {
    "object":       ["yolo"],
    "color":        ["hsv"],
    "object_color": ["yolo", "hsv"],
    "ocr":          ["ocr"],
    "counting":     ["yolo", "counter"],
    "event":        ["motion", "yolo"],
    "scene":        ["yolo", "hsv"],
}

# ============================================================
# SAMPLING MAPPING — temporal_scope → sampling method
# ============================================================

SCOPE_TO_SAMPLING = {
    "full":     "uniform",
    "specific": "direct_seek",
    "search":   "binary_search",
}

# ============================================================
# SAMPLE RATE — intent → frames per second
# Some intents need more frames than others
# ============================================================

INTENT_TO_SAMPLE_RATE = {
    "object":       1,      # 1 frame per second
    "color":        1,
    "object_color": 1,
    "ocr":          0.5,    # 1 frame per 2 seconds (text doesn't change fast)
    "counting":     1,
    "event":        3,      # 3 frames per second (need temporal detail)
    "scene":        0.33,   # 1 frame per 3 seconds (sparse overview)
}

# ============================================================
# EARLY STOP RULES — which combinations allow early termination
# ============================================================

EARLY_STOP_RULES = {
    # (intent, temporal_scope) → (early_stop, confidence_threshold)

    # Object — stop when found, except counting needs all frames
    ("object", "full"):         (True, 0.85),
    ("object", "specific"):     (False, 0.0),   # single frame, no stopping needed
    ("object", "search"):       (True, 0.85),

    # Color
    ("color", "full"):          (True, 0.80),
    ("color", "specific"):      (False, 0.0),
    ("color", "search"):        (True, 0.80),

    # Object + Color
    ("object_color", "full"):   (True, 0.85),
    ("object_color", "specific"): (False, 0.0),
    ("object_color", "search"): (True, 0.85),

    # OCR — stop once text is found
    ("ocr", "full"):            (True, 0.70),
    ("ocr", "specific"):        (False, 0.0),
    ("ocr", "search"):          (True, 0.70),

    # Counting — NEVER early stop, needs all frames for accurate count
    ("counting", "full"):       (False, 0.0),
    ("counting", "specific"):   (False, 0.0),
    ("counting", "search"):     (False, 0.0),

    # Event — stop once event is detected
    ("event", "full"):          (True, 0.80),
    ("event", "specific"):      (False, 0.0),
    ("event", "search"):        (True, 0.80),

    # Scene — NEVER early stop, needs full overview
    ("scene", "full"):          (False, 0.0),
    ("scene", "specific"):      (False, 0.0),
    ("scene", "search"):        (False, 0.0),
}

# Default if combination not found
DEFAULT_EARLY_STOP = (True, 0.85)


# ============================================================
# MAIN SELECT FUNCTION
# ============================================================

def select(intent: str, temporal_scope: str) -> dict:
    """
    Main entry point. Maps (intent, temporal_scope) → strategy config.

    Args:
        intent: from prompt_interpreter (object, color, object_color, ocr, counting, event, scene)
        temporal_scope: from prompt_interpreter (full, specific, search)

    Returns:
        dict with keys:
            strategy             — sampling method (uniform / direct_seek / binary_search)
            modules              — list of CV modules to activate
            sample_rate          — frames per second to process
            early_stop           — whether to stop on confident result
            confidence_threshold — minimum confidence to trigger stop
            intent               — passed through for reference
            temporal_scope       — passed through for reference
    """

    # Get sampling strategy from temporal_scope
    strategy = SCOPE_TO_SAMPLING.get(temporal_scope, "uniform")

    # Get CV modules from intent
    modules = INTENT_TO_MODULES.get(intent, ["yolo"])

    # Get sample rate from intent
    sample_rate = INTENT_TO_SAMPLE_RATE.get(intent, 1)

    # Override sample rate for specific scope — not applicable
    if temporal_scope == "specific":
        sample_rate = 0  # not used, direct seek grabs exact frame

    # Get early stop rules from (intent, temporal_scope) pair
    early_stop, confidence_threshold = EARLY_STOP_RULES.get(
        (intent, temporal_scope),
        DEFAULT_EARLY_STOP
    )

    return {
        "strategy": strategy,
        "modules": modules,
        "sample_rate": sample_rate,
        "early_stop": early_stop,
        "confidence_threshold": confidence_threshold,
        "intent": intent,
        "temporal_scope": temporal_scope,
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_cases = [
        # (intent, temporal_scope, expected_strategy, expected_modules, expected_early_stop)
        ("object",       "full",     "uniform",       ["yolo"],              True),
        ("object",       "specific", "direct_seek",   ["yolo"],              False),
        ("object",       "search",   "binary_search", ["yolo"],              True),

        ("color",        "full",     "uniform",       ["hsv"],               True),
        ("color",        "specific", "direct_seek",   ["hsv"],               False),

        ("object_color", "full",     "uniform",       ["yolo", "hsv"],       True),
        ("object_color", "specific", "direct_seek",   ["yolo", "hsv"],       False),
        ("object_color", "search",   "binary_search", ["yolo", "hsv"],       True),

        ("ocr",          "full",     "uniform",       ["ocr"],               True),
        ("ocr",          "specific", "direct_seek",   ["ocr"],               False),

        ("counting",     "full",     "uniform",       ["yolo", "counter"],   False),
        ("counting",     "specific", "direct_seek",   ["yolo", "counter"],   False),

        ("event",        "full",     "uniform",       ["motion", "yolo"],    True),
        ("event",        "search",   "binary_search", ["motion", "yolo"],    True),

        ("scene",        "full",     "uniform",       ["yolo", "hsv"],       False),
    ]

    print(f"\n{'='*120}")
    print(f"{'INTENT':<16} {'SCOPE':<12} {'STRATEGY':<16} {'MODULES':<22} {'RATE':<8} {'STOP':<8} {'THRESH':<8} {'PASS'}")
    print(f"{'='*120}")

    passed = 0
    failed = 0

    for intent, scope, exp_strategy, exp_modules, exp_stop in test_cases:
        config = select(intent, scope)

        strategy_ok = config["strategy"] == exp_strategy
        modules_ok = config["modules"] == exp_modules
        stop_ok = config["early_stop"] == exp_stop
        ok = strategy_ok and modules_ok and stop_ok

        if ok:
            passed += 1
        else:
            failed += 1

        print(
            f"{intent:<16} "
            f"{scope:<12} "
            f"{config['strategy']:<16} "
            f"{str(config['modules']):<22} "
            f"{config['sample_rate']:<8} "
            f"{str(config['early_stop']):<8} "
            f"{config['confidence_threshold']:<8} "
            f"{'PASS' if ok else 'FAIL <<<'}"
        )

    print(f"{'='*120}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")

    # Show full config for one query
    print("\n--- Full Config Example ---")
    print("Query: 'Is there a red car?' → intent: object_color, scope: full\n")
    config = select("object_color", "full")
    for key, value in config.items():
        print(f"  {key}: {value}")

    # Show how same intent gets different strategies
    print("\n--- 2D Matrix Proof ---")
    print("Same intent (object), different scopes:\n")
    for scope in ["full", "specific", "search"]:
        config = select("object", scope)
        print(f"  scope: {scope:<10} → strategy: {config['strategy']:<16} early_stop: {config['early_stop']}")