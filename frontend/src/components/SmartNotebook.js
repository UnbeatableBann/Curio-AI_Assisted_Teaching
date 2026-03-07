import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './SmartNotebook.css';

const SmartNotebook = () => {
    const [notes, setNotes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchNotes();
    }, []);

    const fetchNotes = async () => {
        try {
            const response = await fetch('http://localhost:8002/notebook/all');
            if (!response.ok) {
                throw new Error('Failed to fetch notebook data');
            }
            const data = await response.json();
            // data.notes contains the list according to our backend API response
            setNotes(data.notes || []);
            setLoading(false);
        } catch (err) {
            console.error("Error loading notes:", err);
            setError("Unable to load your smart notes. Please try again later.");
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="smart-notebook-container">
                <div className="loading-container">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4"></div>
                    <p>Loading your smart notebook...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="smart-notebook-container">
                <div className="error-container">
                    <svg className="w-16 h-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <p>{error}</p>
                    <button onClick={fetchNotes} className="retry-button">Try Again</button>
                </div>
            </div>
        );
    }

    return (
        <div className="smart-notebook-container">
            <div className="notebook-header">
                <h1>Smart Notebook</h1>
                <p className="notebook-description">Your AI-generated summaries and visual study guides.</p>
            </div>

            <div className="notebook-grid">
                {notes.length === 0 ? (
                    <div className="empty-state">
                        <p>No notes found yet. Start an autonomous session to generate some!</p>
                    </div>
                ) : (
                    notes.map((note, index) => (
                        <div key={index} className="note-card">
                            <div className="note-image-container">
                                {note.image ? (
                                    <img
                                        src={note.image.startsWith('http') || note.image.startsWith('data:') ? note.image : `data:image/png;base64,${note.image}`}
                                        alt={`${note.topic} Visual`}
                                        className="note-image"
                                    />
                                ) : (
                                    <div className="note-placeholder">
                                        <svg className="w-12 h-12 mb-2 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                        </svg>
                                        <span>No Visual Generated</span>
                                    </div>
                                )}
                            </div>

                            <div className="note-content">
                                <div className="note-meta">
                                    <span className="note-topic-badge">{note.topic || 'General'}</span>
                                </div>

                                <h3 className="note-title">{note.subtopic || 'Summary'}</h3>

                                <div className="note-body">
                                    <ReactMarkdown>{note.content}</ReactMarkdown>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default SmartNotebook;
