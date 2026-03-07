import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Upload, X, File, CheckCircle } from 'lucide-react';
import './UploadInterface.css';

const UploadInterface = ({ compact = false }) => {
    const [dragActive, setDragActive] = useState(false);
    const [files, setFiles] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState(null); // 'success' | 'error'
    const [uploadedContext, setUploadedContext] = useState(
        JSON.parse(localStorage.getItem('uploadedContext') || '[]')
    );
    const inputRef = useRef(null);

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFiles(Array.from(e.dataTransfer.files));
        }
    };

    const handleChange = (e) => {
        e.preventDefault();
        if (e.target.files && e.target.files[0]) {
            handleFiles(Array.from(e.target.files));
        }
    };

    const handleFiles = (newFiles) => {
        setFiles(prev => [...prev, ...newFiles]);
        setUploadStatus(null);
    };

    const removeFile = (index) => {
        setFiles(prev => prev.filter((_, i) => i !== index));
    };

    const handleUpload = async () => {
        if (files.length === 0) return;

        setUploading(true);

        try {
            const formData = new FormData();
            files.forEach(file => {
                formData.append('files', file);
            });

            // Call the backend API
            const response = await fetch('http://localhost:8000/api/upload-doc', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Upload failed');
            }

            const data = await response.json();
            console.log('Upload success:', data);

            // Update local storage with new files and categories
            if (data.files) {
                const updatedContext = [...uploadedContext, ...data.files];
                setUploadedContext(updatedContext);
                localStorage.setItem('uploadedContext', JSON.stringify(updatedContext));
            }

            setUploadStatus('success');

            // Clear pending files
            setTimeout(() => {
                setUploadStatus(null);
                setFiles([]);
            }, 3000);

        } catch (error) {
            console.error("Upload failed", error);
            setUploadStatus('error');
            alert(`Upload failed: ${error.message}`);
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className={`upload-interface ${compact ? 'compact' : ''}`}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="upload-card"
            >
                <div className="upload-header">
                    <h2>Upload Documents</h2>
                    <p>Upload files to use with the AI tools below.</p>
                </div>

                <form
                    className={`drop-zone ${dragActive ? "drag-active" : ""}`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => inputRef.current.click()}
                >
                    <input
                        ref={inputRef}
                        type="file"
                        multiple
                        onChange={handleChange}
                        style={{ display: 'none' }}
                    />
                    <div className="drop-content">
                        <Upload size={32} className="upload-icon" />
                        <div className="text-content">
                            <p className="main-text">Drag & drop or <span className="highlight">browse</span></p>
                            <p className="sub-text">PDF, DOCX, TXT, PPTX</p>
                        </div>
                    </div>
                </form>

                {files.length > 0 && (
                    <div className="file-list">
                        {files.map((file, index) => (
                            <div key={index} className="file-item">
                                <File size={16} className="file-icon" />
                                <span className="file-name">{file.name}</span>
                                <button onClick={(e) => { e.stopPropagation(); removeFile(index); }} className="remove-btn">
                                    <X size={14} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <div className="actions">
                    <button
                        className={`upload-btn ${files.length === 0 ? 'disabled' : ''}`}
                        onClick={handleUpload}
                        disabled={files.length === 0 || uploading}
                    >
                        {uploading ? (
                            <span className="loading-dots">Uploading...</span>
                        ) : uploadStatus === 'success' ? (
                            <><CheckCircle size={18} /> Uploaded</>
                        ) : (
                            <><Upload size={18} /> Upload Files</>
                        )}
                    </button>
                </div>

                {uploadedContext.length > 0 && (
                    <div className="uploaded-context-display">
                        <h3>Uploaded Context</h3>
                        <div className="context-pills">
                            {uploadedContext.map((file, idx) => (
                                <div key={idx} className="context-pill">
                                    <span className="pill-name">{file.filename}</span>
                                    <span className="pill-category">{file.category}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </motion.div>
        </div>
    );
};

export default UploadInterface;
