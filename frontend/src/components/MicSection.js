import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './MicSection.css';

const MicSection = () => {
    const [isRecording, setIsRecording] = useState(false);
    const [recordingTime, setRecordingTime] = useState(0);
    const [chunkCount, setChunkCount] = useState(0);
    const [backendHealth, setBackendHealth] = useState(null);
    const [lastUpload, setLastUpload] = useState(null);
    const [galleryItems, setGalleryItems] = useState([]);
    const [summaryText, setSummaryText] = useState('Summary will appear here once the session starts.');
    const [quizItems, setQuizItems] = useState([]);
    const [modelText, setModelText] = useState('Model output will stream here in real time.');
    const [isGalleryOpen, setIsGalleryOpen] = useState(false);
    const [selectedImage, setSelectedImage] = useState(null);
    const streamRef = useRef(null);
    const audioChunksRef = useRef([]);
    const intervalRef = useRef(null);
    const timerRef = useRef(null);
    const chunkStartTimeRef = useRef(null);
    const isSendingChunkRef = useRef(false);
    const isRecordingRef = useRef(false);
    const chunkCountRef = useRef(0);

    // Polling interval to check if we can send the next chunk
    // The actual "chunk duration" is dynamic: it's however long the previous request took + buffering time.
    const POLLING_INTERVAL = 1000;
    const MIN_CHUNK_DURATION = 5000;

    useEffect(() => {
        if (isRecording) {
            timerRef.current = setInterval(() => {
                setRecordingTime((prev) => prev + 1);
            }, 1000);
        } else {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        }

        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        };
    }, [isRecording]);

    useEffect(() => {
        let isMounted = true;
        const check = async () => {
            try {
                const res = await fetch('http://localhost:8000/api/health');
                const data = await res.json();
                if (isMounted) setBackendHealth(data);
            } catch {
                if (isMounted) setBackendHealth({ status: 'down' });
            }
        };
        check();
        const id = setInterval(check, 30000);
        return () => {
            isMounted = false;
            clearInterval(id);
        };
    }, []);

    useEffect(() => {
        const socket = new WebSocket('ws://localhost:8000/ws/home');

        socket.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                const items = Array.isArray(payload?.images) ? payload.images : [];
                const normalized = items
                    .map((item, index) => ({
                        id: item?.id ?? index,
                        imageUrl: item?.imageUrl ?? item?.url ?? item?.image ?? '',
                        title: item?.title ?? 'Learning Snapshot',
                        description: item?.description ?? item?.text ?? ''
                    }))
                    .filter((item) => item.imageUrl);
                if (normalized.length) {
                    setGalleryItems(normalized);
                }
                if (typeof payload?.summary === 'string') {
                    setSummaryText(payload.summary);
                }
                if (Array.isArray(payload?.quiz)) {
                    setQuizItems(payload.quiz);
                }
                if (typeof payload?.model === 'string') {
                    setModelText(payload.model);
                }
            } catch {
            }
        };

        return () => {
            socket.close();
        };
    }, []);

    // New AudioContext Refs and Logic
    const audioContextRef = useRef(null);
    const processorRef = useRef(null);
    const sourceRef = useRef(null);

    useEffect(() => {
        return () => {
            if (audioContextRef.current) {
                audioContextRef.current.close();
            }
            if (streamRef.current) {
                streamRef.current.getTracks().forEach(track => track.stop());
            }
        };
    }, []);

    // Convert Float32 to Int16 PCM
    const convertToPCM = (samples) => {
        const buffer = new ArrayBuffer(samples.length * 2);
        const view = new DataView(buffer);
        for (let i = 0; i < samples.length; i++) {
            let s = Math.max(-1, Math.min(1, samples[i]));
            // standard conversion
            s = s < 0 ? s * 0x8000 : s * 0x7FFF;
            view.setInt16(i * 2, s, true); // little-endian
        }
        return new Blob([view], { type: 'application/octet-stream' });
    };

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });
            streamRef.current = stream;

            const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            if (audioContext.sampleRate !== 16000) {
                console.warn('AudioContext sample rate is ' + audioContext.sampleRate + ', expected 16000. Audio will be sent at ' + audioContext.sampleRate);
            }
            audioContextRef.current = audioContext;

            const source = audioContext.createMediaStreamSource(stream);
            sourceRef.current = source;

            // bufferSize 4096, 1 input channel, 1 output channel
            const processor = audioContext.createScriptProcessor(4096, 1, 1);
            processorRef.current = processor;

            audioChunksRef.current = [];
            chunkStartTimeRef.current = Date.now();
            isSendingChunkRef.current = false;

            processor.onaudioprocess = (e) => {
                if (!isRecordingRef.current) return;
                const inputData = e.inputBuffer.getChannelData(0);
                // Clone the data because input buffer is reused
                audioChunksRef.current.push(new Float32Array(inputData));
            };

            // Connect graph: Source -> Processor -> Gain(Mute) -> Destination
            const gainNode = audioContext.createGain();
            gainNode.gain.value = 0;

            source.connect(processor);
            processor.connect(gainNode);
            gainNode.connect(audioContext.destination);

            isRecordingRef.current = true;
            setIsRecording(true);
            setRecordingTime(0);
            chunkCountRef.current = 0;
            setChunkCount(0);

            // Set up interval to check for chunks to send
            intervalRef.current = setInterval(async () => {
                const timeSinceLastChunk = Date.now() - (chunkStartTimeRef.current || Date.now());

                if (isRecordingRef.current && !isSendingChunkRef.current && timeSinceLastChunk >= MIN_CHUNK_DURATION) {
                    isSendingChunkRef.current = true;
                    chunkStartTimeRef.current = Date.now();

                    try {
                        const currentCount = chunkCountRef.current;
                        // This will grab ALL allowed accumulated audio
                        await sendAudioChunk(currentCount);
                        chunkCountRef.current += 1;
                        setChunkCount(chunkCountRef.current);
                    } finally {
                        isSendingChunkRef.current = false;
                    }
                }
            }, POLLING_INTERVAL);

        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Could not access microphone. Please check permissions.');
        }
    };

    const stopRecording = async () => {
        isRecordingRef.current = false;
        setIsRecording(false);

        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }

        // Cleanup Audio Nodes
        if (sourceRef.current) sourceRef.current.disconnect();
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current.onaudioprocess = null;
        }
        if (audioContextRef.current) {
            // Send final chunk before closing
            if (audioChunksRef.current.length > 0) {
                await sendAudioChunk(chunkCountRef.current);
            }
            audioContextRef.current.close();
        }

        // Stop stream tracks
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }

        audioChunksRef.current = [];

        // Notify backend to stop
        try {
            await fetch('http://localhost:8000/stop', {
                method: 'POST',
            });
            console.log('Stop signal sent to backend');
        } catch (error) {
            console.error('Error sending stop signal:', error);
        }
    };

    const sendAudioChunk = async (chunkNum) => {
        // Snapshot current chunks and clear ref immediately to continue recording
        if (audioChunksRef.current.length === 0) return;

        const currentChunks = [...audioChunksRef.current];
        audioChunksRef.current = []; // Clear for next batch

        // Flatten Float32Arrays
        const totalLength = currentChunks.reduce((acc, chunk) => acc + chunk.length, 0);
        const mergedSamples = new Float32Array(totalLength);
        let offset = 0;
        for (const chunk of currentChunks) {
            mergedSamples.set(chunk, offset);
            offset += chunk.length;
        }

        // Encode to Raw PCM 16-bit
        const audioBlob = convertToPCM(mergedSamples);

        const formData = new FormData();
        formData.append('audio', audioBlob, `chunk_${Date.now()}.pcm`);
        formData.append('chunk_number', chunkNum);
        formData.append('timestamp', new Date().toISOString());

        try {
            const response = await fetch('http://localhost:8000/transcribe-bytes', {
                method: 'POST',
                body: formData,
            });

            if (response.ok) {
                const data = await response.json();
                setLastUpload({ ok: true, at: new Date().toISOString(), data });
                console.log(`Chunk ${chunkNum} sent successfully`);
            } else {
                setLastUpload({ ok: false, at: new Date().toISOString(), error: `HTTP ${response.status}` });
                console.error('Failed to send audio chunk');
            }
        } catch (error) {
            setLastUpload({ ok: false, at: new Date().toISOString(), error: String(error) });
            console.error('Error sending audio chunk:', error);
        }
    };

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    return (
        <section className="mic-section">
            <div className="dashboard-grid">
                <div className="mic-container">
                    <div className="mic-controls">
                        <div className="mic-visual">
                            <div className={`mic-circle ${isRecording ? 'recording' : ''}`}>
                                <div className="recording-waves">
                                    <div className="wave"></div>
                                    <div className="wave"></div>
                                    <div className="wave"></div>
                                </div>
                                <svg
                                    className="mic-icon"
                                    viewBox="0 0 24 24"
                                    fill="currentColor"
                                    xmlns="http://www.w3.org/2000/svg"
                                >
                                    <path d="M12 14C14.21 14 16 12.21 16 10V4C16 1.79 14.21 0 12 0C9.79 0 8 1.79 8 4V10C8 12.21 9.79 14 12 14ZM18 10C18 13.31 15.31 16 12 16C8.69 16 6 13.31 6 10H4C4 13.97 7.03 17.25 10.88 17.88C11.2307 17.9372 11.5833 17.9814 11.9378 18.0123C11.9585 18.0141 11.9792 18.0159 12 18.0177V21H10V23H14V21H12V18.0177C12.0208 18.0159 12.0415 18.0141 12.0622 18.0123C12.4167 17.9814 12.7693 17.9372 13.12 17.88C16.97 17.25 20 13.97 20 10H18Z" />
                                </svg>
                            </div>
                        </div>

                        <div className="timer-display">
                            {formatTime(recordingTime)}
                        </div>

                        <div className={`status-badge ${isRecording ? 'recording' : ''}`}>
                            {isRecording ? 'Recording Live Audio' : 'Ready to Record'}
                        </div>

                        {!isRecording ? (
                            <button className="action-button start" onClick={startRecording}>
                                Start Recording
                            </button>
                        ) : (
                            <button className="action-button stop" onClick={stopRecording}>
                                Stop Recording
                            </button>
                        )}

                        <div className="stats-footer">
                            <div className="stat-item">
                                <span className="stat-label">Chunks</span>
                                <span className="stat-value">{chunkCount}</span>
                            </div>
                            <div className="stat-item">
                                <span className="stat-label">Last Upload</span>
                                <span className="stat-value">
                                    {lastUpload ? (
                                        lastUpload.ok ? (
                                            <span style={{ color: '#22c55e' }}>Success</span>
                                        ) : (
                                            <span style={{ color: '#ef4444' }}>Failed</span>
                                        )
                                    ) : (
                                        '--:--'
                                    )}
                                </span>
                            </div>
                            <div className="stat-item">
                                <span className="stat-label">System Status</span>
                                <div className="health-indicator">
                                    <div className={`health-dot ${backendHealth?.status === 'ok' ? 'up' : 'down'}`}></div>
                                    <span className="stat-value" style={{ fontSize: '0.75rem' }}>
                                        {backendHealth?.status === 'ok' ? 'ONLINE' : 'OFFLINE'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="dashboard-card summary-card">
                    <div className="card-header">
                        <h3 className="card-title">Summary</h3>
                    </div>
                    <div className="card-content scrollable">
                        <div className="markdown-content">
                            <ReactMarkdown>{summaryText}</ReactMarkdown>
                        </div>
                    </div>
                </div>

                <div className="dashboard-card quiz-card">
                    <div className="card-header">
                        <h3 className="card-title">Quiz</h3>
                    </div>
                    <div className="card-content scrollable">
                        {quizItems.length > 0 ? (
                            <div className="quiz-list">
                                {quizItems.map((quizItem, index) => (
                                    <div className="quiz-item" key={index}>
                                        <span className="quiz-question">{quizItem.question ?? `Question ${index + 1}`}</span>
                                        {Array.isArray(quizItem.options) && quizItem.options.length > 0 ? (
                                            <div className="quiz-options">
                                                {quizItem.options.map((option, optionIndex) => (
                                                    <span className="quiz-option" key={optionIndex}>{option}</span>
                                                ))}
                                            </div>
                                        ) : null}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="info-text">Quiz questions will appear here once available.</p>
                        )}
                    </div>
                </div>

                <div className="dashboard-card model-card">
                    <div className="card-header">
                        <h3 className="card-title">Model Output</h3>
                    </div>
                    <div className="card-content scrollable">
                        <p className="info-text">{modelText}</p>
                    </div>
                </div>

                <div className="dashboard-card gallery-card">
                    <div className="card-header">
                        <h3 className="card-title">Visual Notes</h3>
                    </div>
                    <div className="card-content">
                        <div className="showcase-grid-compact">
                            {galleryItems.length > 0 ? (
                                galleryItems.slice(0, 4).map((item, index) => {
                                    const isFourthAndMore = index === 3 && galleryItems.length > 4;
                                    return (
                                        <div
                                            className={`showcase-card compact ${isFourthAndMore ? 'more-trigger' : ''}`}
                                            key={item.id}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setIsGalleryOpen(true);
                                            }}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <img className="showcase-image" src={item.imageUrl} alt={item.title} />
                                            {isFourthAndMore ? (
                                                <div className="more-overlay">
                                                    <span className="more-count">+{galleryItems.length - 3}</span>
                                                </div>
                                            ) : (
                                                <div className="showcase-caption overlay">
                                                    <span className="showcase-caption-title">{item.title}</span>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })
                            ) : (
                                <div className="showcase-empty compact">
                                    No images yet
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {isGalleryOpen ? (
                <div className="gallery-modal">
                    <div className="gallery-modal-backdrop" onClick={() => setIsGalleryOpen(false)}></div>
                    <div className="gallery-modal-content">
                        <div className="gallery-modal-header">
                            <h3 className="gallery-modal-title">All Images</h3>
                            <button className="gallery-modal-close" type="button" onClick={() => setIsGalleryOpen(false)}>
                                Close
                            </button>
                        </div>
                        <div className="gallery-modal-grid">
                            {galleryItems.map((item) => (
                                <div
                                    className="gallery-modal-card"
                                    key={item.id}
                                    onClick={() => setSelectedImage(item)}
                                    style={{ cursor: 'pointer' }}
                                >
                                    <img className="gallery-modal-image" src={item.imageUrl} alt={item.title} />
                                    <div className="gallery-modal-caption">
                                        <span className="gallery-modal-title-text">{item.title}</span>
                                        {item.description ? (
                                            <span className="gallery-modal-caption-text">{item.description}</span>
                                        ) : null}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            ) : null}

            {selectedImage ? (
                <div className="lightbox-overlay" onClick={() => setSelectedImage(null)}>
                    <button className="lightbox-close" onClick={() => setSelectedImage(null)}>
                        ×
                    </button>
                    <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
                        <img className="lightbox-image" src={selectedImage.imageUrl} alt={selectedImage.title} />
                        <div className="lightbox-caption">
                            <h3>{selectedImage.title}</h3>
                            {selectedImage.description && <p>{selectedImage.description}</p>}
                        </div>
                    </div>
                </div>
            ) : null}
        </section>
    );
};

export default MicSection;
