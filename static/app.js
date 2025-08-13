const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const overlay = document.getElementById('overlay');
const draw = document.createElement('canvas');
draw.id = 'draw';
draw.style.position = 'absolute';
draw.style.left = '0';
draw.style.top = '0';
draw.style.pointerEvents = 'none';
draw.style.width = '100%';
draw.style.height = '100%';
draw.style.zIndex = '10';
const recognizeToggle = document.getElementById('recognizeToggle');
const currentName = document.getElementById('currentName');
const currentScore = document.getElementById('currentScore');
const message = document.getElementById('message');
const lastFace = document.getElementById('lastFace');
const thumbWrap = document.getElementById('thumbWrap');
const lastFaceTime = document.getElementById('lastFaceTime');

let stream = null;
let recognizing = false;
let recogTimer = null;

function ensureGetUserMedia() {
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    return true;
  }
  const legacyGetUserMedia =
    navigator.getUserMedia ||
    navigator.webkitGetUserMedia ||
    navigator.mozGetUserMedia ||
    navigator.msGetUserMedia;
  if (!legacyGetUserMedia) {
    return false;
  }
  if (!navigator.mediaDevices) {
    navigator.mediaDevices = {};
  }
  navigator.mediaDevices.getUserMedia = (constraints) =>
    new Promise((resolve, reject) => legacyGetUserMedia.call(navigator, constraints, resolve, reject));
  return true;
}

async function startCamera() {
  try {
    const isSecure = window.isSecureContext || location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname);
    if (!isSecure) {
      throw new Error('Camera requires HTTPS or localhost');
    }
    if (!ensureGetUserMedia()) {
      throw new Error('Camera API not supported in this browser');
    }
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }}, audio: false });
    video.srcObject = stream;
    await video.play();
    // Match drawing canvas to video size
    draw.width = video.videoWidth;
    draw.height = video.videoHeight;
    // Insert draw canvas on top of video
    const vc = document.querySelector('.video-container');
    if (vc && !document.getElementById('draw')) {
      vc.appendChild(draw);
    }
  } catch (err) {
    showMessage(`Camera error: ${err.message}`, true);
  }
}

function captureFrameBlob(mimeType = 'image/jpeg', quality = 0.9) {
  const width = video.videoWidth;
  const height = video.videoHeight;
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, width, height);
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), mimeType, quality);
  });
}

function showMessage(text, isError = false) {
  message.textContent = text;
  message.className = `message ${isError ? 'error' : ''}`;
  if (text) setTimeout(() => { message.textContent = ''; message.className = 'message'; }, 5000);
}

recognizeToggle.addEventListener('click', async () => {
  recognizing = !recognizing;
  recognizeToggle.textContent = recognizing ? 'Stop Recognizing' : 'Start Recognizing';
  if (recognizing) {
    loopRecognize();
  } else if (recogTimer) {
    clearTimeout(recogTimer);
    recogTimer = null;
    const dctx = draw.getContext('2d');
    dctx.clearRect(0, 0, draw.width, draw.height);
  }
});

async function loopRecognize() {
  if (!recognizing) return;
  try {
    const blob = await captureFrameBlob();
    const form = new FormData();
    form.append('threshold', '0.35');
    form.append('image', blob, 'frame.jpg');
    const res = await fetch('/api/recognize', { method: 'POST', body: form });
    const data = await res.json();
    const dctx = draw.getContext('2d');
    dctx.clearRect(0, 0, draw.width, draw.height);
    if (Array.isArray(data.results) && data.results.length > 0) {
      // Ensure backing canvas matches current video size
      if (draw.width !== video.videoWidth || draw.height !== video.videoHeight) {
        draw.width = video.videoWidth;
        draw.height = video.videoHeight;
      }
      const [srcW, srcH] = Array.isArray(data.image_size) && data.image_size.length === 2
        ? data.image_size : [video.videoWidth, video.videoHeight];
      const scaleX = draw.width / srcW;
      const scaleY = draw.height / srcH;
      // Display the first match info
      const first = data.results.find(r => r.recognized) || data.results[0];
      const scoreText = first.score != null ? `(score: ${first.score.toFixed(3)})` : '';
      currentName.textContent = first.personnel_id ? `${first.name} [${first.personnel_id}]` : first.name;
      currentScore.textContent = scoreText;
      if (first.face_image_url) {
        if (thumbWrap) thumbWrap.classList.remove('hidden');
        if (lastFace) lastFace.src = first.face_image_url + `?t=${Date.now()}`;
        if (lastFaceTime && first.recognized_at) {
          const t = new Date(first.recognized_at);
          lastFaceTime.textContent = `at ${t.toLocaleString()}`;
        }
      }
      // Draw all boxes
      const lw = Math.max(2, Math.round(Math.min(draw.width, draw.height) / 300));
      dctx.lineWidth = lw;
      const colorForId = (key) => {
        // Deterministic HSL color from identity key
        let hash = 0;
        for (let i = 0; i < key.length; i++) {
          hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
        }
        const hue = hash % 360;
        return `hsl(${hue}, 80%, 55%)`;
      };
      data.results.forEach(r => {
        if (!Array.isArray(r.bbox) || r.bbox.length !== 4) return;
        const identityKey = `${r.name}|${r.personnel_id || ''}`;
        const [bx1, by1, bx2, by2] = r.bbox;
        const x1 = Math.max(0, Math.floor(bx1 * scaleX));
        const y1 = Math.max(0, Math.floor(by1 * scaleY));
        const x2 = Math.max(0, Math.floor(bx2 * scaleX));
        const y2 = Math.max(0, Math.floor(by2 * scaleY));
        const w = Math.max(0, x2 - x1);
        const h = Math.max(0, y2 - y1);
        const stroke = r.recognized ? colorForId(identityKey) : 'hsl(0, 0%, 75%)';
        dctx.strokeStyle = stroke;
        dctx.strokeRect(x1, y1, w, h);
        const pidFrag = r.personnel_id ? ` [${r.personnel_id}]` : '';
        const label = `${r.name}${pidFrag}`;
        dctx.font = `${Math.max(14, Math.round(h * 0.08))}px Segoe UI, Roboto, Arial`;
        dctx.textBaseline = 'top';
        const metrics = dctx.measureText(label);
        const textW = metrics.width + 10;
        const textH = Math.max(18, Math.round(parseInt(dctx.font, 10) + 6));
        let ty = y1 - textH - 4;
        if (ty < 0) ty = y1 + lw;
        const tx = Math.max(0, Math.min(draw.width - textW - 2, x1));
        dctx.fillStyle = 'rgba(0,0,0,0.65)';
        dctx.fillRect(tx, ty, textW, textH);
        dctx.fillStyle = '#e2e8f0';
        dctx.fillText(label, tx + 5, ty + 3);
      });
    } else {
      currentName.textContent = '-';
      currentScore.textContent = '';
      if (thumbWrap) thumbWrap.classList.add('hidden');
      if (lastFace) lastFace.removeAttribute('src');
      if (lastFaceTime) lastFaceTime.textContent = '';
      const dctx2 = draw.getContext('2d');
      dctx2.clearRect(0, 0, draw.width, draw.height);
    }
  } catch (e) {
    // ignore transient errors
  } finally {
    recogTimer = setTimeout(loopRecognize, 1000);
  }
}

startCamera();
