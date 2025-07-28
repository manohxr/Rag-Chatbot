const form = document.getElementById('chat-form');
const input = document.getElementById('user-input');
const chatWindow = document.getElementById('chat-window');
const pdfInput = document.getElementById('pdf-upload');

const uploadInput = document.getElementById('pdf-upload');
const paperclipIcon = document.getElementById('paperclip-icon');
const spinner = document.getElementById('upload-spinner');

const dropdownToggle = document.getElementById('dropdown-toggle');
const dropdownList = document.getElementById('dropdown-list');
let selectedNamespace = '';

dropdownToggle.addEventListener('click', () => {
    dropdownList.classList.toggle('hidden');
});

window.addEventListener('click', (e) => {
    if (!dropdownToggle.contains(e.target) && !dropdownList.contains(e.target)) {
        dropdownList.classList.add('hidden');
    }
});

uploadInput.addEventListener('change', async () => {
    const file = uploadInput.files[0];
    if (!file) return;

    // Show spinner, hide paperclip
    paperclipIcon.style.display = 'none';
    spinner.style.display = 'block';
    uploadInput.disabled = true;

    const formData = new FormData();
    formData.append('pdf', file);

    try {
        const response = await fetch('/upload_pdf', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (!response.ok) {
            addMessage('bot', data.message || 'Upload failed, please try again.');
            throw new Error(data.message || 'Upload failed.');
        }

        addMessage('bot', `Uploaded: ${file.name}`);
        addMessage('bot', data.message);
        await loadPDFs();
    } catch (err) {
        console.error('Upload error:', err);
        addMessage('bot', 'Error uploading file, please try again.');
    } finally {
        spinner.style.display = 'none';
        paperclipIcon.style.display = 'block';
        uploadInput.disabled = false;
        uploadInput.value = '';
    }
});


dropdownList.addEventListener('click', (e) => {
    const item = e.target.closest('.dropdown-item');
    if (!item) return;
    if (e.target.classList.contains('trash')) return;
    const val = item.dataset.value;
    selectedNamespace = val;
    dropdownToggle.textContent = val || 'Base LLM ⏷';
    dropdownList.classList.add('hidden');
});

async function loadPDFs() {
    const response = await fetch('/get_pdfs');
    const pdfs = await response.json();

    dropdownList.innerHTML = `<div class="dropdown-item" data-value="">Base LLM</div>`;

    pdfs.forEach(pdf => {
        const item = document.createElement('div');
        item.className = 'dropdown-item';
        item.dataset.value = pdf.pdf_name;
        item.innerHTML = `
          <span>${pdf.pdf_name}</span>
          <svg class="trash" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none"
     viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
  <path stroke-linecap="round" stroke-linejoin="round"
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22m-5 0V5a2 2 0 00-2-2H8a2 2 0 00-2 2v2" />
</svg>

        `;

        item.querySelector('.trash').addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!confirm(`Delete "${pdf.pdf_name}"? This cannot be undone.`)) return;

            const res = await fetch('/delete_pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pdf_name: pdf.pdf_name })
            });
            const result = await res.json();

            if (res.ok) {
                addMessage('bot', `${result.message}`);
                loadPDFs();
            } else {
                addMessage('bot', `${result.message}`);
            }
        });

        dropdownList.appendChild(item);
    });
}

form.addEventListener('submit', function (e) {
    e.preventDefault();
    const message = input.value.trim();
    if (message === '') return;

    addMessage('user', message);
    input.value = '';
    streamBotResponse(message);
});



function addMessage(sender, text, timeValue = null) {
    const messageWrapper = document.createElement('div');
    messageWrapper.classList.add('message', sender);

    const messageText = document.createElement('div');
    messageText.classList.add('message-text');
    messageText.textContent = text;

    const time = document.createElement('div');
    time.classList.add('message-time');

    if (timeValue) {
        const ts = new Date(timeValue);
        time.textContent = ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else {
        time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    messageWrapper.appendChild(messageText);
    messageWrapper.appendChild(time);

    chatWindow.appendChild(messageWrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function streamBotResponse(userMessage) {
    const namespace = selectedNamespace || null;

    const messageWrapper = document.createElement('div');
    messageWrapper.classList.add('message', 'bot');

    const messageText = document.createElement('div');
    messageText.classList.add('message-text');
    messageWrapper.appendChild(messageText);

    const time = document.createElement('div');
    time.classList.add('message-time');
    messageWrapper.appendChild(time);

    chatWindow.appendChild(messageWrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, namespace: namespace })
    })
        .then(response => {
            if (!response.body) throw new Error('ReadableStream not supported');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = '';

            function read() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        return;
                    }
                    const chunk = decoder.decode(value);
                    fullText += chunk;
                    messageText.textContent = fullText;
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                    read();
                });
            }
            read();
        })
        .catch(err => {
            console.error('Streaming error:', err);
            addMessage('bot', 'Error - could not get response');
        });
}

async function loadHistory() {
    const response = await fetch('/get_history');
    const history = await response.json();

    let lastDate = null;

    history.forEach(chat => {
        const ts = new Date(chat.timestamp);
        const dateStr = ts.toDateString();

        if (dateStr !== lastDate) {
            insertDateSeparator(dateStr);
            lastDate = dateStr;
        }

        addMessage('user', chat.user_message, chat.timestamp);
        addMessage('bot', chat.bot_response, chat.timestamp);
    });
}

function insertDateSeparator(dateStr) {
    const separator = document.createElement('div');
    separator.classList.add('date-separator');
    separator.textContent = dateStr;
    chatWindow.appendChild(separator);
}

window.onload = () => {
    loadHistory();
    loadPDFs();
};