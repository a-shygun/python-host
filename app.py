from flask import redirect, url_for, Flask, render_template, request
import os, threading
import yt_dlp
from instagrapi import Client
import time
import random
from dotenv import load_dotenv
import json
from datetime import timedelta, datetime
import json
import socket
import csv


load_dotenv("secure/credentials.env")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
TO_UPLOAD_DIR = "instaposter/to_upload"
CAPTIONS_JSON = "instaposter/captions.json"
PROMPT_FILE = "secure/prompt.txt"
LOG_FILE = "instaposter/logs.csv"
scheduled_hours = [0, 3, 6, 9, 12, 15, 18, 21]
website_log = []
os.makedirs(TO_UPLOAD_DIR, exist_ok=True)
app = Flask(__name__)
app.secret_key = SECRET_KEY


def log_message(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, message])
    print(f"{timestamp} - {message}")


def download_instagram_video(url):
    ydl_opts = {
        'outtmpl': f'{TO_UPLOAD_DIR}/video.%(ext)s',
        'format': 'best',
        'cookiefile': 'secure/cookies.txt'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info_dict)

        channel_name = info_dict['channel']

        existing_files = [f for f in os.listdir(TO_UPLOAD_DIR) if f.startswith(channel_name)]
        count = len(existing_files)

        new_video_name = f"{channel_name} - {count + 1}.mp4"

        new_video_path = os.path.join(TO_UPLOAD_DIR, new_video_name)
        os.rename(video_path, new_video_path)

        log_message(f"⬇️ Downloaded video: {new_video_name} from {channel_name}")
        return new_video_path, channel_name
    except Exception as e:
        log_message(f"❌ Failed to download video from {url}: {e}")
        raise e
   



def upload_to_instagram(video_path, caption):
    try:
        cl = Client()
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.clip_upload(video_path, caption)
        return True
    except Exception as e:
        log_message(f"❌ Instagram upload failed: {e}")
        return False


def setup_post():
    videos = [f for f in os.listdir(TO_UPLOAD_DIR) if f.endswith(".mp4")]

    if not videos:
        log_message("⏳ No videos to post.")
        return False

    video_file = get_random_video()
    video_path = os.path.join(TO_UPLOAD_DIR, video_file)
    creator_name = video_path.split(" - ")[0]
    
    caption = get_caption(creator_name)

    log_message(f"🤖 Uploading now: {video_file}")
    
    if upload_to_instagram(video_path, caption):
        log_message(f"✅ Successfully posted {video_file} to Instagram")

        os.remove(video_path)
        thumb_path = video_path + ".jpg"
        if os.path.exists(thumb_path):
            os.remove(thumb_path)

        log_message(f"✅ Posted and deleted {video_file}")
        return True

    return False

def auto_post_scheduler():
    time.sleep(5)
    while True:
        videos = [f for f in os.listdir(TO_UPLOAD_DIR) if f.endswith(".mp4")]
        if not videos:
            log_message("⏳ No videos to post, checking again in 30 mins")
            time.sleep(1800)
            continue
        next_time = get_next_scheduled_time(scheduled_hours)

        remaining = (next_time - datetime.now()).total_seconds()
        log_message(f"⏳ Pending videos: {len(videos)} | Next post at {next_time.strftime('%H:%M')} ({int(remaining // 60)} mins)")

        # Countdown until next post
        while remaining > 0:
            sleep_interval = min(remaining, 60)  # Update every 1 min
            time.sleep(sleep_interval)
            remaining -= sleep_interval
            # Optional: Refresh video count periodically
            videos = [f for f in os.listdir(TO_UPLOAD_DIR) if f.endswith(".mp4")]
            log_message(f"⏳ Pending videos: {len(videos)} | Next post at {next_time.strftime('%H:%M')} ({int(remaining // 60)} mins)")

        # Try posting
        try:
            setup_post()
        except Exception as e:
            log_message(f"❌ Error during posting: {e}")

def get_next_scheduled_time(scheduled_hours):
    now = datetime.now()
    for h in scheduled_hours:
        scheduled_time = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if scheduled_time > now:
            return scheduled_time

    return (now + timedelta(days=1)).replace(
        hour=scheduled_hours[0], minute=0, second=0, microsecond=0
    )

def get_random_video():
    videos = [f for f in os.listdir(TO_UPLOAD_DIR) if f.endswith(".mp4")]
    if not videos:
        return None
    return random.choice(videos)

def get_caption(creator):
    with open(CAPTIONS_JSON, "r") as f:
        captions = json.load(f)
    random_caption = random.choice(captions)
    final_caption = f"{random_caption['sentence']}\ncr:{creator}\n{random_caption['hashtags']}"
    log_message(f"📝 Generated caption for {creator}: {final_caption}")
    return final_caption


def auto_unfollow():
    cl = Client()
    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)

    try:
        following = cl.user_following(cl.user_id)

        while True:
            if not following:
                log_message("🎉 No more people left to unfollow.")
                break

            next_time = get_next_scheduled_time(scheduled_hours)
            remaining = (next_time - datetime.now()).total_seconds()
            log_message(f"⏳ Unfollowing at: {next_time.strftime('%H:%M')} | Remaining: {int(remaining // 60)} mins")

            # Countdown until unfollow session
            while remaining > 0:
                time.sleep(min(remaining, 300))  # Update every 5 min
                remaining = (next_time - datetime.now()).total_seconds()

            # Unfollow session starts
            log_message(f"🚀 Starting unfollow session at {next_time.strftime('%H:%M')}")

            # One unfollow per minute until next scheduled time
            while True:
                if not following:
                    log_message("🎉 Finished all unfollows.")
                    return

                now = datetime.now()
                # If we've reached or passed the next scheduled hour, break
                if now >= next_time + timedelta(minutes=60):  # Limit unfollow session to 1 hour
                    log_message("✅ Completed this unfollow session.")
                    break

                # Pick a random user to unfollow
                user_id = random.choice(list(following.keys()))
                try:
                    cl.user_unfollow(user_id)
                    following.pop(user_id, None)
                    log_message(f"✅ Unfollowed {user_id} | Remaining: {len(following)}")
                except Exception as e:
                    log_message(f"❌ Failed unfollow {user_id}: {e}")

                # Wait 60 seconds before next unfollow
                time.sleep(60)

    except Exception as e:
        log_message(f"❌ Error in auto_unfollow: {e}")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        if url:
            try:
                log_message("⬇️ Downloading video...")
                new_video_path, channel_name = download_instagram_video(url)
                log_message(f"✅ Video downloaded from {channel_name}")
            except Exception as e:
                log_message(f"❌ Error downloading video: {e}")
        else:
            log_message("❌ No URL provided")
        return redirect(url_for("index"))

    logs = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            logs = [f"{row[0]} {row[1]}" for row in list(reader)[-100:]]
    except Exception as e:
        logs.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ❌ Failed to read log CSV: {e}")

    return render_template("index.html", logs=logs)

@app.route("/upload_now", methods=["POST"])
def manual_upload():
    success = setup_post()
    if success:
        log_message("✅ Random video uploaded successfully!")
    else:
        log_message("❌ No videos to upload or upload failed.")
    return redirect(url_for("index"))

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # connect to a typical LAN gateway
        s.connect(("192.168.1.1", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    ip = get_lan_ip()
    print(f"🌐 Access on LAN: http://{ip}:5555")
    log_message(f"🌐 Hosting Flask app on http://{ip}:5555")

    threading.Thread(target=auto_post_scheduler, daemon=True).start()
    threading.Thread(target=auto_unfollow, daemon=True).start()
    app.run(host="192.168.100.19", port=5555, debug=False)
