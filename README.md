# Vidzly Backend (MVP)

Real, working long-video → short-video pipeline:

`upload → extract audio → Whisper transcription → GPT picks best moments
→ ffmpeg cuts each moment → crops to 9:16 → burns captions → done`

This was tested end-to-end in a sandbox (minus the OpenAI calls, which
need your API key) — the ffmpeg cut/crop/caption steps were run against
a real video file and verified frame-by-frame before this was handed
to you.

## What's real vs. what the frontend prototype had

The Vidzly frontend you already have is a UI prototype — the processing
screen there is a **fake, timed animation**. This backend is the real
thing: actual transcription, actual AI moment-selection, actual ffmpeg
video editing. Wiring the two together is the "Connecting to the
frontend" section at the bottom.

## 1. Requirements

- Python 3.10+
- `ffmpeg` installed and on your PATH (`ffmpeg -version` should work)
- An OpenAI API key with access to Whisper + a chat model
  (get one at https://platform.openai.com/api-keys — this is a paid
  API, transcription + moment-detection will cost roughly a few cents
  per video depending on length)

## 2. Local setup

```bash
cd vidzly-backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# open .env and paste your real OPENAI_API_KEY

uvicorn app.main:app --reload --port 8000
```

Server is now running at `http://localhost:8000`.
Check it's alive: `curl http://localhost:8000/api/health` → `{"status":"ok"}`

## 3. Test it manually with a real video

```bash
curl -X POST http://localhost:8000/api/projects \
  -F "file=@/path/to/your/video.mp4"
# -> {"job_id": "a1b2c3d4e5f6"}

curl http://localhost:8000/api/projects/a1b2c3d4e5f6
# -> poll this every couple seconds; watch "step" and "progress" change:
#    uploading -> transcribing -> finding_moments -> analyzing
#    -> captioning -> done
# once step == "done", the response includes a "clips" array

curl -O http://localhost:8000/api/download/a1b2c3d4e5f6_1
# downloads the first finished vertical clip as an .mp4
```

Processing time is roughly the length of the source video divided by
2-4, plus the time GPT takes to read the transcript — a 10-minute
video usually finishes in 1-3 minutes on a normal server.

## 4. Deploying so it's live on the internet

Pick one — all three work with the included `Dockerfile`:

### Railway (easiest)
1. Push this folder to a GitHub repo
2. https://railway.app → New Project → Deploy from GitHub repo
3. Add environment variable `OPENAI_API_KEY` in Railway's dashboard
4. Railway auto-detects the Dockerfile and deploys — you'll get a
   public URL like `vidzly-backend-production.up.railway.app`

### Render
1. Push this folder to a GitHub repo
2. https://render.com → New → Web Service → connect the repo
3. Render will detect the Dockerfile automatically
4. Add `OPENAI_API_KEY` under Environment
5. Deploy — you get a public URL

### Any VPS (DigitalOcean, Hetzner, etc.)
```bash
# on the server, with Docker installed:
git clone <your-repo-url>
cd vidzly-backend
echo "OPENAI_API_KEY=sk-..." > .env
docker build -t vidzly-backend .
docker run -d -p 8000:8000 --env-file .env vidzly-backend
```
Put a reverse proxy (Caddy or nginx) in front for HTTPS.

**Important:** video processing is CPU-heavy. A free-tier instance
(512MB-1GB RAM) will work for short/low-traffic testing but will be
slow or crash under real load. For real users, a $10-20/month server
with 2+ vCPUs handles this comfortably for moderate traffic.

## 5. Connecting the frontend to this backend

In the `vidzly.html` prototype, `startProcessing()` currently just
calls `goto('processing')` and fakes progress with a `setInterval`.
Replace that with a real call, e.g.:

```javascript
async function startProcessing() {
  goto('processing');
  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch('https://your-backend-url.com/api/projects', {
    method: 'POST', body: formData
  });
  const { job_id } = await res.json();

  const poll = setInterval(async () => {
    const r = await fetch(`https://your-backend-url.com/api/projects/${job_id}`);
    const status = await r.json();
    // update procPct, procRing, proc-step classes, procLiveText from `status`
    if (status.step === 'done') {
      clearInterval(poll);
      renderRealClips(status.clips); // build clip cards from status.clips instead of the CLIPS mock array
      goto('shorts');
    }
    if (status.step === 'error') {
      clearInterval(poll);
      toast('info', status.error);
    }
  }, 2000);
}
```

You'll also want to set `CORS_ORIGINS` in `.env` to your actual
frontend domain (not `*`) once this is live.

## 6. Known MVP limitations (and how to grow past them)

- **Crop is center-crop, not subject-tracking.** Real "keep the face
  in frame" cropping needs a face/pose-detection pass (e.g. MediaPipe)
  that outputs a per-frame crop window instead of the fixed center
  crop in `video.py`. Worth building next since it's the single
  biggest visual-quality jump.
- **Single background worker.** `run_pipeline` runs as a FastAPI
  background task — fine for low traffic, but concurrent uploads
  will queue behind each other on a single server. Move to Celery/RQ
  + Redis once you have real concurrent users.
- **Local disk storage.** Fine for one server; swap `config.py`'s
  `UPLOAD_DIR`/`OUTPUT_DIR` for S3-backed storage before scaling to
  multiple servers.
- **No auth/rate limiting yet.** Add an API key or user-auth check
  in `main.py` before this is public, or anyone with the URL can
  burn through your OpenAI budget.
- **Motion graphics (zoom/punch-in) aren't implemented.** Captions
  and smart-crop are real; the fancier motion-graphics options shown
  in the frontend editor are still UI-only. Same pattern as captions
  — an ffmpeg filter graph added to `video.py` — but scoped out of
  this MVP to keep it shippable.
