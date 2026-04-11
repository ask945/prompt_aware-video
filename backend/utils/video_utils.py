import requests
import os
import cv2

def download_from_cloudinary(video_url, save_dir="temp"):
    os.makedirs(save_dir, exist_ok=True)
    local_path = os.path.join(save_dir, "temp_video.mp4")
    response = requests.get(video_url, stream=True)
    if response.status_code != 200:
        raise Exception("Failed to download video")
    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return local_path

def get_video_metadata(video_path):
    cap = cv2.VideoCapture(video_path)
    metadata = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "duration": cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
    }
    cap.release()
    return metadata

def save_frame(frame, frame_number):
    path = f"frames/frame_{frame_number}.jpg"
    os.makedirs("frames", exist_ok=True)
    cv2.imwrite(path, frame)
    return path

def cleanup_temp(path):
    if os.path.exists(path):
        os.remove(path)