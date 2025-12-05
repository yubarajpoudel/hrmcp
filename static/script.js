const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const fileInput = document.getElementById('file-input');
const fileNameDisplay = document.getElementById('file-name-display');

// Auth Check
const token = localStorage.getItem('access_token');
if (!token) {
    window.location.href = '/login.html';
}

let currentFile = null;

function addMessage(content, role) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', role);

    const contentDiv = document.createElement('div');
    contentDiv.classList.add('content');
    contentDiv.textContent = content;

    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

async function handleSend() {
    const message = messageInput.value.trim();
    if (!message && !currentFile) return;

    messageInput.disabled = true;
    sendBtn.disabled = true;

    if (message) {
        addMessage(message, 'user');
    }
    if (currentFile) {
        addMessage(`[Uploaded File: ${currentFile.name}]`, 'user');
    }

    messageInput.value = '';

    // Create a new message div for the assistant response immediately (Thinking state)
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', 'assistant');
    const contentDiv = document.createElement('div');
    contentDiv.classList.add('content', 'thinking');
    contentDiv.textContent = 'Thinking...';
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
        let response;
        const headers = {
            'Authorization': `Bearer ${token}`
        };

        if (currentFile) {
            const formData = new FormData();
            formData.append('file', currentFile);
            formData.append('role', 'user'); // Default role

            const uploadRes = await fetch('/upload', {
                method: 'POST',
                headers: headers,
                body: formData
            });

            if (uploadRes.status === 401) {
                localStorage.removeItem('access_token');
                window.location.href = '/login.html';
                return;
            }

            if (!uploadRes.ok) {
                throw new Error('File upload failed');
            }

            const uploadData = await uploadRes.json();
            const fileMsg = `I have uploaded a file named ${currentFile.name}.`;
            const fullMessage = message ? `${fileMsg}\n\n${message}` : fileMsg;

            const chatFormData = new FormData();
            chatFormData.append('message', fullMessage);

            response = await fetch('/chat', {
                method: 'POST',
                headers: headers,
                body: chatFormData
            });

            currentFile = null;
            fileInput.value = '';
            fileNameDisplay.textContent = '';

        } else {
            const formData = new FormData();
            formData.append('message', message);

            response = await fetch('/chat', {
                method: 'POST',
                headers: headers,
                body: formData
            });
        }

        if (response.status === 401) {
            localStorage.removeItem('access_token');
            window.location.href = '/login.html';
            return;
        }

        if (!response.ok) {
            throw new Error('Chat request failed');
        }

        // Clear thinking state
        contentDiv.textContent = '';
        contentDiv.classList.remove('thinking');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            contentDiv.textContent += chunk;
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

    } catch (error) {
        console.error('Error:', error);
        contentDiv.classList.remove('thinking');
        contentDiv.textContent = 'Sorry, something went wrong. Please try again.';
    } finally {
        messageInput.disabled = false;
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

sendBtn.addEventListener('click', handleSend);

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSend();
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        currentFile = e.target.files[0];
        fileNameDisplay.textContent = `Selected: ${currentFile.name}`;
    } else {
        currentFile = null;
        fileNameDisplay.textContent = '';
    }
});
