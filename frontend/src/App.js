import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './App.css';
import Navbar from './components/Navbar';
import Home from './components/Home';
import MicSection from './components/MicSection';
import NonAutonomousSection from './components/NonAutonomousSection';
import PPTGenerator from './components/PPTGenerator';
import SmartNotebook from './components/SmartNotebook';

function App() {
  return (
    <Router>
      <div className="App">
        <Navbar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/autonomous" element={
            <div className="page-wrapper" style={{ paddingTop: '80px' }}>
              <MicSection />
            </div>
          } />
          <Route path="/non-autonomous" element={<NonAutonomousSection />} />
          <Route path="/ppt-generator" element={<div style={{ paddingTop: '80px' }}><PPTGenerator /></div>} />
          <Route path="/smart-notebook" element={<div style={{ paddingTop: '80px' }}><SmartNotebook /></div>} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
