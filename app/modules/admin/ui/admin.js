(async () => {
  const user = await AccountMenu.ready;
  if (!user || user.role !== "admin") {
    window.location.href = "/";
    return;
  }

  const page = document.querySelector(".admin-page");
  const tabs = document.querySelectorAll(".admin-tab");
  const panels = document.querySelectorAll(".admin-panel");

  function showTab(name) {
    tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === name));
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.panel !== name;
    });
  }

  tabs.forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));
  page.hidden = false;
})();
