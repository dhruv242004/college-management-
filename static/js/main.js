(function () {
  'use strict';

  // ============================================
  // FORM VALIDATION
  // ============================================
  function initFormValidation() {
    document.querySelectorAll('form[data-validate]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        let valid = true;
        form.querySelectorAll('[required]').forEach(function (el) {
          if (!el.value.trim()) {
            valid = false;
            el.classList.add('is-invalid');
          } else {
            el.classList.remove('is-invalid');
          }
        });
        if (!valid) {
          e.preventDefault();
          // Simple shake effect without heavy CSS dependency
          form.style.transform = 'translateX(-5px)';
          setTimeout(() => form.style.transform = 'translateX(5px)', 100);
          setTimeout(() => form.style.transform = 'translateX(0)', 200);
        }
      });
    });
  }

  // ============================================
  // AUTO-DISMISS ALERTS
  // ============================================
  function initAlertDismiss() {
    // Only dismiss if NOT on login page
    if (!document.querySelector('.auth-page')) {
      setTimeout(function () {
        document.querySelectorAll('.alert-dismissible').forEach(function (a) {
          a.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
          a.style.opacity = '0';
          a.style.transform = 'translateX(20px)';
          setTimeout(() => {
            try {
              let b = new bootstrap.Alert(a);
              b.close();
            } catch (e) {
              a.remove();
            }
          }, 500);
        });
      }, 5000);
    }
  }

  // ============================================
  // CONFIRM DELETE
  // ============================================
  function initConfirmDelete() {
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (!confirm(el.getAttribute('data-confirm') || 'Are you sure you want to delete this item?')) {
          e.preventDefault();
        }
      });
    });
  }

  // ============================================
  // INITIALIZE ALL FUNCTIONALITIES
  // ============================================
  function init() {
    // All visual "reveals", "particles", and "tilts" have been removed 
    // to ensure 100% content visibility and UI stability.
    initFormValidation();
    initAlertDismiss();
    initConfirmDelete();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
