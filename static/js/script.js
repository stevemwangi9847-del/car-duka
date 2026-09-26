function toggleMenu() {
  document.querySelector('.nav-links').classList.toggle('open');
}

function toggleChat() {
  document.getElementById('chatWindow').classList.toggle('open');
}

function handleChatKey(e) {
  if (e.key === 'Enter') sendChat();
}

function appendMsg(text, sender) {
  const body = document.getElementById('chatBody');
  const div = document.createElement('div');
  div.className = 'msg ' + sender;
  div.textContent = text;
  body.appendChild(div);
  body.scrollTop = body.scrollHeight;
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;

  appendMsg(text, 'user');
  input.value = '';

  // Typing indicator
  const body = document.getElementById('chatBody');
  const typing = document.createElement('div');
  typing.className = 'msg bot';
  typing.textContent = 'Typing...';
  typing.id = 'typingIndicator';
  body.appendChild(typing);
  body.scrollTop = body.scrollHeight;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    document.getElementById('typingIndicator')?.remove();
    appendMsg(data.reply, 'bot');
  } catch (err) {
    document.getElementById('typingIndicator')?.remove();
    appendMsg('Sorry, I encountered an error. Please try again.', 'bot');
  }
}

function previewImage(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const preview = document.getElementById('imgPreview');
    preview.src = e.target.result;
    preview.style.display = 'block';
    document.getElementById('fileMsg').innerHTML =
      '<i class="fas fa-check-circle" style="color:#2a9d8f"></i> ' + file.name;
  };
  reader.readAsDataURL(file);
}

// Set min date for booking inputs to today
document.addEventListener('DOMContentLoaded', () => {
  const dateInputs = document.querySelectorAll('input[type="date"]');
  const today = new Date().toISOString().split('T')[0];
  dateInputs.forEach(i => i.min = today);
});