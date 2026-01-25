(function () {
  'use strict';

  // Form validation
  document.querySelectorAll('form[data-validate]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      var valid = true;
      form.querySelectorAll('[required]').forEach(function (el) {
        if (!el.value.trim()) {
          valid = false;
          el.classList.add('is-invalid');
        } else {
          el.classList.remove('is-invalid');
        }
      });
      if (!valid) e.preventDefault();
    });
  });

  // Auto-dismiss alerts (skip on login page so user can read errors)
  if (!document.body.classList.contains('login-page')) {
    setTimeout(function () {
      document.querySelectorAll('.alert-dismissible').forEach(function (a) {
        try {
          var b = new bootstrap.Alert(a);
          b.close();
        } catch (e) {}
      });
    }, 5000);
  }

  // Confirm delete
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (!confirm(el.getAttribute('data-confirm') || 'Are you sure?')) {
        e.preventDefault();
      }
    });
  });
})();
