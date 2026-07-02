# YouTube Downloader

A web-based YouTube video downloader that supports all qualities from 144p up to 8K.

## Features

- Paste any YouTube URL and fetch all available formats
- Download in any resolution (144p, 360p, 720p, 1080p, 4K, 8K)
- Multiple codecs supported (H.264, VP9, AV1)
- Automatic video+audio merging via FFmpeg
- Clean, modern dark-themed UI

## Hosting

### Backend (required)

The Python backend runs on Render (free tier):

1. Fork this repo
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command**: `chmod +x render-build.sh && ./render-build.sh`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
5. Deploy

### Frontend

The frontend is served by the Flask backend itself — no separate hosting needed.

## Tech Stack

- **Backend**: Python, Flask, yt-dlp, FFmpeg
- **Frontend**: Vanilla HTML/CSS/JS
- **Hosting**: Render (backend)
