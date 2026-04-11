"""
Frame Sampler Module

Selects only relevant frames from a video based on strategy config.
This is where the 96% frame reduction happens.

Receives from strategy_selector:
  - strategy: uniform / direct_seek / binary_search
  - sample_rate: frames per second to sample
  - timestamp: specific time in seconds (for direct_seek)

Sampling Methods:
  - uniform:       every Nth frame across full video
  - scene_change:  frames where visual content changes significantly
  - direct_seek:   jump to exact timestamp ± window
  - binary_search: halve search space to find first/last occurrence

Returns: list of {frame, frame_number, timestamp}
"""

import cv2
import numpy as np


# ============================================================
# VIDEO READER HELPER
# ============================================================

def open_video(video_path: str) -> tuple:
    """
    Open video and extract metadata.

    Returns:
        (cap, metadata) where metadata is dict with fps, total_frames, duration
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise Exception(f"Cannot open video: {video_path}")

    metadata = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    metadata["duration"] = metadata["total_frames"] / metadata["fps"] if metadata["fps"] > 0 else 0

    return cap, metadata


def read_frame_at(cap, frame_number: int) -> tuple:
    """
    Read a specific frame by frame number.

    Returns:
        (success, frame) — frame is numpy array or None
    """
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    return ret, frame


# ============================================================
# SAMPLING METHOD 1: UNIFORM
# Pick every Nth frame across the full video
# Used for: object, color, object_color, ocr, counting
# ============================================================

def sample_uniform(video_path: str, sample_rate: float) -> list:
    """
    Uniform sampling — pick 1 frame every (1/sample_rate) seconds.

    Args:
        video_path: path to video file
        sample_rate: frames per second to sample (e.g., 1 = one per second)

    Returns:
        list of {frame, frame_number, timestamp}
    """
    cap, meta = open_video(video_path)
    fps = meta["fps"]
    total = meta["total_frames"]

    # Calculate interval: how many frames to skip between samples
    if sample_rate <= 0:
        sample_rate = 1
    interval = max(1, int(fps / sample_rate))

    selected = []
    frame_number = 0

    while frame_number < total:
        ret, frame = read_frame_at(cap, frame_number)
        if not ret:
            break

        timestamp = frame_number / fps

        selected.append({
            "frame": frame,
            "frame_number": frame_number,
            "timestamp": timestamp,
        })

        frame_number += interval

    cap.release()
    return selected


# ============================================================
# SAMPLING METHOD 2: SCENE CHANGE DETECTION
# Detect frames where visual content changes significantly
# Used as supplement for event detection
# ============================================================

def sample_scene_change(video_path: str, sample_rate: float, threshold: float = 30.0) -> list:
    """
    Scene change detection — sample frames where visual difference
    between consecutive frames exceeds threshold.

    Also includes uniform baseline samples to avoid missing static events.

    Args:
        video_path: path to video file
        sample_rate: baseline uniform rate (frames per second)
        threshold: pixel difference threshold to detect scene change

    Returns:
        list of {frame, frame_number, timestamp}
    """
    cap, meta = open_video(video_path)
    fps = meta["fps"]
    total = meta["total_frames"]

    # Baseline uniform interval
    interval = max(1, int(fps / sample_rate))

    selected = []
    seen_frames = set()  # avoid duplicates
    prev_gray = None

    frame_number = 0

    while frame_number < total:
        ret, frame = read_frame_at(cap, frame_number)
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        timestamp = frame_number / fps

        should_add = False

        # Scene change check
        if prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray)
            mean_diff = np.mean(diff)

            if mean_diff > threshold:
                should_add = True

        # Baseline uniform check
        if frame_number % interval == 0:
            should_add = True

        # First frame always included
        if frame_number == 0:
            should_add = True

        if should_add and frame_number not in seen_frames:
            selected.append({
                "frame": frame,
                "frame_number": frame_number,
                "timestamp": timestamp,
            })
            seen_frames.add(frame_number)

        prev_gray = gray
        frame_number += 1

    cap.release()
    return selected


# ============================================================
# SAMPLING METHOD 3: DIRECT SEEK
# Jump to exact timestamp ± small window for context
# Used for: temporal queries ("what happens at 2:30?")
# ============================================================

def sample_direct_seek(video_path: str, timestamp: float, window: int = 5) -> list:
    """
    Direct seek — jump to specific timestamp and grab a window of frames.

    Args:
        video_path: path to video file
        timestamp: target time in seconds
        window: number of frames to grab on each side of target

    Returns:
        list of {frame, frame_number, timestamp}
    """
    cap, meta = open_video(video_path)
    fps = meta["fps"]
    total = meta["total_frames"]

    # Calculate target frame
    target_frame = int(timestamp * fps)

    # Clamp to valid range
    start = max(0, target_frame - window)
    end = min(total - 1, target_frame + window)

    selected = []

    for frame_number in range(start, end + 1):
        ret, frame = read_frame_at(cap, frame_number)
        if not ret:
            break

        ts = frame_number / fps

        selected.append({
            "frame": frame,
            "frame_number": frame_number,
            "timestamp": ts,
        })

    cap.release()
    return selected


# ============================================================
# SAMPLING METHOD 4: BINARY SEARCH
# Halve the search space to find first occurrence efficiently
# Used for: "when does X first appear?" queries
#
# NOTE: Binary search needs a detection function callback
# because it must CHECK each frame to decide which half to search.
# The callback is provided by analyzer.py
# ============================================================

def sample_binary_search(video_path: str, detect_fn, max_iterations: int = 20) -> list:
    """
    Binary search — find first occurrence of target by halving search space.

    Reduces O(N) to O(log N) frames processed.

    Args:
        video_path: path to video file
        detect_fn: callback function(frame) → bool (True if target found)
        max_iterations: maximum search iterations to prevent infinite loop

    Returns:
        list of {frame, frame_number, timestamp, detected}
    """
    cap, meta = open_video(video_path)
    fps = meta["fps"]
    total = meta["total_frames"]

    low = 0
    high = total - 1
    result_frame = None
    checked = []
    iterations = 0

    while low <= high and iterations < max_iterations:
        mid = (low + high) // 2
        iterations += 1

        ret, frame = read_frame_at(cap, mid)
        if not ret:
            high = mid - 1
            continue

        timestamp = mid / fps
        detected = detect_fn(frame)

        checked.append({
            "frame": frame,
            "frame_number": mid,
            "timestamp": timestamp,
            "detected": detected,
        })

        if detected:
            # Found — search left half for earlier occurrence
            result_frame = mid
            high = mid - 1
        else:
            # Not found — search right half
            low = mid + 1

    cap.release()

    # If found, also grab a few frames around the earliest detection
    # for better context
    if result_frame is not None:
        cap2 = cv2.VideoCapture(video_path)
        context_start = max(0, result_frame - 3)
        context_end = min(total - 1, result_frame + 3)

        already_checked = {f["frame_number"] for f in checked}

        for fn in range(context_start, context_end + 1):
            if fn not in already_checked:
                ret, frame = read_frame_at(cap2, fn)
                if ret:
                    checked.append({
                        "frame": frame,
                        "frame_number": fn,
                        "timestamp": fn / fps,
                        "detected": detect_fn(frame),
                    })

        cap2.release()

    # Sort by frame number
    checked.sort(key=lambda x: x["frame_number"])
    return checked


# ============================================================
# MAIN SAMPLE FUNCTION — ENTRY POINT
# ============================================================

def sample(video_path: str, strategy_config: dict, detect_fn=None) -> list:
    """
    Main entry point. Routes to correct sampling method based on strategy config.

    Args:
        video_path: path to video file (local, already downloaded)
        strategy_config: from strategy_selector.select()
            - strategy: "uniform" / "direct_seek" / "binary_search"
            - sample_rate: frames per second
            - temporal_scope: "full" / "specific" / "search"
            - intent: for reference
        detect_fn: callback for binary search (provided by analyzer.py)
            function(frame) → bool

    Returns:
        list of {frame, frame_number, timestamp}
    """
    strategy = strategy_config["strategy"]
    sample_rate = strategy_config.get("sample_rate", 1)
    intent = strategy_config.get("intent", "")
    timestamp = strategy_config.get("timestamp", None)

    if strategy == "direct_seek":
        if timestamp is None:
            raise ValueError("direct_seek strategy requires a timestamp")
        return sample_direct_seek(video_path, timestamp)

    elif strategy == "binary_search":
        if detect_fn is None:
            raise ValueError("binary_search strategy requires a detect_fn callback")
        return sample_binary_search(video_path, detect_fn)

    elif strategy == "uniform":
        # Event detection benefits from scene change detection
        if intent == "event":
            return sample_scene_change(video_path, sample_rate)
        else:
            return sample_uniform(video_path, sample_rate)

    else:
        # Unknown strategy — fallback to uniform
        return sample_uniform(video_path, sample_rate)


# ============================================================
# STATS HELPER
# ============================================================

def get_sampling_stats(video_path: str, selected_frames: list) -> dict:
    """
    Calculate sampling efficiency stats for results.

    Returns:
        dict with total_frames, frames_selected, reduction_percent
    """
    _, meta = open_video(video_path)
    total = meta["total_frames"]
    selected = len(selected_frames)
    reduction = ((total - selected) / total * 100) if total > 0 else 0

    return {
        "total_frames": total,
        "frames_selected": selected,
        "reduction_percent": round(reduction, 1),
        "fps": meta["fps"],
        "duration": round(meta["duration"], 1),
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    import sys

    # Usage: python frame_sampler.py <video_path>
    if len(sys.argv) < 2:
        print("Usage: python frame_sampler.py <video_path>")
        print("\nRunning with dummy stats demo...\n")

        # Demo without actual video
        print("--- Sampling Efficiency Table ---\n")
        print(f"{'Video Duration':<18} {'FPS':<6} {'Total Frames':<15} {'Uniform 1/s':<14} {'Binary Search':<15} {'Reduction'}")
        print(f"{'='*85}")

        demos = [
            (60,  30),   # 1 minute
            (300, 30),   # 5 minutes
            (1800, 30),  # 30 minutes
            (3600, 30),  # 1 hour
        ]

        for duration, fps in demos:
            total = duration * fps
            uniform = duration  # 1 frame per second
            binary = min(20, int(np.log2(total)) + 1)  # log2 frames

            import math
            reduction_uniform = round((total - uniform) / total * 100, 1)
            reduction_binary = round((total - binary) / total * 100, 1)

            dur_str = f"{duration // 60} min" if duration < 3600 else f"{duration // 3600} hour"

            print(
                f"{dur_str:<18} "
                f"{fps:<6} "
                f"{total:<15} "
                f"{uniform:<14} "
                f"{binary:<15} "
                f"{reduction_uniform}% / {reduction_binary}%"
            )

        print(f"\n--- Strategy Routing ---\n")
        print(f"{'Strategy':<18} {'Method Called':<25} {'Use Case'}")
        print(f"{'='*70}")
        print(f"{'uniform':<18} {'sample_uniform()':<25} {'object, color, ocr, counting, scene'}")
        print(f"{'uniform + event':<18} {'sample_scene_change()':<25} {'event detection'}")
        print(f"{'direct_seek':<18} {'sample_direct_seek()':<25} {'temporal queries (at 2:30)'}")
        print(f"{'binary_search':<18} {'sample_binary_search()':<25} {'presence queries (first appear)'}")

        sys.exit(0)

    video_path = sys.argv[1]

    # Test uniform sampling
    print(f"\n--- Testing Uniform Sampling (1 fps) ---")
    frames = sample_uniform(video_path, sample_rate=1)
    stats = get_sampling_stats(video_path, frames)
    print(f"Total frames: {stats['total_frames']}")
    print(f"Selected: {stats['frames_selected']}")
    print(f"Reduction: {stats['reduction_percent']}%")
    print(f"Duration: {stats['duration']}s")

    # Test scene change sampling
    print(f"\n--- Testing Scene Change Sampling (3 fps baseline) ---")
    frames_sc = sample_scene_change(video_path, sample_rate=3, threshold=30.0)
    stats_sc = get_sampling_stats(video_path, frames_sc)
    print(f"Total frames: {stats_sc['total_frames']}")
    print(f"Selected: {stats_sc['frames_selected']}")
    print(f"Reduction: {stats_sc['reduction_percent']}%")

    # Test direct seek
    print(f"\n--- Testing Direct Seek (at 5.0s) ---")
    frames_ds = sample_direct_seek(video_path, timestamp=5.0, window=5)
    print(f"Frames grabbed: {len(frames_ds)}")
    for f in frames_ds:
        print(f"  Frame #{f['frame_number']} at {f['timestamp']:.2f}s")

    # Test via main sample() function
    print(f"\n--- Testing Main Router ---")
    config = {
        "strategy": "uniform",
        "sample_rate": 1,
        "intent": "object",
        "temporal_scope": "full",
    }
    routed = sample(video_path, config)
    print(f"Strategy: uniform → got {len(routed)} frames")

    config_event = {
        "strategy": "uniform",
        "sample_rate": 3,
        "intent": "event",
        "temporal_scope": "full",
    }
    routed_event = sample(video_path, config_event)
    print(f"Strategy: uniform + event → got {len(routed_event)} frames (scene change)")

    config_seek = {
        "strategy": "direct_seek",
        "sample_rate": 0,
        "intent": "object",
        "temporal_scope": "specific",
        "timestamp": 5.0,
    }
    routed_seek = sample(video_path, config_seek)
    print(f"Strategy: direct_seek → got {len(routed_seek)} frames")