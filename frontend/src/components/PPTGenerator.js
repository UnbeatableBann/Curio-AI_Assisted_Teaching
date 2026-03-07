import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Download, RefreshCw, Sparkles } from 'lucide-react';
import './PPTGenerator.css';

const PPTGenerator = () => {
    const navigate = useNavigate();
    const [topic, setTopic] = useState('');
    const [stage, setStage] = useState('topic'); // 'topic' | 'generated'
    const [loading, setLoading] = useState(false);
    const [generatedSlides, setGeneratedSlides] = useState([]);
    const [pptxFilename, setPptxFilename] = useState('');
    const [error, setError] = useState('');

    const handleGenerate = async () => {
        if (!topic.trim()) return;
        setLoading(true);
        setError('');

        try {
            const response = await fetch('http://localhost:8000/api/generate-ppt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ topic }),
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Generation failed');
            }

            const data = await response.json();

            // Handle the case where slides might be wrapped or just a list
            let slides = data.slides;
            if (data.slides && data.slides.slides) {
                slides = data.slides.slides;
            }

            setGeneratedSlides(slides || []);
            setPptxFilename(data.pptx_filename);
            setStage('generated');
        } catch (err) {
            console.error(err);
            setError('Failed to generate slides. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = () => {
        if (!pptxFilename) return;
        window.location.href = `http://localhost:8000/api/download-ppt/${pptxFilename}`;
    };

    const reset = () => {
        setTopic('');
        setStage('topic');
        setGeneratedSlides([]);
        setPptxFilename('');
        setError('');
    };

    return (
        <div className="ppt-generator-container">
            <div className="ppt-header">
                <button className="back-btn" onClick={() => navigate('/non-autonomous')}>
                    <ArrowLeft size={20} /> Back
                </button>
                <div className="ppt-logo">
                    <Sparkles size={20} className="logo-icon" />
                    <span>CurioSlides</span>
                </div>
            </div>

            <main className="ppt-main">
                {stage === 'topic' && (
                    <section className="ppt-card topic-card">
                        <h1 className="ppt-title">Create AI Presentations</h1>
                        <p className="ppt-subtitle">Refine the topic to guide the AI generation from your uploaded context.</p>

                        <div className="input-group">
                            <input
                                type="text"
                                value={topic}
                                onChange={(e) => setTopic(e.target.value)}
                                placeholder="Enter presentation topic..."
                                className="ppt-input"
                                onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                            />
                        </div>

                        {error && <div className="error-msg">{error}</div>}

                        <div className="actions">
                            <button
                                className="btn btn-primary"
                                onClick={handleGenerate}
                                disabled={!topic || loading}
                            >
                                {loading ? (
                                    <>
                                        <span className="loader"></span> Generating...
                                    </>
                                ) : (
                                    <>
                                        <Sparkles size={18} /> Generate Slides
                                    </>
                                )}
                            </button>
                        </div>

                        {loading && (
                            <div className="loading-status">
                                <p>Generating content & visuals...</p>
                                <p className="small">This usually takes about 30-60 seconds.</p>
                            </div>
                        )}
                    </section>
                )}

                {stage === 'generated' && (
                    <section className="results-view">
                        <div className="results-header">
                            <h2 className="section-title">Your Presentation is Ready!</h2>
                            <div className="actions-group">
                                <button className="btn btn-secondary" onClick={reset}>
                                    <RefreshCw size={18} /> Create New
                                </button>
                                <button className="btn btn-primary" onClick={handleDownload}>
                                    <Download size={18} /> Download PPTX
                                </button>
                            </div>
                        </div>

                        <div className="slides-grid">
                            {generatedSlides.map((slide, index) => (
                                <div key={index} className="slide-card">
                                    <div className="slide-number">{index + 1}</div>
                                    <div className="slide-content">
                                        <h3>{slide.title}</h3>
                                        {Array.isArray(slide.content) ? (
                                            <ul>
                                                {slide.content.map((point, i) => (
                                                    <li key={i}>{point}</li>
                                                ))}
                                            </ul>
                                        ) : (
                                            <p>{slide.content}</p>
                                        )}

                                        {slide.visual_description && (
                                            <div className="visual-hint">
                                                <strong>Visual Idea:</strong> {slide.visual_description}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </section>
                )}
            </main>

            <div className="ppt-background-glow"></div>
        </div>
    );
};

export default PPTGenerator;
