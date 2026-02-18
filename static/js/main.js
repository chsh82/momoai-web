// MOMOAI v4.1.0 - Sidebar Toggle
  document.addEventListener('DOMContentLoaded', function() {
      const sidebar = document.getElementById('sidebar');
      const sidebarToggle = document.getElementById('sidebarToggle');
      const mainContent = document.getElementById('mainContent');

      if (sidebarToggle && sidebar) {
          sidebarToggle.addEventListener('click', function() {
              sidebar.classList.toggle('hidden');
              sidebar.classList.toggle('md:block');
              if (mainContent) {
                  mainContent.classList.toggle('md:ml-64');
              }
          });
      }
  });
