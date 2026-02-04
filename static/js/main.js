(function () {
  'use strict';

  // ============================================
  // 3D CARD TILT EFFECT
  // ============================================
  function initCardTilt() {
    const cards = document.querySelectorAll('.card, .glass-card, .stats-card');
    
    cards.forEach(card => {
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = (y - centerY) / 20;
        const rotateY = (centerX - x) / 20;
        
        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(10px)`;
      });
      
      card.addEventListener('mouseleave', () => {
        card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateZ(0)';
        card.style.transition = 'transform 0.5s ease';
      });
      
      card.addEventListener('mouseenter', () => {
        card.style.transition = 'transform 0.1s ease';
      });
    });
  }

  // ============================================
  // FLOATING PARTICLES EFFECT
  // ============================================
  function createParticles() {
    const container = document.querySelector('.bg-animated');
    if (!container) return;
    
    const particleCount = 50;
    
    for (let i = 0; i < particleCount; i++) {
      const particle = document.createElement('div');
      particle.className = 'floating-particle';
      particle.style.cssText = `
        position: absolute;
        width: ${Math.random() * 4 + 2}px;
        height: ${Math.random() * 4 + 2}px;
        background: ${['#6366f1', '#ec4899', '#8b5cf6', '#06b6d4'][Math.floor(Math.random() * 4)]};
        border-radius: 50%;
        left: ${Math.random() * 100}%;
        top: ${Math.random() * 100}%;
        opacity: ${Math.random() * 0.5 + 0.2};
        animation: floatParticle ${Math.random() * 20 + 10}s linear infinite;
        animation-delay: ${Math.random() * -20}s;
        pointer-events: none;
        box-shadow: 0 0 ${Math.random() * 10 + 5}px currentColor;
      `;
      container.appendChild(particle);
    }
    
    // Add keyframes for particles
    if (!document.querySelector('#particle-keyframes')) {
      const style = document.createElement('style');
      style.id = 'particle-keyframes';
      style.textContent = `
        @keyframes floatParticle {
          0% {
            transform: translateY(100vh) rotate(0deg);
            opacity: 0;
          }
          10% {
            opacity: 0.5;
          }
          90% {
            opacity: 0.5;
          }
          100% {
            transform: translateY(-100vh) rotate(720deg);
            opacity: 0;
          }
        }
      `;
      document.head.appendChild(style);
    }
  }

  // ============================================
  // GLOWING CURSOR EFFECT
  // ============================================
  function initGlowingCursor() {
    const cursor = document.createElement('div');
    cursor.className = 'custom-cursor';
    cursor.style.cssText = `
      position: fixed;
      width: 20px;
      height: 20px;
      border: 2px solid rgba(99, 102, 241, 0.5);
      border-radius: 50%;
      pointer-events: none;
      z-index: 9999;
      transition: transform 0.1s ease, width 0.2s ease, height 0.2s ease, border-color 0.2s ease;
      transform: translate(-50%, -50%);
      mix-blend-mode: difference;
    `;
    document.body.appendChild(cursor);
    
    const cursorDot = document.createElement('div');
    cursorDot.className = 'cursor-dot';
    cursorDot.style.cssText = `
      position: fixed;
      width: 6px;
      height: 6px;
      background: #6366f1;
      border-radius: 50%;
      pointer-events: none;
      z-index: 9999;
      transform: translate(-50%, -50%);
      box-shadow: 0 0 10px #6366f1, 0 0 20px #6366f1;
    `;
    document.body.appendChild(cursorDot);
    
    document.addEventListener('mousemove', (e) => {
      cursor.style.left = e.clientX + 'px';
      cursor.style.top = e.clientY + 'px';
      cursorDot.style.left = e.clientX + 'px';
      cursorDot.style.top = e.clientY + 'px';
    });
    
    // Hover effects on interactive elements
    const interactiveElements = document.querySelectorAll('a, button, .btn, input, select, textarea, .nav-link, .card');
    interactiveElements.forEach(el => {
      el.addEventListener('mouseenter', () => {
        cursor.style.width = '40px';
        cursor.style.height = '40px';
        cursor.style.borderColor = 'rgba(236, 72, 153, 0.8)';
        cursorDot.style.transform = 'translate(-50%, -50%) scale(1.5)';
      });
      el.addEventListener('mouseleave', () => {
        cursor.style.width = '20px';
        cursor.style.height = '20px';
        cursor.style.borderColor = 'rgba(99, 102, 241, 0.5)';
        cursorDot.style.transform = 'translate(-50%, -50%) scale(1)';
      });
    });
  }

  // ============================================
  // SCROLL REVEAL ANIMATIONS
  // ============================================
  function initScrollReveal() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry, index) => {
        if (entry.isIntersecting) {
          entry.target.style.animationDelay = `${index * 0.1}s`;
          entry.target.classList.add('animate-slide-up');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    });
    
    document.querySelectorAll('.card, .table-responsive, .glass-card').forEach(el => {
      el.style.opacity = '0';
      observer.observe(el);
    });
  }

  // ============================================
  // RIPPLE EFFECT ON BUTTONS
  // ============================================
  function initRippleEffect() {
    document.querySelectorAll('.btn').forEach(button => {
      button.addEventListener('click', function(e) {
        const ripple = document.createElement('span');
        const rect = this.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;
        
        ripple.style.cssText = `
          position: absolute;
          width: ${size}px;
          height: ${size}px;
          left: ${x}px;
          top: ${y}px;
          background: rgba(255, 255, 255, 0.3);
          border-radius: 50%;
          transform: scale(0);
          animation: rippleEffect 0.6s ease-out;
          pointer-events: none;
        `;
        
        this.style.position = 'relative';
        this.style.overflow = 'hidden';
        this.appendChild(ripple);
        
        setTimeout(() => ripple.remove(), 600);
      });
    });
    
    // Add ripple keyframes
    if (!document.querySelector('#ripple-keyframes')) {
      const style = document.createElement('style');
      style.id = 'ripple-keyframes';
      style.textContent = `
        @keyframes rippleEffect {
          to {
            transform: scale(4);
            opacity: 0;
          }
        }
      `;
      document.head.appendChild(style);
    }
  }

  // ============================================
  // NUMBER COUNTER ANIMATION
  // ============================================
  function initCounterAnimation() {
    const counters = document.querySelectorAll('[data-count]');
    
    counters.forEach(counter => {
      const target = parseInt(counter.getAttribute('data-count'));
      const duration = 2000;
      const step = target / (duration / 16);
      let current = 0;
      
      const updateCounter = () => {
        current += step;
        if (current < target) {
          counter.textContent = Math.floor(current);
          requestAnimationFrame(updateCounter);
        } else {
          counter.textContent = target;
        }
      };
      
      const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          updateCounter();
          observer.unobserve(counter);
        }
      });
      
      observer.observe(counter);
    });
  }

  // ============================================
  // MAGNETIC BUTTON EFFECT
  // ============================================
  function initMagneticButtons() {
    document.querySelectorAll('.btn-primary, .btn-success').forEach(button => {
      button.addEventListener('mousemove', function(e) {
        const rect = this.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        
        this.style.transform = `translate(${x * 0.2}px, ${y * 0.2}px)`;
      });
      
      button.addEventListener('mouseleave', function() {
        this.style.transform = 'translate(0, 0)';
        this.style.transition = 'transform 0.3s ease';
      });
      
      button.addEventListener('mouseenter', function() {
        this.style.transition = 'transform 0.1s ease';
      });
    });
  }

  // ============================================
  // TYPEWRITER EFFECT FOR HEADINGS
  // ============================================
  function initTypewriter() {
    const elements = document.querySelectorAll('[data-typewriter]');
    
    elements.forEach(el => {
      const text = el.textContent;
      el.textContent = '';
      el.style.borderRight = '2px solid var(--primary)';
      el.style.animation = 'blink 0.7s infinite';
      
      let i = 0;
      const type = () => {
        if (i < text.length) {
          el.textContent += text.charAt(i);
          i++;
          setTimeout(type, 50);
        } else {
          el.style.borderRight = 'none';
          el.style.animation = 'none';
        }
      };
      
      const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          type();
          observer.unobserve(el);
        }
      });
      
      observer.observe(el);
    });
    
    // Add blink keyframes
    if (!document.querySelector('#blink-keyframes')) {
      const style = document.createElement('style');
      style.id = 'blink-keyframes';
      style.textContent = `
        @keyframes blink {
          0%, 50% { border-color: var(--primary); }
          51%, 100% { border-color: transparent; }
        }
      `;
      document.head.appendChild(style);
    }
  }

  // ============================================
  // FORM VALIDATION
  // ============================================
  function initFormValidation() {
    document.querySelectorAll('form[data-validate]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        var valid = true;
        form.querySelectorAll('[required]').forEach(function (el) {
          if (!el.value.trim()) {
            valid = false;
            el.classList.add('is-invalid');
            el.style.animation = 'shake 0.5s ease';
            setTimeout(() => el.style.animation = '', 500);
          } else {
            el.classList.remove('is-invalid');
          }
        });
        if (!valid) e.preventDefault();
      });
    });
    
    // Add shake animation
    if (!document.querySelector('#shake-keyframes')) {
      const style = document.createElement('style');
      style.id = 'shake-keyframes';
      style.textContent = `
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20%, 60% { transform: translateX(-10px); }
          40%, 80% { transform: translateX(10px); }
        }
      `;
      document.head.appendChild(style);
    }
  }

  // ============================================
  // AUTO-DISMISS ALERTS
  // ============================================
  function initAlertDismiss() {
    if (!document.querySelector('.login-page')) {
      setTimeout(function () {
        document.querySelectorAll('.alert-dismissible').forEach(function (a) {
          a.style.animation = 'slideOut 0.5s ease forwards';
          setTimeout(() => {
            try {
              var b = new bootstrap.Alert(a);
              b.close();
            } catch (e) {
              a.remove();
            }
          }, 500);
        });
      }, 5000);
    }
    
    // Add slideOut animation
    if (!document.querySelector('#slideout-keyframes')) {
      const style = document.createElement('style');
      style.id = 'slideout-keyframes';
      style.textContent = `
        @keyframes slideOut {
          to {
            opacity: 0;
            transform: translateX(100%);
          }
        }
      `;
      document.head.appendChild(style);
    }
  }

  // ============================================
  // CONFIRM DELETE
  // ============================================
  function initConfirmDelete() {
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (!confirm(el.getAttribute('data-confirm') || 'Are you sure?')) {
          e.preventDefault();
        }
      });
    });
  }

  // ============================================
  // SIDEBAR HOVER SOUND EFFECT (Visual)
  // ============================================
  function initSidebarEffects() {
    const navLinks = document.querySelectorAll('#sidebar .nav-link');
    
    navLinks.forEach(link => {
      link.addEventListener('mouseenter', () => {
        // Add a subtle flash effect
        link.style.boxShadow = '0 0 30px rgba(99, 102, 241, 0.5)';
        setTimeout(() => {
          link.style.boxShadow = '';
        }, 200);
      });
    });
  }

  // ============================================
  // TABLE ROW HOVER GLOW
  // ============================================
  function initTableEffects() {
    document.querySelectorAll('.table tbody tr').forEach(row => {
      row.addEventListener('mouseenter', () => {
        row.style.boxShadow = '0 0 20px rgba(99, 102, 241, 0.2)';
      });
      row.addEventListener('mouseleave', () => {
        row.style.boxShadow = '';
      });
    });
  }

  // ============================================
  // LOGIN FORM 3D TILT
  // ============================================
  function initLoginTilt() {
    const loginCard = document.querySelector('.login-card-3d');
    if (!loginCard) return;
    
    loginCard.addEventListener('mousemove', (e) => {
      const rect = loginCard.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = (y - centerY) / 30;
      const rotateY = (centerX - x) / 30;
      
      loginCard.style.animation = 'none';
      loginCard.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(20px)`;
    });
    
    loginCard.addEventListener('mouseleave', () => {
      loginCard.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateZ(0)';
      loginCard.style.transition = 'transform 0.5s ease';
      setTimeout(() => {
        loginCard.style.animation = 'cardFloat 6s ease-in-out infinite';
      }, 500);
    });
  }

  // ============================================
  // INITIALIZE ALL EFFECTS
  // ============================================
  function init() {
    initCardTilt();
    createParticles();
    // initGlowingCursor(); // Disabled by default - can enable if wanted
    initScrollReveal();
    initRippleEffect();
    initCounterAnimation();
    initMagneticButtons();
    // initTypewriter(); // Disabled by default - can enable if wanted
    initFormValidation();
    initAlertDismiss();
    initConfirmDelete();
    initSidebarEffects();
    initTableEffects();
    initLoginTilt();
    
    // Initialize AOS if available
    if (typeof AOS !== 'undefined') {
      AOS.init({
        duration: 800,
        once: true,
        easing: 'ease-out-cubic'
      });
    }
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
