const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const fileInput = document.getElementById('file-input');
const fileNameDisplay = document.getElementById('file-name-display');

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

    // Disable input while processing
    messageInput.disabled = true;
    sendBtn.disabled = true;

    // Display user message
    if (message) {
        addMessage(message, 'user');
    }
    if (currentFile) {
        addMessage(`[Uploaded File: ${currentFile.name}]`, 'user');
    }

    messageInput.value = '';

    try {
        let response;

        // If there's a file, upload it first or send with message?
        // The backend expects /upload for files and /chat for messages.
        // But the prompt implies we might want to do both or the chat needs to know about the file.
        // Let's upload the file first if it exists.

        if (currentFile) {
            const formData = new FormData();
            formData.append('file', currentFile);
            formData.append('role', 'user'); // Default role

            const uploadRes = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!uploadRes.ok) {
                throw new Error('File upload failed');
            }

            const uploadData = await uploadRes.json();
            // We might want to inform the chat about the uploaded file
            // The backend doesn't seem to automatically link them, so we'll append info to the message
            // or just rely on the user's message referencing it.
            // Let's append a note to the message sent to chat.

            // If message is empty but file was uploaded, we should probably say something
            const fileMsg = `I have uploaded a file named ${currentFile.name}.`;
            const fullMessage = message ? `${fileMsg}\n\n${message}` : fileMsg;

            const chatFormData = new FormData();
            chatFormData.append('message', fullMessage);

            response = await fetch('/chat', {
                method: 'POST',
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
                body: formData
            });
        }

        if (!response.ok) {
            throw new Error('Chat request failed');
        }

        const data = await response.json();
        addMessage(data.result, 'assistant');

    } catch (error) {
        console.error('Error:', error);
        addMessage('Sorry, something went wrong. Please try again.', 'system');
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
