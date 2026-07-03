const express = require('express');
const path = require('path');
const { Innertube, UniversalCache } = require('youtubei.js');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Allow requests from your GitHub Pages frontend (and anywhere, for simplicity)
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

// ---- Cached Innertube client (don't recreate per request) ----
let ytClient = null;
async function getYT() {
  if (!ytClient) {
    ytClient = await Innertube.create({
      lang: 'en',
      location: 'IN',
      cache: new UniversalCache(false), // in-memory cache, safe for Render's ephemeral fs
      generate_session_locally: true,   // avoids depending on YT server-side session gen
    });
  }
  return ytClient;
}

function extractVideoId(input) {
  if (!input) return null;
  const idPattern = /^[a-zA-Z0-9_-]{11}$/;
  if (idPattern.test(input)) return input;
  try {
    const url = new URL(input);
    if (url.hostname.includes('youtu.be')) return url.pathname.slice(1);
    if (url.searchParams.get('v')) return url.searchParams.get('v');
  } catch (_) {}
  return null;
}

// ---- Get available formats/info for a video ----
app.post('/api/formats', async (req, res) => {
  try {
    const videoId = extractVideoId(req.body.videoId || req.body.url);
    if (!videoId) return res.status(400).json({ error: 'Valid videoId or URL required' });

    const client = await getYT();
    const info = await client.getInfo(videoId);

    const allFormats = [
      ...(info.streaming_data?.formats || []),
      ...(info.streaming_data?.adaptive_formats || []),
    ];

    const formats = allFormats
      .filter(f => f.mime_type)
      .map(f => ({
        itag: f.itag,
        quality: f.quality_label || f.quality || 'unknown',
        mimeType: f.mime_type,
        hasAudio: f.has_audio,
        hasVideo: f.has_video,
        bitrate: f.bitrate,
        contentLength: f.content_length,
      }));

    res.json({
      videoId,
      title: info.basic_info.title,
      author: info.basic_info.author,
      duration: info.basic_info.duration,
      thumbnail: info.basic_info.thumbnail?.[0]?.url || null,
      formats,
    });
  } catch (err) {
    console.error('Innertube /api/formats error:', err.message);
    res.status(500).json({ error: 'Failed to fetch formats', detail: err.message });
  }
});

// ---- Stream/proxy a specific itag directly to the client ----
app.get('/api/stream', async (req, res) => {
  try {
    const videoId = extractVideoId(req.query.videoId);
    const itag = parseInt(req.query.itag, 10);
    if (!videoId || !itag) return res.status(400).json({ error: 'videoId and itag required' });

    const client = await getYT();
    const info = await client.getInfo(videoId);

    const allFormats = [
      ...(info.streaming_data?.formats || []),
      ...(info.streaming_data?.adaptive_formats || []),
    ];
    const format = allFormats.find(f => f.itag === itag);
    if (!format) return res.status(404).json({ error: 'Format not found for this itag' });

    const streamUrl = format.decipher(client.session.player);

    // Support range requests (seeking) by forwarding the Range header upstream
    const upstreamHeaders = {};
    if (req.headers.range) upstreamHeaders.range = req.headers.range;

    const upstream = await fetch(streamUrl, { headers: upstreamHeaders });

    res.status(upstream.status);
    res.setHeader('Content-Type', format.mime_type || 'video/mp4');
    if (upstream.headers.get('content-length')) {
      res.setHeader('Content-Length', upstream.headers.get('content-length'));
    }
    if (upstream.headers.get('content-range')) {
      res.setHeader('Content-Range', upstream.headers.get('content-range'));
      res.setHeader('Accept-Ranges', 'bytes');
    }

    const reader = upstream.body.getReader();
    req.on('close', () => reader.cancel().catch(() => {}));
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      res.write(Buffer.from(value));
    }
    res.end();
  } catch (err) {
    console.error('Innertube /api/stream error:', err.message);
    if (!res.headersSent) res.status(500).json({ error: 'Streaming failed', detail: err.message });
  }
});

app.get('/health', (req, res) => res.json({ status: 'ok' }));

app.listen(PORT, () => {
  console.log(`Server live on port ${PORT}`);
});
