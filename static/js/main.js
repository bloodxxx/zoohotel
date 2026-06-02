/* ZooHotel — JS */

document.addEventListener('DOMContentLoaded', () => {

  // Confirm dialogs
  document.querySelectorAll('[data-confirm]').forEach(btn => {
    btn.addEventListener('click', e => {
      if (!confirm(btn.dataset.confirm)) e.preventDefault();
    });
  });

  // Mobile sidebar toggle
  const toggler = document.getElementById('sidebar-toggler');
  const sidebar = document.getElementById('sidebar');
  if (toggler && sidebar) {
    toggler.addEventListener('click', () => sidebar.classList.toggle('open'));
  }

  // Auto-dismiss alerts
  setTimeout(() => {
    document.querySelectorAll('.alert-auto').forEach(el => {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    });
  }, 4000);
});
