const facesList = document.getElementById('facesList');
const refreshListBtn = document.getElementById('refreshList');
const clearAllBtn = document.getElementById('clearAll');
const message = document.getElementById('message');
const editPanel = document.getElementById('editPanel');
const editName = document.getElementById('editName');
const editPid = document.getElementById('editPid');
const saveEdit = document.getElementById('saveEdit');
const cancelEdit = document.getElementById('cancelEdit');

let selected = null; // { name, personnel_id }

function showMessage(text, isError = false) {
  message.textContent = text;
  message.className = `message ${isError ? 'error' : ''}`;
  if (text) setTimeout(() => { message.textContent=''; message.className='message'; }, 4000);
}

async function refreshFacesList() {
  try {
    const res = await fetch('/api/faces');
    const data = await res.json();
    facesList.innerHTML = '';
    (data.faces || []).forEach((rec) => {
      const li = document.createElement('li');
      const row = document.createElement('div');
      row.className = 'row';
      const left = document.createElement('div');
      const pid = rec.personnel_id ? ` • ID: ${rec.personnel_id}` : '';
      left.innerHTML = `<div><strong>${rec.name}</strong><span class="meta">${pid}</span></div><div class="meta">samples: ${rec.samples}</div>`;
      const right = document.createElement('div');
      right.className = 'actions-inline';
      const editBtn = document.createElement('button');
      editBtn.textContent = 'Edit';
      editBtn.addEventListener('click', () => beginEdit(rec));
      const delBtn = document.createElement('button');
      delBtn.textContent = 'Delete';
      delBtn.className = 'danger';
      delBtn.addEventListener('click', () => deleteIdentity(rec));
      right.appendChild(editBtn);
      right.appendChild(delBtn);
      row.appendChild(left);
      row.appendChild(right);
      li.appendChild(row);
      facesList.appendChild(li);
    });
  } catch (e) {
    showMessage('Failed to load faces', true);
  }
}

refreshListBtn.addEventListener('click', refreshFacesList);

clearAllBtn.addEventListener('click', async () => {
  try {
    await fetch('/api/clear', { method: 'POST' });
    await refreshFacesList();
    showMessage('Cleared all registered faces');
  } catch (e) {
    showMessage('Failed to clear', true);
  }
});

refreshFacesList();

function beginEdit(rec) {
  selected = { name: rec.name, personnel_id: rec.personnel_id || null };
  editName.value = rec.name || '';
  editPid.value = rec.personnel_id || '';
  editPanel.classList.remove('hidden');
}

cancelEdit.addEventListener('click', () => {
  selected = null;
  editPanel.classList.add('hidden');
});

saveEdit.addEventListener('click', async () => {
  if (!selected) return;
  const newName = editName.value.trim();
  const newPid = editPid.value.trim();
  if (!newName) { showMessage('New name required', true); return; }
  try {
    const form = new FormData();
    form.append('old_name', selected.name);
    if (selected.personnel_id) form.append('old_personnel_id', selected.personnel_id);
    form.append('new_name', newName);
    if (newPid) form.append('new_personnel_id', newPid);
    const res = await fetch('/api/identity/rename', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Rename failed');
    }
    showMessage('Updated');
    selected = null;
    editPanel.classList.add('hidden');
    await refreshFacesList();
  } catch (e) {
    showMessage(e.message, true);
  }
});

async function deleteIdentity(rec) {
  try {
    const form = new FormData();
    form.append('name', rec.name);
    if (rec.personnel_id) form.append('personnel_id', rec.personnel_id);
    const res = await fetch('/api/identity/delete', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Delete failed');
    }
    showMessage('Deleted');
    await refreshFacesList();
  } catch (e) {
    showMessage(e.message, true);
  }
}


