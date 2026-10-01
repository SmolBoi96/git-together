// Reorderable rebase-todo list: drag, arrow buttons, or vim keys.
(function () {
  const list = document.getElementById("todo");
  const form = document.getElementById("rank-form");
  if (!list) return;

  const lines = () => Array.from(list.children);

  function renumber() {
    lines().forEach((li, i) => {
      li.querySelector(".hash").textContent = "#" + (i + 1);
    });
  }

  function move(li, dir) {
    if (dir < 0 && li.previousElementSibling) {
      list.insertBefore(li, li.previousElementSibling);
    } else if (dir > 0 && li.nextElementSibling) {
      list.insertBefore(li.nextElementSibling, li);
    }
    renumber();
    li.focus();
  }

  list.addEventListener("click", (e) => {
    const btn = e.target.closest(".mv");
    if (btn) move(btn.closest("li"), Number(btn.dataset.dir));
  });

  // Drag and drop.
  let dragging = null;
  list.addEventListener("dragstart", (e) => {
    dragging = e.target.closest("li");
    dragging.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
  });
  list.addEventListener("dragend", () => {
    if (dragging) dragging.classList.remove("dragging");
    dragging = null;
    renumber();
  });
  list.addEventListener("dragover", (e) => {
    if (!dragging) return;
    e.preventDefault();
    const over = e.target.closest("li");
    if (!over || over === dragging) return;
    const rect = over.getBoundingClientRect();
    const after = e.clientY > rect.top + rect.height / 2;
    list.insertBefore(dragging, after ? over.nextSibling : over);
  });

  // Vim keys: j/k move the cursor, J/K move the line, ":wq" + Enter saves.
  let cmd = null;
  const cmdline = document.createElement("div");
  cmdline.className = "cmdline";
  form.appendChild(cmdline);

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.matches("input, select, textarea")) return;

    if (cmd !== null) {
      if (e.key === "Enter") {
        if (cmd === "wq" || cmd === "w" || cmd === "x") form.requestSubmit();
        cmd = null;
      } else if (e.key === "Escape") {
        cmd = null;
      } else if (e.key === "Backspace") {
        cmd = cmd.length ? cmd.slice(0, -1) : null;
      } else if (e.key.length === 1) {
        cmd += e.key;
      }
      cmdline.textContent = cmd === null ? "" : ":" + cmd;
      e.preventDefault();
      return;
    }
    if (e.key === ":") {
      cmd = "";
      cmdline.textContent = ":";
      e.preventDefault();
      return;
    }

    const current = document.activeElement.closest && document.activeElement.closest(".todo-line");
    const all = lines();
    const idx = current ? all.indexOf(current) : -1;

    if (e.key === "j" || e.key === "ArrowDown" && !e.shiftKey) {
      (all[Math.min(idx + 1, all.length - 1)] || all[0]).focus();
    } else if (e.key === "k" || e.key === "ArrowUp" && !e.shiftKey) {
      (all[Math.max(idx - 1, 0)] || all[0]).focus();
    } else if (current && (e.key === "J" || e.key === "ArrowDown" && e.shiftKey)) {
      move(current, 1);
    } else if (current && (e.key === "K" || e.key === "ArrowUp" && e.shiftKey)) {
      move(current, -1);
    } else if (e.key === "g") {
      all[0].focus();
    } else if (e.key === "G") {
      all[all.length - 1].focus();
    } else {
      return;
    }
    e.preventDefault();
  });
})();
