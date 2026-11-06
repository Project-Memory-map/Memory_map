(() => {
  const sidebar = document.getElementById("sidebar");

  document.getElementById("sidebar-toggle").addEventListener("click", () => {
    sidebar.classList.toggle("is-open");
  });

  MemoryMap.init("map");
})();
