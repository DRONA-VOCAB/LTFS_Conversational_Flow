// L&T Finance Feedback Survey - Web Interface
const API_BASE = '/api/v1';

let callId = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let isBotSpeaking = false; 

// VAD (Voice Activity Detection) variables
let audioContext = null;
let analyser = null;
let microphone = null;
let vadProcessor = null;
let vadAnimationFrame = null;
let vadConfig = {
    silenceThreshold: 0.01,      // Volume threshold (0-1)
    silenceDuration: 2000,       // Milliseconds of silence before auto-stop
    minRecordingDuration: 500,   // Minimum recording duration (ms)
    checkInterval: 100,          // Check interval (ms)
    smoothingTimeConstant: 0.8   // Smoothing for volume detection
};
let silenceStartTime = null;
let isSpeaking = false;
let isAutomaticMode = true; // Enable automatic 2-way conversation
let isWaitingForBotAudio = false; // Track if we're waiting for bot audio to finish

// DOM Elements
const initiateBtn = document.getElementById('initiate-btn');
const agreementNoInput = document.getElementById('agreement-no');
const initiateStatus = document.getElementById('initiate-status');
const conversationSection = document.getElementById('conversation-section');
const recordBtn = document.getElementById('record-btn');
const stopBtn = document.getElementById('stop-btn');
const playBtn = document.getElementById('play-btn');
const sendBtn = document.getElementById('send-btn');
const botAudio = document.getElementById('bot-audio');
const userAudio = document.getElementById('user-audio');
const playBotAudioBtn = document.getElementById('play-bot-audio-btn');
const recordingStatus = document.getElementById('recording-status');
const logContainer = document.getElementById('log-container');
const feedbackSection = document.getElementById('feedback-section');
const feedbackContent = document.getElementById('feedback-content');

// Function to hide all manual buttons
function hideAllButtons() {
    if (recordBtn) recordBtn.style.display = 'none';
    if (stopBtn) stopBtn.style.display = 'none';
    if (playBtn) playBtn.style.display = 'none';
    if (sendBtn) sendBtn.style.display = 'none';
    const recordingControls = document.querySelector('.recording-controls');
    if (recordingControls) recordingControls.style.display = 'none';
}

// Check if HTTPS is required for microphone access
function checkHTTPSRequirement() {
    const isLocalhost = window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1' ||
                       window.location.hostname === '[::1]';
    const isHTTPS = window.location.protocol === 'https:';
    
    if (!isHTTPS && !isLocalhost) {
        const warningDiv = document.createElement('div');
        warningDiv.id = 'https-warning';
        warningDiv.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #ff6b6b;
            color: white;
            padding: 15px;
            text-align: center;
            z-index: 10000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        `;
        warningDiv.innerHTML = `
            <strong>⚠️ HTTPS Required:</strong> Microphone access requires HTTPS or localhost. 
            Current URL: <code>${window.location.protocol}//${window.location.host}</code>
            <br>
            <small>Please access via HTTPS or use localhost. Microphone features will not work over HTTP.</small>
        `;
        document.body.insertBefore(warningDiv, document.body.firstChild);
        console.warn('HTTPS required for microphone access. Current protocol:', window.location.protocol);
        return false;
    }
    return true;
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check HTTPS requirement
    checkHTTPSRequirement();
    
    // Hide all manual buttons immediately
    hideAllButtons();
    
    initiateBtn.addEventListener('click', initiateCall);
    document.getElementById('load-customers-btn').addEventListener('click', loadCustomers);
    document.getElementById('end-call-btn').addEventListener('click', endCall);
    // Removed manual button listeners - fully automatic mode
    playBotAudioBtn.addEventListener('click', () => {
        if (botAudio.src) {
            botAudio.play().catch(err => {
                console.error('Error playing audio:', err);
                showError('Error playing audio. Please check your browser audio settings.');
            });
        }
    });
    
    // Ensure buttons stay hidden
    setInterval(hideAllButtons, 100);
});

// Load Customers
async function loadCustomers() {
    const loadBtn = document.getElementById('load-customers-btn');
    const customersList = document.getElementById('customers-list');
    const customersContainer = document.getElementById('customers-container');
    
    loadBtn.disabled = true;
    loadBtn.innerHTML = '<span class="loading"></span> Loading...';
    customersContainer.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE}/customers?limit=50`);
        
        if (!response.ok) {
            throw new Error('Failed to load customers');
        }

        const data = await response.json();
        
        if (data.customers && data.customers.length > 0) {
            let html = `<p style="margin-bottom: 10px; color: #666; font-size: 14px;">Found ${data.total} customer(s). Click on an agreement number to use it:</p>`;
            html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px;">';
            
            data.customers.forEach(customer => {
                const paymentInfo = customer.has_payment 
                    ? `<span style="color: #28a745;">✓ Has Payment (₹${customer.payment_amount || 'N/A'})</span>`
                    : '<span style="color: #dc3545;">✗ No Payment</span>';
                
                html += `
                    <div class="customer-card" style="padding: 12px; background: white; border-radius: 6px; border: 2px solid #e0e0e0; cursor: pointer; transition: all 0.3s;" 
                         onclick="selectCustomer('${customer.agreement_no}', '${customer.customer_name || ''}')"
                         onmouseover="this.style.borderColor='#667eea'; this.style.transform='translateY(-2px)'"
                         onmouseout="this.style.borderColor='#e0e0e0'; this.style.transform='translateY(0)'">
                        <div style="font-weight: 600; color: #667eea; margin-bottom: 5px;">${customer.agreement_no}</div>
                        <div style="font-size: 14px; color: #666; margin-bottom: 5px;">${customer.customer_name || 'N/A'}</div>
                        <div style="font-size: 12px; color: #999;">${paymentInfo}</div>
                    </div>
                `;
            });
            
            html += '</div>';
            customersContainer.innerHTML = html;
            customersList.style.display = 'block';
        } else {
            customersContainer.innerHTML = '<p style="color: #666;">No customers found in database. Please add customer data first.</p>';
            customersList.style.display = 'block';
        }
        
    } catch (error) {
        showError('Failed to load customers: ' + error.message);
        customersContainer.innerHTML = '<p style="color: #dc3545;">Error loading customers. Please check your database connection.</p>';
        customersList.style.display = 'block';
    } finally {
        loadBtn.disabled = false;
        loadBtn.innerHTML = 'Load Customers';
    }
}

