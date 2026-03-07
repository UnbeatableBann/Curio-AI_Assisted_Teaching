import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import './Navbar.css';

const Navbar = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleNavigation = (path) => {
    navigate(path);
    setIsMobileMenuOpen(false);
  };

  return (
    <nav className={`navbar ${isScrolled ? 'scrolled' : ''}`}>
      <div className="navbar-container">
        <div className="navbar-brand" onClick={() => handleNavigation('/')}>
          <span className="brand-logo">Curio AI</span>
          <span className="brand-subtitle">Co-Teacher</span>
        </div>

        {/* Desktop Menu */}
        <ul className="navbar-menu">
          <li>
            <button
              onClick={() => handleNavigation('/')}
              className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
            >
              Home
            </button>
          </li>
          <li>
            <button
              onClick={() => handleNavigation('/autonomous')}
              className={`nav-link ${location.pathname === '/autonomous' ? 'active' : ''}`}
            >
              Co-Teacher
            </button>
          </li>
          <li>
            <button
              onClick={() => handleNavigation('/non-autonomous')}
              className={`nav-link ${location.pathname === '/non-autonomous' ? 'active' : ''}`}
            >
              Preparation Kit
            </button>
          </li>
        </ul>

        {/* Mobile Menu Button */}
        <button
          className={`mobile-menu-toggle ${isMobileMenuOpen ? 'active' : ''}`}
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          aria-label="Toggle menu"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>
      </div>

      {/* Mobile Menu */}
      <div className={`mobile-menu ${isMobileMenuOpen ? 'open' : ''}`}>
        <button onClick={() => handleNavigation('/')} className="mobile-nav-link">
          Home
        </button>
        <button onClick={() => handleNavigation('/autonomous')} className="mobile-nav-link">
          Co-Teacher
        </button>
        <button onClick={() => handleNavigation('/non-autonomous')} className="mobile-nav-link">
          Preparation Kit
        </button>
      </div>
    </nav>
  );
};

export default Navbar;
