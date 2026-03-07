import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Mic, Grid } from 'lucide-react';
import './Home.css';

const Home = () => {
    const navigate = useNavigate();

    return (
        <div className="home-container">
            <div className="home-content">
                <div className="header-section">
                    <h1 className="main-title">Curio AI Co-Teacher</h1>
                    <p className="subtitle">Choose your learning experience</p>
                </div>

                <div className="cards-container">
                    <div
                        className="option-card autonomous"
                        onClick={() => navigate('/autonomous')}
                    >
                        <div className="card-icon">
                            <Mic size={48} />
                        </div>
                        <h2>Co-Teacher</h2>
                        <p>Hands-free, voice-driven AI tutoring.</p>
                    </div>

                    <div
                        className="option-card non-autonomous"
                        onClick={() => navigate('/non-autonomous')}
                    >
                        <div className="card-icon">
                            <Grid size={48} />
                        </div>
                        <h2>Preparation Kit</h2>
                        <p>Interactive tools and file uploads.</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Home;
