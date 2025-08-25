from flask import Flask, render_template, request
import os
import yt_dlp
from instagrapi import Client
import subprocess
import threading
import time
import random
from dotenv import load_dotenv
import json
from datetime import datetime
from datetime import timedelta
load_dotenv("secure/credentials.env")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
OLLAMA_MODEL = "llama3.2:latest"

# ---------------- CONFIG ----------------
TO_UPLOAD_DIR = "instaposter/to_upload"
UPLOADED_DIR = "instaposter/uploaded"
POSTS_JSON = "instaposter/posts.json"
PROMPT_FILE = "secure/prompt.txt"

# os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(TO_UPLOAD_DIR, exist_ok=True)
os.makedirs(UPLOADED_DIR, exist_ok=True)

# ---------------------------------------

app = Flask(__name__)
app.secret_key = SECRET_KEY
# --------- HELPERS ---------

def load_posts():
    with open(POSTS_JSON, "r") as f:
        return json.load(f)


def save_posts(posts):
    with open(POSTS_JSON, "w") as f:
        json.dump(posts, f, indent=4)


def generate_caption(creator: str) -> str:
    # prompt = (
    #     "Write a short Instagram caption (5 words max) with cute or seductive vibes. "
    #     "Include a few relevant hashtags at the end. "
    #     "Do not write anything else, just the caption with hashtags."
    # )
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt = f.read().strip()

    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL, prompt],
            capture_output=True,
            text=True,
            check=True
        )
        caption = result.stdout.strip()
    except Exception as e:
        print("❌ Ollama generate failed:", e)
        caption = "♥︎"

    hashtag_index = caption.find("#")
    if hashtag_index == -1:
        main_text = caption
        hashtags = ""
    else:
        main_text = caption[:hashtag_index].strip()
        hashtags = caption[hashtag_index:].strip()

    final_caption = f"{main_text}\ncr:{creator}"
    if hashtags:
        final_caption += f"\n{hashtags}"
    
    return final_caption


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
    
    new_video_name = f"{channel_name} - {count + 1}.mp4"
    new_video_path = os.path.join(TO_UPLOAD_DIR, new_video_name)

    os.rename(video_path, new_video_path)

    caption = generate_caption(channel_name)
    
    posts = load_posts()
    posts.append({
        "video_name": new_video_name,
        "video_path": new_video_path,
        "caption": caption,
        "url": url,
        "posted": False
    })
    save_posts(posts)

    print(f"✅ Downloaded: {new_video_name}")
    return new_video_path, channel_name

def post_to_instagram(video_path, caption):
    cl = Client()
    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    cl.clip_upload(video_path, caption)
    return True

# --------- AUTO POST THREAD ---------
def auto_post_later():
    time.sleep(5)  # Wait for Flask to start
    while True:
        try:
            posts = load_posts()
            pending_posts = [p for p in posts if not p["posted"]]

            if pending_posts:
                # Print status about pending posts
                next_post_time = datetime.now() + timedelta(seconds=1)  # Optional placeholder
                print(f"⏳ There are {len(pending_posts)} pending videos to post.")
                print(f"Next one will be posted soon.")

                # Pick a random pending post
                post = random.choice(pending_posts)
                video_path = post["video_path"]
                caption = post["caption"]

                print(f"🤖 Auto-posting {post['video_name']}...")
                post_to_instagram(video_path, caption)

                # Move the video file
                new_video_path = os.path.join(UPLOADED_DIR, os.path.basename(video_path))
                os.rename(video_path, new_video_path)
                post["video_path"] = new_video_path

                # Move the Instagram-generated thumbnail if exists
                thumbnail_path = video_path + ".jpg"
                if os.path.exists(thumbnail_path):
                    new_thumb_path = os.path.join(UPLOADED_DIR, os.path.basename(thumbnail_path))
                    os.rename(thumbnail_path, new_thumb_path)
                    print(f"📷 Moved thumbnail {os.path.basename(thumbnail_path)}")

                # Update JSON entry
                post["posted"] = True
                post["date"] = datetime.now().isoformat(timespec='seconds')
                save_posts(posts)

                print(f"✅ Auto-posted {post['video_name']} at {post['date']}")

            else:
                print("⏳ No pending videos to post.")

        except Exception as e:
            print(f"❌ Error in auto_post_later: {e}")

        time.sleep(10800)  # Wait 3 hours

# --------- FLASK ROUTE ---------
# @app.route("/", methods=["GET", "POST"])
# def index():
#     log = ""
#     if request.method == "POST":
#         url = request.form.get("url")
#         action = request.form.get("action")
#         if not url:
#             log = "❌ No URL provided"
#         else:
#             try:
#                 log += "⬇️ Downloading video...\n"
#                 video_path, creator = download_instagram_video(url)
#                 log += f"✅ Video downloaded: {video_path}\n"
#                 log += f"🎨 Creator ID: {creator}\n"

#                 if action == "Submit Later":
#                     filename = os.path.basename(video_path)
#                     new_path = os.path.join(TO_UPLOAD_DIR, f"{creator} - {filename}")
#                     os.rename(video_path, new_path)
#                     log += f"⏳ Video saved for later upload: {new_path}\n"

#                 elif action == "Upload Now":
#                     log += "🤖 Generating caption...\n"
#                     caption = generate_caption(creator)
#                     log += f"💬 Caption: {caption}\n"
#                     log += "📤 Posting to Instagram...\n"
#                     post_to_instagram(video_path, caption, creator)
#                     log += "✅ Posted successfully!\n"

#             except Exception as e:
#                 log += f"❌ Error: {e}\n"

#     return render_template("index.html", log=log)
from flask import redirect, url_for, flash, get_flashed_messages

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        action = request.form.get("action")
        if not url:
            flash("❌ No URL provided")
        else:
            try:
                flash("⬇️ Downloading video...")
                video_path, creator = download_instagram_video(url)
                flash(f"✅ Video downloaded: {video_path}")
                flash(f"🎨 Creator ID: {creator}")

                if action == "Submit Later":
                    flash(f"⏳ Video saved for later upload: {video_path}")

                elif action == "Upload Now":
                    flash("🤖 Generating caption...")
                    caption = generate_caption(creator)
                    flash(f"💬 Caption: {caption}")
                    flash("📤 Posting to Instagram...")
                    post_to_instagram(video_path, caption)
                    flash("✅ Posted successfully!")

            except Exception as e:
                flash(f"❌ Error: {e}")

        # Redirect after POST to avoid resubmission
        return redirect(url_for("index"))

    # GET request: show form and library
    posts = load_posts()
    to_post = [p for p in posts if not p.get("posted")]
    posted = [p for p in posts if p.get("posted")]

    messages = get_flashed_messages()

    return render_template(
        "index.html",
        log_messages=messages,
        to_post=to_post,
        posted=posted
    )
if __name__ == "__main__":
    threading.Thread(target=auto_post_later, daemon=True).start()
    app.run(host="192.168.100.24", port=5555, debug=False)
    