// Select Customer
function selectCustomer(agreementNo, customerName) {
    document.getElementById('agreement-no').value = agreementNo;
    showStatus(initiateStatus, `Selected: ${agreementNo}${customerName ? ' - ' + customerName : ''}`, 'success');
    // Scroll to initiate button
    document.getElementById('initiate-section').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Initiate Call
async function endCall() {
    if (!callId) {
        showError('No active call to end');
        return;
    }
    
    if (!confirm('Are you sure you want to end this call?')) {
        return;
    }
    
    try {
        showStatus(recordingStatus, 'Ending call...', 'info');
        
        const response = await fetch(`${API_BASE}/call/${callId}/end`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to end call');
        }
        
        const data = await response.json();
        
        // Stop recording if active
        if (isRecording) {
            stopRecording();
        }
        
        // Update UI
        document.getElementById('call-status').textContent = 'Ended';
        document.getElementById('end-call-btn').style.display = 'none';
        
        // Show feedback
        await fetchFeedback();
        
        showStatus(recordingStatus, 'Call ended successfully', 'success');
        addLogEntry('system', 'Call ended by user');
        
    } catch (error) {
        console.error('Error ending call:', error);
        showError('Failed to end call: ' + error.message);
    }
}

async function initiateCall() {
    const agreementNo = agreementNoInput.value.trim();
    
    if (!agreementNo) {
        showStatus(initiateStatus, 'Please enter an agreement number', 'error');
        return;
    }

    initiateBtn.disabled = true;
    initiateBtn.innerHTML = '<span class="loading"></span> Initiating...';

    try {
        const response = await fetch(`${API_BASE}/call/initiate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ agreement_no: agreementNo }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to initiate call');
        }

        const data = await response.json();
        callId = data.call_id;
        
        // Update UI
        document.getElementById('call-id').textContent = callId;
        document.getElementById('current-step').textContent = data.next_step || 'call_opening';
        document.getElementById('call-status').textContent = 'In Progress';
        
        // Play bot audio
        if (!data.audio_data) {
            throw new Error('No audio data received from server');
        }
        
        // Try different audio formats
        const audioFormats = [
            { mime: 'audio/wav', type: 'wav' },
            { mime: 'audio/mpeg', type: 'mp3' },
            { mime: 'audio/ogg', type: 'ogg' },
            { mime: 'audio/webm', type: 'webm' }
        ];
        
        let audioData = null;
        let audioUrl = null;
        
        // Try to decode audio (format will be auto-detected)
        console.log('Decoding audio data, base64 length:', data.audio_data ? data.audio_data.length : 0);
        lastAudioBase64 = data.audio_data; // Store for retry attempts
        audioData = base64ToBlob(data.audio_data, 'audio/wav');
        if (audioData && audioData.size > 0) {
            lastAudioBlob = audioData; // Store for retry attempts
            audioUrl = URL.createObjectURL(audioData);
            botAudio.type = audioData.type || 'audio/wav';
            botAudio.src = audioUrl;
            console.log('Audio loaded, size:', audioData.size, 'bytes, type:', botAudio.type);
        } else {
            console.error('Failed to decode audio data or audio is empty');
            throw new Error('Failed to decode audio data or audio is empty');
        }
        
        // Ensure audio element is visible
        botAudio.style.display = 'block';
        playBotAudioBtn.style.display = 'inline-block';
        
        // Wait for audio to load, then try to play
        const tryPlay = () => {
            const playPromise = botAudio.play();
            if (playPromise !== undefined) {
                playPromise
                    .then(() => {
                        console.log('Audio playing successfully');
                        isBotSpeaking = true;
                        playBotAudioBtn.style.display = 'none'; // Hide play button if autoplay works
                    })
                    .catch(error => {
                        console.warn('Autoplay prevented:', error);
                        // Keep play button visible for manual playback
                        showStatus(initiateStatus, 'Audio ready - Click "Play Bot Message" button to hear', 'info');
                    });
            }
        };
        
        // Try immediate play (in case metadata is already loaded)
        if (botAudio.readyState >= 2) {
            tryPlay();
        } else {
            // Wait for audio to load
            botAudio.addEventListener('loadedmetadata', tryPlay, { once: true });
            botAudio.addEventListener('canplay', tryPlay, { once: true });
        }
        
        // Set up automatic flow: when bot audio ends, auto-start recording
        if (isAutomaticMode) {
            isWaitingForBotAudio = true;
            botAudio.addEventListener('ended', () => {
                console.log('Bot audio finished, auto-starting recording...');
                isBotSpeaking = false;
                isWaitingForBotAudio = false;
                // Small delay before starting recording
                setTimeout(() => {
                    if (callId && !isRecording) {
                        startRecording();
                    }
                }, 500);
            }, { once: true });
        }
        
        // Update bot message
        document.getElementById('bot-message').textContent = data.text || 'Call opening message';
        document.getElementById('bot-time').textContent = new Date().toLocaleTimeString();
        
        // Ensure audio element is visible
        botAudio.style.display = 'block';
        
        // Show end call button
        document.getElementById('end-call-btn').style.display = 'inline-block';
        
        // Show conversation section
        conversationSection.style.display = 'block';
        initiateStatus.innerHTML = '';
        showStatus(initiateStatus, `Call initiated successfully! Call ID: ${callId}`, 'success');
        
        // Show automatic mode indicator
        const autoModeIndicator = document.getElementById('auto-mode-indicator');
        if (autoModeIndicator) {
            autoModeIndicator.style.display = 'block';
        }
        
        // Fully automatic mode - hide all buttons
        hideAllButtons();
        recordingStatus.textContent = '🔄 Automatic mode - Bot will speak first, then recording starts automatically';
        
        // Request microphone permission proactively (before recording starts)
        if (isAutomaticMode) {
            try {
                // Request permission now so user can grant it before recording starts
                const permissionState = await checkMicrophonePermission();
                if (permissionState === 'prompt') {
                    // Try to get permission now (this will show the browser prompt)
                    try {
                        const testStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        // Permission granted! Stop the test stream immediately
                        testStream.getTracks().forEach(track => track.stop());
                        addLogEntry('system', 'Microphone permission granted');
                    } catch (permError) {
                        // Permission denied or error - will handle when recording starts
                        console.warn('Microphone permission not granted yet:', permError);
                        recordingStatus.textContent = '⚠️ Microphone permission needed - you\'ll be prompted when recording starts';
                    }
                } else if (permissionState === 'denied') {
                    showError('Microphone access is blocked. Please enable it in your browser settings and refresh the page.');
                    recordingStatus.textContent = '❌ Microphone access blocked';
                } else {
                    addLogEntry('system', 'Microphone permission already granted');
                }
            } catch (error) {
                console.warn('Error checking microphone permission:', error);
            }
        }
        
        // Add to log
        addLogEntry('system', `Call initiated for agreement: ${agreementNo}`);
        addLogEntry('bot', data.text || 'Call opening message');
        
    } catch (error) {
        showError(error.message);
        showStatus(initiateStatus, error.message, 'error');
    } finally {
        initiateBtn.disabled = false;
        initiateBtn.innerHTML = 'Start Call';
    }
}

// Check microphone permissions
async function checkMicrophonePermission() {
    try {
        if (navigator.permissions) {
            const result = await navigator.permissions.query({ name: 'microphone' });
            return result.state; // 'granted', 'denied', or 'prompt'
        }
        return 'prompt'; // If permissions API not available, assume prompt
    } catch (error) {
        console.warn('Permission check failed:', error);
        return 'prompt';
    }
}

// Start Recording with VAD
async function startRecording() {
    try {
        // If bot is currently speaking, pause/stop bot audio first (barge-in)
        if (isBotSpeaking) {
            try {
                botAudio.pause();
                botAudio.currentTime = 0;
            } catch (e) {
                console.warn('Error stopping bot audio during barge-in:', e);
            }
            isBotSpeaking = false;
            isWaitingForBotAudio = false;
        }

        // Check HTTPS requirement first
        const isLocalhost = window.location.hostname === 'localhost' || 
                           window.location.hostname === '127.0.0.1' ||
                           window.location.hostname === '[::1]';
        const isHTTPS = window.location.protocol === 'https:';
        
        if (!isHTTPS && !isLocalhost) {
            const errorMsg = '❌ HTTPS Required: Microphone access requires HTTPS or localhost.\n\n' +
                'Current URL: ' + window.location.protocol + '//' + window.location.host + '\n\n' +
                'Solutions:\n' +
                '1. Use HTTPS: Access via https://' + window.location.host + '\n' +
                '2. Use localhost: Access via http://localhost:8000\n' +
                '3. Set up SSL certificate (Let\'s Encrypt) for production';
            showError(errorMsg);
            recordingStatus.textContent = '❌ HTTPS required for microphone';
            addLogEntry('system', 'Microphone blocked: HTTPS required (current: ' + window.location.protocol + ')');
            return;
        }

        // Check permissions first
        const permissionState = await checkMicrophonePermission();
        if (permissionState === 'denied') {
            showError('Microphone access is blocked. Please enable it in your browser settings:\n\n' +
                'Chrome/Edge: Click the lock icon in address bar → Site settings → Microphone → Allow\n' +
                'Firefox: Click the lock icon → Permissions → Microphone → Allow\n' +
                'Safari: Safari → Settings → Websites → Microphone → Allow for this site');
            recordingStatus.textContent = '❌ Microphone access denied';
            return;
        }

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        silenceStartTime = null;
        isSpeaking = false;

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(audioBlob);
            userAudio.src = audioUrl;
            userAudio.style.display = 'none'; // Hide in automatic mode
            
            // Stop VAD
            stopVAD();
            
            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());
            
            // Automatically send audio in automatic mode
            if (isAutomaticMode && audioChunks.length > 0) {
                setTimeout(() => {
                    sendAudio();
                }, 300);
            }
        };

        mediaRecorder.start();
        isRecording = true;
        
        // Initialize VAD
        startVAD(stream);
        
        // Update UI - no buttons, just status
        recordingStatus.textContent = '🔴 Recording... Speak now';
        recordingStatus.classList.add('active', 'recording');
        
        addLogEntry('system', 'Recording started automatically with VAD');
        
    } catch (error) {
        let errorMessage = 'Microphone access denied. ';
        
        if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
            errorMessage += 'Please allow microphone access:\n\n' +
                '1. Click the lock/camera icon in your browser\'s address bar\n' +
                '2. Find "Microphone" or "Camera" settings\n' +
                '3. Change it to "Allow"\n' +
                '4. Refresh the page and try again';
        } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
            errorMessage += 'No microphone found. Please connect a microphone and try again.';
        } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
            errorMessage += 'Microphone is being used by another application. Please close other apps using the microphone and try again.';
        } else {
            errorMessage += 'Please check your browser settings and allow microphone access.';
        }
        
        showError(errorMessage);
        recordingStatus.textContent = '❌ Microphone access error';
        console.error('Recording error:', error);
        addLogEntry('system', `Recording error: ${error.name} - ${error.message}`);
    }
}

// Start Voice Activity Detection
function startVAD(stream) {
    try {
        // Create audio context
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = vadConfig.smoothingTimeConstant;
        
        microphone = audioContext.createMediaStreamSource(stream);
        microphone.connect(analyser);
        
        // Start VAD monitoring
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const startTime = Date.now();
        
        function checkVAD() {
            if (!isRecording) {
                return;
            }
            
            analyser.getByteTimeDomainData(dataArray);
            
            // Calculate RMS (Root Mean Square) volume
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                const normalized = (dataArray[i] - 128) / 128;
                sum += normalized * normalized;
            }
            const rms = Math.sqrt(sum / dataArray.length);
            const volume = rms;
            
            // Update UI with volume indicator
            updateVADIndicator(volume);
            
            // Check if speaking
            if (volume > vadConfig.silenceThreshold) {
                // User is speaking
                if (!isSpeaking) {
                    isSpeaking = true;
                    silenceStartTime = null;
                    recordingStatus.textContent = '🔴 Recording... 🗣️ Speaking';
                    recordingStatus.classList.add('speaking');
                }
            } else {
                // Silence detected
                if (isSpeaking) {
                    isSpeaking = false;
                    silenceStartTime = Date.now();
                    recordingStatus.textContent = '🔴 Recording... ⏸️ Silence detected';
                    recordingStatus.classList.remove('speaking');
                }
                
                // Check if silence duration exceeded threshold
                if (silenceStartTime !== null) {
                    const silenceDuration = Date.now() - silenceStartTime;
                    const recordingDuration = Date.now() - startTime;
                    
                    // Only auto-stop if:
                    // 1. Silence duration exceeds threshold
                    // 2. Minimum recording duration has passed
                    if (silenceDuration >= vadConfig.silenceDuration && 
                        recordingDuration >= vadConfig.minRecordingDuration) {
                        console.log('Auto-stopping recording due to silence');
                        recordingStatus.textContent = '✅ Auto-stopped (silence detected) - Sending...';
                        stopRecording();
                        // Audio will be auto-sent in mediaRecorder.onstop
                        return;
                    }
                }
            }
            
            vadAnimationFrame = setTimeout(checkVAD, vadConfig.checkInterval);
        }
        
        checkVAD();
        
    } catch (error) {
        console.error('VAD initialization error:', error);
        recordingStatus.textContent = '🔴 Recording... (VAD unavailable)';
    }
}

// Stop Voice Activity Detection
function stopVAD() {
    if (vadAnimationFrame) {
        clearTimeout(vadAnimationFrame);
        vadAnimationFrame = null;
    }
    
    if (microphone) {
        try {
            microphone.disconnect();
        } catch (e) {
            // Ignore disconnect errors
        }
        microphone = null;
    }
    
    if (analyser) {
        analyser = null;
    }
    
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close().catch(e => {
            console.warn('Error closing audio context:', e);
        });
        audioContext = null;
    }
    
    // Clear VAD indicator
    clearVADIndicator();
}

// Update VAD visual indicator
function updateVADIndicator(volume) {
    const recordIcon = document.getElementById('record-icon');
    if (!recordIcon) return;
    
    // Calculate indicator level (0-5)
    const level = Math.min(5, Math.floor(volume * 10));
    
    // Update icon with visual feedback
    if (volume > vadConfig.silenceThreshold) {
        // Speaking - show animated indicator
        const bars = '█'.repeat(level);
        recordIcon.textContent = `🎤${bars}`;
        recordIcon.style.color = '#28a745';
    } else {
        // Silent
        recordIcon.textContent = '🎤';
        recordIcon.style.color = '#dc3545';
    }
}

// Clear VAD indicator
function clearVADIndicator() {
    const recordIcon = document.getElementById('record-icon');
    if (recordIcon) {
        recordIcon.textContent = '🎤';
        recordIcon.style.color = '';
    }
}

// Stop Recording
function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        
        // Stop VAD
        stopVAD();
        
        // Update UI - no buttons to update
        if (!recordingStatus.textContent.includes('Sending')) {
            recordingStatus.textContent = '✅ Recording stopped';
        }
        recordingStatus.classList.remove('recording', 'speaking');
        
        addLogEntry('system', 'Recording stopped automatically');
    }
}

// Play Recording - Not used in automatic mode
function playRecording() {
    // Removed - not needed in automatic mode
}

// Send Audio
async function sendAudio() {
    if (!callId) {
        showError('No active call. Please initiate a call first.');
        return;
    }

    if (audioChunks.length === 0) {
        showError('No audio recorded. Please record your response first.');
        return;
    }

    // Update status - no button to disable
    recordingStatus.textContent = '📤 Sending audio...';

    try {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append('audio_file', audioBlob, 'recording.wav');

        const response = await fetch(`${API_BASE}/call/${callId}/audio`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to process audio');
        }

        const data = await response.json();
        
        // Update current step
        document.getElementById('current-step').textContent = data.next_step || 'unknown';
        
        // Play bot response audio
        if (!data.audio_data) {
            console.error('No audio data in response');
            showError('No audio received from bot. Please try again.');
            return;
        }
        
        console.log('Decoding bot response audio, base64 length:', data.audio_data ? data.audio_data.length : 0);
        lastAudioBase64 = data.audio_data; // Store for retry attempts
        const audioData = base64ToBlob(data.audio_data, 'audio/wav');
        if (!audioData || audioData.size === 0) {
            console.error('Failed to decode audio data or audio is empty');
            showError('Failed to decode audio data or audio is empty');
            return;
        }
        
        lastAudioBlob = audioData; // Store for retry attempts
        const audioUrl = URL.createObjectURL(audioData);
        botAudio.type = audioData.type || 'audio/wav';
        botAudio.src = audioUrl;
        console.log('Bot response audio loaded, size:', audioData.size, 'bytes, type:', botAudio.type);
        
        // Ensure audio element is visible
        botAudio.style.display = 'block';
        playBotAudioBtn.style.display = 'inline-block';
        
        // Try to play audio
        const tryPlay = () => {
            const playPromise = botAudio.play();
            if (playPromise !== undefined) {
                playPromise
                    .then(() => {
                        console.log('Bot response audio playing');
                        isBotSpeaking = true;
                        playBotAudioBtn.style.display = 'none';
                    })
                    .catch(error => {
                        console.warn('Autoplay prevented:', error);
                        // Keep play button visible
                    });
            }
        };
        
        if (botAudio.readyState >= 2) {
            tryPlay();
        } else {
            botAudio.addEventListener('loadedmetadata', tryPlay, { once: true });
            botAudio.addEventListener('canplay', tryPlay, { once: true });
        }
        
        // Set up automatic flow: when bot audio ends, auto-start recording
        if (isAutomaticMode) {
            botAudio.addEventListener('ended', () => {
                console.log('Bot response audio finished, auto-starting recording...');
                isWaitingForBotAudio = false;
                // Small delay before starting recording
                setTimeout(() => {
                    if (callId && !isRecording && !data.is_complete) {
                        startRecording();
                    }
                }, 500);
            }, { once: true });
            isWaitingForBotAudio = true;
        }
        
        // Update bot message
        document.getElementById('bot-message').textContent = data.text || 'Bot response';
        document.getElementById('bot-time').textContent = new Date().toLocaleTimeString();
        
        // Add to log
        addLogEntry('user', 'Audio sent');
        addLogEntry('bot', data.text || 'Bot response');
        
        // Reset recording UI
        audioChunks = [];
        userAudio.style.display = 'none';
        recordingStatus.classList.remove('active');
        recordingStatus.textContent = '✅ Audio sent - Waiting for bot response...';
        
        // Check if call is complete
        if (data.is_complete) {
            document.getElementById('call-status').textContent = 'Completed';
            recordingStatus.textContent = '✅ Call completed';
            isAutomaticMode = false; // Stop automatic flow
            await fetchFeedback();
        }
        
    } catch (error) {
        showError(error.message);
        recordingStatus.textContent = '❌ Error sending audio';
    }
}

// Fetch Feedback
async function fetchFeedback() {
    if (!callId) return;

    try {
        const response = await fetch(`${API_BASE}/call/${callId}/feedback`);
        
        if (response.ok) {
            const feedback = await response.json();
            displayFeedback(feedback);
        }
    } catch (error) {
        console.error('Error fetching feedback:', error);
    }
}

// Display Feedback
function displayFeedback(feedback) {
    feedbackSection.style.display = 'block';
    
    const complianceBadge = feedback.is_compliant 
        ? '<span class="compliance-badge compliant">Compliant</span>'
        : '<span class="compliance-badge non-compliant">Non-Compliant</span>';
    
    let html = `
        <div class="feedback-item">
            <strong>Call ID:</strong> ${feedback.call_id}
        </div>
        <div class="feedback-item">
            <strong>Agreement Number:</strong> ${feedback.agreement_no || 'N/A'}
        </div>
        <div class="feedback-item">
            <strong>Customer Name:</strong> ${feedback.customer_name || 'N/A'}
        </div>
        <div class="feedback-item">
            <strong>Compliance Status:</strong> ${complianceBadge}
        </div>
    `;
    
    if (feedback.compliance_notes) {
        html += `
            <div class="feedback-item">
                <strong>Compliance Notes:</strong> ${feedback.compliance_notes}
            </div>
        `;
    }
    
    if (feedback.responses) {
        html += '<div class="feedback-item"><strong>Responses:</strong><ul style="margin-top: 10px; padding-left: 20px;">';
        for (const [key, value] of Object.entries(feedback.responses)) {
            if (value !== null && value !== undefined) {
                html += `<li><strong>${key.replace(/_/g, ' ')}:</strong> ${value}</li>`;
            }
        }
        html += '</ul></div>';
    }
    
    feedbackContent.innerHTML = html;
}

// Utility Functions
function showStatus(element, message, type) {
    element.textContent = message;
    element.className = `status-message ${type}`;
}

function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

function addLogEntry(type, message) {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `
        <strong>${type.toUpperCase()}:</strong> ${message}
        <span style="float: right; color: #999; font-size: 12px;">${new Date().toLocaleTimeString()}</span>
    `;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Detect audio format from bytes
function detectAudioFormat(byteArray) {
    if (byteArray.length < 4) {
        return null;
    }
    
    // Check for WAV (RIFF header)
    const riff = String.fromCharCode(byteArray[0], byteArray[1], byteArray[2], byteArray[3]);
    if (riff === 'RIFF') {
        return 'audio/wav';
    }
    
    // Check for MP3 (ID3 tag or MPEG header)
    // ID3 tag starts with "ID3"
    const id3 = String.fromCharCode(byteArray[0], byteArray[1], byteArray[2]);
    if (id3 === 'ID3') {
        return 'audio/mpeg';
    }
    
    // MPEG header: 0xFF 0xFB or 0xFF 0xF3 or 0xFF 0xF2
    if (byteArray[0] === 0xFF && (byteArray[1] === 0xFB || byteArray[1] === 0xF3 || byteArray[1] === 0xF2)) {
        return 'audio/mpeg';
    }
    
    // Check for OGG (OggS)
    const ogg = String.fromCharCode(byteArray[0], byteArray[1], byteArray[2], byteArray[3]);
    if (ogg === 'OggS') {
        return 'audio/ogg';
    }
    
    // Check for WebM (starts with 0x1A 0x45 0xDF 0xA3)
    if (byteArray[0] === 0x1A && byteArray[1] === 0x45 && byteArray[2] === 0xDF && byteArray[3] === 0xA3) {
        return 'audio/webm';
    }
    
    // Check for FLAC (fLaC)
    if (byteArray.length >= 4) {
        const flac = String.fromCharCode(byteArray[0], byteArray[1], byteArray[2], byteArray[3]);
        if (flac === 'fLaC') {
            return 'audio/flac';
        }
    }
    
    return null; // Unknown format
}

function base64ToBlob(base64, mimeType) {
    try {
        if (!base64 || base64.length === 0) {
            console.error('Empty base64 string');
            return null;
        }
        
        const byteCharacters = atob(base64);
        if (byteCharacters.length === 0) {
            console.error('Decoded audio is empty');
            return null;
        }
        
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        
        // Check if audio data is corrupted (all zeros or mostly zeros)
        const firstBytes = byteArray.slice(0, 16);
        const allZeros = firstBytes.every(b => b === 0);
        const mostlyZeros = firstBytes.filter(b => b === 0).length > 12;
        
        if (allZeros) {
            console.error('ERROR: Audio data appears to be all zeros - corrupted or empty!');
            console.error('First 16 bytes:', Array.from(firstBytes).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' '));
            showError('Audio data is corrupted (all zeros). Please check TTS service response.');
            return null;
        } else if (mostlyZeros) {
            console.warn('WARNING: Audio data appears mostly zeros - may be corrupted!');
        }
        
        // Check if we have valid audio data (non-zero bytes)
        const nonZeroCount = Array.from(byteArray).filter(b => b !== 0).length;
        if (nonZeroCount < byteArray.length * 0.1) {
            console.error('ERROR: Less than 10% of audio data is non-zero - likely corrupted!');
            showError('Audio data appears corrupted. Please check TTS service.');
            return null;
        }
        
        // Detect actual audio format
        const detectedFormat = detectAudioFormat(byteArray);
        if (detectedFormat && detectedFormat !== mimeType) {
            console.log(`Detected audio format: ${detectedFormat} (was expecting ${mimeType})`);
            mimeType = detectedFormat;
        } else if (!detectedFormat) {
            console.warn('Could not detect audio format, using provided:', mimeType);
            // Show first few bytes for debugging
            const header = Array.from(byteArray.slice(0, 8))
                .map(b => '0x' + b.toString(16).padStart(2, '0'))
                .join(' ');
            console.log('First 8 bytes:', header);
        }
        
        const blob = new Blob([byteArray], { type: mimeType });
        console.log(`Created blob: ${blob.size} bytes, type: ${blob.type}`);
        return blob;
    } catch (error) {
        console.error('Error decoding base64 audio:', error);
        showError('Error processing audio data. Please try again.');
        return null;
    }
}

// Store original base64 data for retry attempts
let lastAudioBase64 = null;
let lastAudioBlob = null;

// Handle audio loading errors
botAudio.addEventListener('error', (e) => {
    const error = botAudio.error;
    let errorMessage = 'Error loading audio. ';
    
    if (error) {
        switch(error.code) {
            case error.MEDIA_ERR_ABORTED:
                errorMessage += 'Audio loading aborted.';
                break;
            case error.MEDIA_ERR_NETWORK:
                errorMessage += 'Network error while loading audio.';
                break;
            case error.MEDIA_ERR_DECODE:
            case error.MEDIA_ERR_SRC_NOT_SUPPORTED:
                errorMessage += 'Audio format not supported by browser. ';
                // Try alternative formats
                if (lastAudioBase64) {
                    const formats = ['audio/mpeg', 'audio/ogg', 'audio/webm', 'audio/flac'];
                    const currentFormat = botAudio.type || 'audio/wav';
                    const currentIndex = formats.indexOf(currentFormat);
                    
                    if (currentIndex < formats.length - 1) {
                        const nextFormat = formats[currentIndex + 1];
                        console.log(`Trying alternative format: ${nextFormat}`);
                        
                        // Revoke old URL
                        if (botAudio.src && botAudio.src.startsWith('blob:')) {
                            URL.revokeObjectURL(botAudio.src);
                        }
                        
                        // Try with new format
                        const newBlob = base64ToBlob(lastAudioBase64, nextFormat);
                        if (newBlob) {
                            const newUrl = URL.createObjectURL(newBlob);
                            botAudio.type = nextFormat;
                            botAudio.src = newUrl;
                            console.log(`Retrying with format: ${nextFormat}`);
                            return; // Don't show error yet, let it try
                        }
                    }
                }
                errorMessage += 'The audio format from TTS service may not be browser-compatible.';
                break;
            default:
                errorMessage += `Unknown error (code: ${error.code}).`;
        }
        console.error('Audio error details:', {
            code: error.code,
            message: error.message,
            currentFormat: botAudio.type,
            src: botAudio.src ? botAudio.src.substring(0, 50) + '...' : 'no src'
        });
    } else {
        errorMessage += 'Unknown audio error.';
        console.error('Audio error event:', e);
    }
    
    console.error('Full audio error:', error);
    showError(errorMessage);
    // Keep play button visible in case user wants to try
    playBotAudioBtn.style.display = 'inline-block';
});

botAudio.addEventListener('loadeddata', () => {
    console.log('Audio loaded successfully, duration:', botAudio.duration, 'seconds');
    console.log('Audio readyState:', botAudio.readyState);
    console.log('Audio networkState:', botAudio.networkState);
});

botAudio.addEventListener('loadstart', () => {
    console.log('Audio loading started');
});

botAudio.addEventListener('progress', () => {
    if (botAudio.buffered.length > 0) {
        console.log('Audio loading progress:', botAudio.buffered.end(0), '/', botAudio.duration);
    }
});

botAudio.addEventListener('canplay', () => {
    console.log('Audio can play');
    // Try autoplay again when audio is ready
    if (botAudio.src && !botAudio.paused === false) {
        botAudio.play().catch(err => {
            console.log('Autoplay still blocked, user can click play button');
        });
    }
});

// Track when bot is actively speaking for barge-in support
botAudio.addEventListener('play', () => {
    isBotSpeaking = true;
});

botAudio.addEventListener('pause', () => {
    // pause can be called without ending; only clear flag if not at end
    if (botAudio.currentTime < (botAudio.duration || Infinity)) {
        isBotSpeaking = false;
    }
});

botAudio.addEventListener('ended', () => {
    isBotSpeaking = false;
});