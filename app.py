from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import yt_dlp
import os
import uuid
import threading
import time
import re

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# HTML template (single-page app)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Downloader</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0f0f0f; color: #fff; min-height: 100vh; display: flex; justify-content: center; align-items: center; }
        .container { max-width: 800px; width: 100%; padding: 2rem; }
        h1 { text-align: center; margin-bottom: 2rem; font-size: 2.5rem; background: linear-gradient(135deg, #ff0000, #cc0000); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .input-group { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
        input[type="text"] { flex: 1; padding: 1rem; border: 2px solid #333; border-radius: 8px; background: #1a1a1a; color: #fff; font-size: 1rem; outline: none; transition: border-color 0.3s; }
        input[type="text"]:focus { border-color: #ff0000; }
        button { padding: 1rem 2rem; background: #ff0000; color: #fff; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background 0.3s; }
        button:hover { background: #cc0000; }
        button:disabled { background: #555; cursor: not-allowed; }
        .formats-table { display: none; margin-top: 2rem; }
        .formats-table.active { display: block; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #333; }
        th { background: #1a1a1a; color: #aaa; font-weight: 600; }
        tr:hover { background: #1a1a1a; }
        .download-btn { background: #2ea043; padding: 0.4rem 1rem; font-size: 0.85rem; }
        .download-btn:hover { background: #238636; }
        .status { text-align: center; padding: 1rem; margin-top: 1rem; border-radius: 8px; display: none; }
        .status.loading { display: block; background: #1a1a1a; border: 1px solid #333; }
        .status.error { display: block; background: #2d1b1b; border: 1px solid #ff4444; color: #ff6666; }
        .progress-bar { width: 100%; height: 4px; background: #333; border-radius: 2px; margin-top: 1rem; overflow: hidden; display: none; }
        .progress-bar.active { display: block; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #ff0000, #ff6666); width: 0%; transition: width 0.3s; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
        .badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-left: 0.5rem; }
        .badge.vp9 { background: #1a6d1a; }
        .badge.av1 { background: #6d1a6d; }
        .badge.h264 { background: #1a3a6d; }
        .badge.opus { background: #6d5a1a; }
        .badge.aac { background: #1a6d5a; }
        .video-info { margin-top: 2rem; display: none; }
        .video-info.active { display: flex; gap: 1.5rem; align-items: flex-start; }
        .video-info img { max-width: 200px; border-radius: 8px; }
        .video-info h2 { font-size: 1.2rem; margin-bottom: 0.5rem; }
        .video-info p { color: #aaa; font-size: 0.9rem; }
        .error-msg { color: #ff6666; }
        select { padding: 0.5rem; background: #1a1a1a; color: #fff; border: 1px solid #333; border-radius: 4px; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>▶ YouTube Downloader</h1>
        <div class="input-group">
            <input type="text" id="url-input" placeholder="Paste YouTube URL here..." />
            <button id="fetch-btn" onclick="fetchFormats()">Fetch Formats</button>
        </div>
        <div id="status" class="status"></div>
        <div class="progress-bar" id="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
        </div>
        <div id="video-info" class="video-info"></div>
        <div id="formats-table" class="formats-table"></div>
    </div>

    <script>
        async function fetchFormats() {
            const url = document.getElementById('url-input').value.trim();
            if (!url) return showError('Please paste a YouTube URL');

            const btn = document.getElementById('fetch-btn');
            btn.disabled = true;
            btn.textContent = 'Loading...';
            showStatus('Fetching available formats...', 'loading');
            document.getElementById('progress-bar').classList.add('active');

            try {
                const resp = await fetch('/api/formats', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                const data = await resp.json();
                if (data.error) return showError(data.error);
                displayFormats(data);
            } catch (e) {
                showError('Failed to connect to server');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Fetch Formats';
                document.getElementById('progress-bar').classList.remove('active');
            }
        }

        function displayFormats(data) {
            const infoDiv = document.getElementById('video-info');
            infoDiv.innerHTML = `
                <img src="${data.thumbnail}" alt="thumbnail" />
                <div>
                    <h2>${data.title}</h2>
                    <p>${data.duration} | ${data.uploader}</p>
                </div>
            `;
            infoDiv.classList.add('active');

            const tableDiv = document.getElementById('formats-table');
            let html = '<table><thead><tr><th>Format</th><th>Resolution</th><th>Codec</th><th>FPS</th><th>Size (est.)</th><th>Action</th></tr></thead><tbody>';

            for (const f of data.formats) {
                if (f.vcodec === 'none') continue; // audio-only, handle separately
                const badgeClass = f.vcodec.includes('vp9') ? 'vp9' : f.vcodec.includes('av1') ? 'av1' : 'h264';
                html += `<tr>
                    <td>${f.format_id}</td>
                    <td>${f.resolution || 'N/A'}</td>
                    <td>${f.vcodec} <span class="badge ${badgeClass}">${f.vcodec.split('.')[0]}</span></td>
                    <td>${f.fps || 'N/A'}</td>
                    <td>${f.filesize_approx || 'N/A'}</td>
                    <td><button class="download-btn" onclick="downloadVideo('${data.url}', '${f.format_id}')">Download</button></td>
                </tr>`;
            }
            html += '</tbody></table>';
            tableDiv.innerHTML = html;
            tableDiv.classList.add('active');
            hideStatus();
        }

        async function downloadVideo(url, formatId) {
            showStatus('Downloading...', 'loading');
            document.getElementById('progress-bar').classList.add('active');

            try {
                const resp = await fetch('/api/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, format_id: formatId })
                });
                if (!resp.ok) {
                    const err = await resp.json();
                    return showError(err.error || 'Download failed');
                }
                const blob = await resp.blob();
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                const cd = resp.headers.get('Content-Disposition');
                const match = cd && cd.match(/filename="(.+)"/);
                a.download = match ? match[1] : 'video.mp4';
                a.click();
                URL.revokeObjectURL(a.href);
                hideStatus();
                document.getElementById('progress-bar').classList.remove('active');
            } catch (e) {
                showError('Download failed: ' + e.message);
                document.getElementById('progress-bar').classList.remove('active');
            }
        }

        function showStatus(msg, type) {
            const div = document.getElementById('status');
            div.textContent = msg;
            div.className = `status ${type}`;
        }

        function showError(msg) {
            const div = document.getElementById('status');
            div.textContent = '❌ ' + msg;
            div.className = 'status error';
            document.getElementById('progress-bar').classList.remove('active');
            document.getElementById('fetch-btn').disabled = false;
            document.getElementById('fetch-btn').textContent = 'Fetch Formats';
        }

        function hideStatus() {
            document.getElementById('status').className = 'status';
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/formats', methods=['POST'])
def get_formats():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    # Validate YouTube URL
    yt_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/'
    if not re.match(yt_regex, url):
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            formats = []
            for f in info.get('formats', []):
                # Skip formats without video
                if f.get('vcodec') == 'none':
                    continue

                filesize = f.get('filesize') or f.get('filesize_approx')
                filesize_str = format_bytes(filesize) if filesize else 'N/A'

                formats.append({
                    'format_id': f.get('format_id'),
                    'resolution': f.get('resolution') or f"{f.get('height', '?')}p",
                    'vcodec': f.get('vcodec', 'unknown'),
                    'acodec': f.get('acodec', 'unknown'),
                    'fps': f.get('fps'),
                    'filesize_approx': filesize_str,
                    'ext': f.get('ext'),
                })

            # Also include best audio-only + video merge options
            return jsonify({
                'title': info.get('title'),
                'duration': format_duration(info.get('duration')),
                'uploader': info.get('uploader'),
                'thumbnail': info.get('thumbnail'),
                'url': url,
                'formats': formats,
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id', '').strip()

    if not url or not format_id:
        return jsonify({'error': 'URL and format_id are required'}), 400

    output_template = os.path.join(DOWNLOAD_DIR, f'%(title)s_%(id)s.%(ext)s')

    ydl_opts = {
        'format': f'{format_id}+bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            # Handle post-processed extensions
            base, _ = os.path.splitext(filename)
            mp4_file = base + '.mp4'
            if os.path.exists(mp4_file):
                filename = mp4_file

            if not os.path.exists(filename):
                # Try to find the file
                import glob
                files = glob.glob(os.path.join(DOWNLOAD_DIR, f"*{info.get('id', '')}*"))
                if files:
                    filename = files[0]

            return send_file(
                filename,
                as_attachment=True,
                download_name=f"{info.get('title', 'video')}.mp4",
                mimetype='video/mp4'
            )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def format_duration(seconds):
    if not seconds:
        return 'N/A'
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
