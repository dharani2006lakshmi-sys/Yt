from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import yt_dlp
from yt_dlp.utils import DownloadError
import os
import re
import glob

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'DNT': '1',
    'Connection': 'keep-alive',
}

def build_opts(for_download=False):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'http_headers': HEADERS,
        'extractor_args': {
            'youtube': {
                'player_client': ['web_embedded', 'tv'],
                'player_skip': ['webpage', 'configs'],
            }
        },
        'extract_flat': False,
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
    }
    if for_download:
        opts.update({
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s_%(id)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        })
    return opts

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/formats', methods=['POST'])
def get_formats():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    if not re.match(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/', url):
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    try:
        with yt_dlp.YoutubeDL(build_opts()) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []
        for f in info.get('formats', []):
            if f.get('vcodec') == 'none':
                continue
            filesize = f.get('filesize') or f.get('filesize_approx')
            formats.append({
                'format_id': f.get('format_id'),
                'resolution': f.get('resolution') or f"{f.get('height', '?')}p",
                'vcodec': f.get('vcodec', 'unknown'),
                'acodec': f.get('acodec', 'unknown'),
                'fps': f.get('fps'),
                'filesize_approx': format_bytes(filesize) if filesize else 'N/A',
                'ext': f.get('ext'),
            })

        return jsonify({
            'title': info.get('title'),
            'duration': format_duration(info.get('duration')),
            'uploader': info.get('uploader'),
            'thumbnail': info.get('thumbnail'),
            'url': url,
            'formats': formats,
        })

    except DownloadError as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            return jsonify({'error': 'YouTube is blocking this server IP. Try again later or use a different hosting region.'}), 500
        return jsonify({'error': error_msg}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id', '').strip()

    if not url or not format_id:
        return jsonify({'error': 'URL and format_id are required'}), 400

    opts = build_opts(for_download=True)
    opts['format'] = f'{format_id}+bestaudio[ext=m4a]/bestaudio/best'

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            base, _ = os.path.splitext(filename)
            mp4_file = base + '.mp4'
            if os.path.exists(mp4_file):
                filename = mp4_file

            if not os.path.exists(filename):
                files = glob.glob(os.path.join(DOWNLOAD_DIR, f"*{info.get('id', '')}*"))
                if files:
                    filename = files[0]

            if not os.path.exists(filename):
                return jsonify({'error': 'Downloaded file not found'}), 500

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
        if size < 1023:
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
