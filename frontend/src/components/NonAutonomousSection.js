import React from 'react';
import { useNavigate } from 'react-router-dom';
import UploadInterface from './UploadInterface';
import './NonAutonomousSection.css';

const NonAutonomousSection = () => {
  const navigate = useNavigate();

  const handlePPTGenerator = () => {
    navigate('/ppt-generator');
  };

  const handleBrainstorm = () => {
    alert('Brainstorm feature coming soon!');
  };


  return (
    <section className="non-autonomous-section">
      <div className="section-container">
        <h2 className="section-title">Non Autonomous</h2>
        <p className="section-description">
          Upload your documents and explore our AI-powered tools
        </p>

        <div className="content-wrapper">
          <UploadInterface />

          <div className="tools-divider">
            <span>Available Tools</span>
          </div>

          <div className="tools-grid">
            <div className="tool-card" onClick={handlePPTGenerator}>
              <div className="tool-icon">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M14 2V8H20"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M16 13H8"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M16 17H8"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M10 9H9H8"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <h3 className="tool-title">PPT Generator</h3>
              <p className="tool-description">
                Generate professional presentations with AI assistance
              </p>
            </div>

            <div className="tool-card" onClick={handleBrainstorm}>
              <div className="tool-icon">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M12 2L2 7L12 12L22 7L12 2Z"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M2 17L12 22L22 17"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M2 12L12 17L22 12"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <h3 className="tool-title">Brainstorm</h3>
              <p className="tool-description">
                Collaborative idea generation and creative thinking
              </p>
            </div>

            <div className="tool-card" onClick={() => navigate('/smart-notebook')}>
              <div className="tool-icon">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <h3 className="tool-title">Smart Notebook</h3>
              <p className="tool-description">
                View your AI-generated summaries and visual notes
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default NonAutonomousSection;
