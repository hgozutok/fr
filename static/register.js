const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const message = document.getElementById('message');
const nameInput = document.getElementById('nameInput');
const personnelIdInput = document.getElementById('personnelIdInput');
const registerBtn = document.getElementById('registerBtn');

let stream = null;

function ensureGetUserMedia() {
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) return true;
  const legacy = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia || navigator.msGetUserMedia;
  if (!legacy) return false;
  if (!navigator.mediaDevices) navigator.mediaDevices = {};
  navigator.mediaDevices.getUserMedia = (constraints) => new Promise((resolve, reject) => legacy.call(navigator, constraints, resolve, reject));
  return true;
}

async function startCamera() {
  try {
    const isSecure = window.isSecureContext || location.protocol === 'https:' || ['localhost','127.0.0.1'].includes(location.hostname);
    if (!isSecure) throw new Error('Camera requires HTTPS or localhost');
    if (!ensureGetUserMedia()) throw new Error('Camera API not supported');
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }}, audio: false });
    video.srcObject = stream;
    await video.play();
  } catch (e) {
    showMessage(`Camera error: ${e.message}`, true);
  }
}

function showMessage(text, isError = false) {
  message.textContent = text;
  message.className = `message ${isError ? 'error' : ''}`;
  if (text) setTimeout(() => { message.textContent=''; message.className='message'; }, 5000);
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

registerBtn.addEventListener('click', async () => {
  const name = nameInput.value.trim();
  const personnelId = personnelIdInput.value.trim();
  if (!name) {
    showMessage('Please enter full name', true);
    return;
  }
  try {
    const blob = await captureFrameBlob();
    const form = new FormData();
    form.append('name', name);
    if (personnelId) form.append('personnel_id', personnelId);
    form.append('image', blob, 'frame.jpg');
    const res = await fetch('/api/register', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Registration failed');
    }
    nameInput.value = '';
    personnelIdInput.value = '';
    showMessage('Registered successfully');
  } catch (e) {
    showMessage(e.message, true);
  }
});

startCamera();


