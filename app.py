from flask import redirect, url_for, flash, Flask, render_template, request
import os, threading
import yt_dlp
from instagrapi import Client
import time
import random
from dotenv import load_dotenv
import json
from datetime import timedelta, datetime

load_dotenv("secure/credentials.env")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
OLLAMA_MODEL = "llama3.2:latest"
TO_UPLOAD_DIR = "instaposter/to_upload"
CAPTIONS_JSON = "instaposter/captions.json"
PROMPT_FILE = "secure/prompt.txt"
os.makedirs(TO_UPLOAD_DIR, exist_ok=True)
app = Flask(__name__)
app.secret_key = SECRET_KEY


def generate_caption(creator):
    import json
    with open(CAPTIONS_JSON, "r") as f:
        captions = json.load(f)
    random_caption = random.choice(captions)
    return f"{random_caption['sentence']}\ncr:{creator}\n{random_caption['hashtags']}"


def download_instagram_video(url):
    ydl_opts = {
        'outtmpl': f'{TO_UPLOAD_DIR}/video.%(ext)s',
        'format': 'best',
        'cookiefile': 'secure/cookies.txt'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        video_path = ydl.prepare_filename(info_dict)

    channel_name = info_dict['channel']

    existing_files = [f for f in os.listdir(TO_UPLOAD_DIR) if f.startswith(channel_name)]
    count = len(existing_files)

    if count > 0:
        new_video_name = f"{channel_name} - {count + 1}.mp4"
    else:
        new_video_name = f"{channel_name}.mp4"
        
    new_video_path = os.path.join(TO_UPLOAD_DIR, new_video_name)

    os.rename(video_path, new_video_path)

    print(f"✅ Downloaded: {new_video_name}")
    return new_video_path, channel_name


def post_to_instagram(video_path, caption):
    cl = Client()
    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    cl.clip_upload(video_path, caption)
    return True


website_log = []
def auto_post_later():
    scheduled_hours = [0, 3, 6, 9, 12, 15, 18, 21]
    time.sleep(5)

    while True:
        videos = [f for f in os.listdir(TO_UPLOAD_DIR) if f.endswith(".mp4")]
        now = datetime.now()

        if not videos:
            log_entry = f"{now.strftime('%Y-%m-%d %H:%M:%S')} ⏳ No videos to post, checking again in 30 mins"
            print(log_entry)
            website_log.append(log_entry)
            time.sleep(1800)
            continue

        next_post_time = None
        for h in scheduled_hours:
            scheduled_time = now.replace(hour=h, minute=0, second=0, microsecond=0)
            if scheduled_time > now:
                next_post_time = scheduled_time
                break
        if not next_post_time:
            next_post_time = (now + timedelta(days=1)).replace(hour=scheduled_hours[0], minute=0, second=0, microsecond=0)

        remaining = (next_post_time - now).total_seconds()
        log_entry = f"{now.strftime('%Y-%m-%d %H:%M:%S')} ⏳ Pending videos: {len(videos)} | Next post at {next_post_time.strftime('%H:%M')} ({int(remaining // 60)} mins)"
        print(log_entry)
        website_log.append(log_entry)

        while remaining > 0:
            sleep_interval = min(remaining, 60)
            time.sleep(sleep_interval)
            remaining -= sleep_interval
            now = datetime.now()
            log_entry = f"{now.strftime('%Y-%m-%d %H:%M:%S')} ⏳ Pending videos: {len(videos)} | Next post at {next_post_time.strftime('%H:%M')} ({int(remaining // 60)} mins)"
            print(log_entry)
            website_log.append(log_entry)

        video_file = random.choice(videos)
        video_path = os.path.join(TO_UPLOAD_DIR, video_file)
        creator_name = video_file.split(" - ")[0]
        caption = generate_caption(creator_name)
        

        try:
            post_to_instagram(video_path, caption)
            os.remove(video_path)
            thumb_path = video_path + ".jpg"
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ✅ Posted and deleted {video_file}"
            print(log_entry)
            website_log.append(log_entry)
        except Exception as e:
            log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ❌ Failed to post {video_file}: {e}"
            print(log_entry)
            website_log.append(log_entry)             


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        if not url:
            flash("❌ No URL provided")
        else:
            try:
                flash("⬇️ Downloading video...")
                video_path, creator = download_instagram_video(url)
                flash(f"✅ Video downloaded: {video_path}")
            except Exception as e:
                flash(f"❌ Error: {e}")
        return redirect(url_for("index"))


    display_log = website_log[-100:]
    return render_template("index.html", logs=display_log)


def auto_unfollow():
    cl = Client()
    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)

    scheduled_hours = [0, 3, 6, 9, 12, 15, 18, 21]

    try:
        following = cl.user_following(cl.user_id)

        while True:
            if not following:
                log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 🎉 No more people left to unfollow."
                print(log_entry)
                website_log.append(log_entry)
                break

            now = datetime.now()
            next_time = None
            for h in scheduled_hours:
                scheduled_time = now.replace(hour=h, minute=0, second=0, microsecond=0)
                if scheduled_time > now:
                    next_time = scheduled_time
                    break

            if not next_time:
                next_time = (now + timedelta(days=1)).replace(
                    hour=scheduled_hours[0], minute=0, second=0, microsecond=0
                )

            remaining = (next_time - now).total_seconds()
            log_entry = (f"{now.strftime('%Y-%m-%d %H:%M:%S')} ⏳ Waiting until "
                         f"{next_time.strftime('%H:%M')} to unfollow batch | Remaining: {int(remaining//60)} mins")
            print(log_entry)
            website_log.append(log_entry)

            while remaining > 0:
                time.sleep(min(remaining, 300))
                now = datetime.now()
                remaining = (next_time - now).total_seconds()

            batch = random.sample(list(following.keys()), min(10, len(following)))
            for user_id in batch:
                try:
                    cl.user_unfollow(user_id)
                    following.pop(user_id, None)
                    log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ✅ Unfollowed {user_id} | Remaining: {len(following)}"
                    print(log_entry)
                    website_log.append(log_entry)
                except Exception as e:
                    log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ❌ Failed unfollow {user_id}: {e}"
                    print(log_entry)
                    website_log.append(log_entry)

    except Exception as e:
        log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ❌ Error in auto_unfollow: {e}"
        print(log_entry)
        website_log.append(log_entry)


if __name__ == "__main__":
    threading.Thread(target=auto_post_later, daemon=True).start()
    threading.Thread(target=auto_unfollow, daemon=True).start()

    app.run(host="192.168.100.24", port=5555, debug=False)


