const tbody = document.getElementById("project-tbody");
const form = document.getElementById("project-form");
const openProjectModalBtn = document.getElementById("open-project-modal");
const projectModal = document.getElementById("project-modal");
const projectModalCloseBtn = document.getElementById("project-modal-close");

const modal = document.getElementById("modal");
const modalTitle = document.getElementById("modal-title");
const modalContent = document.getElementById("modal-content");
const modalActions = document.getElementById("modal-actions");
const modalCloseBtn = document.getElementById("modal-close");

function openModal(title, contentHtml, actions = []) {
  modalTitle.textContent = title;
  modalContent.innerHTML = contentHtml;
  modalActions.innerHTML = "";

  actions.forEach((action) => {
    const btn = document.createElement("button");
    btn.className = `btn ${action.className || "btn-secondary"}`;
    btn.textContent = action.text;
    btn.onclick = action.onClick;
    modalActions.appendChild(btn);
  });

  modal.classList.remove("hidden");
}

function closeModal() {
  modal.classList.add("hidden");
}

function openProjectModal() {
  projectModal.classList.remove("hidden");
}

function closeProjectModal() {
  projectModal.classList.add("hidden");
}

modalCloseBtn.addEventListener("click", closeModal);
modal.addEventListener("click", (event) => {
  if (event.target === modal) closeModal();
});

openProjectModalBtn.addEventListener("click", openProjectModal);
projectModalCloseBtn.addEventListener("click", closeProjectModal);
projectModal.addEventListener("click", (event) => {
  if (event.target === projectModal) closeProjectModal();
});

document.addEventListener("click", () => {
  document.querySelectorAll(".menu").forEach((m) => m.classList.remove("show"));
});

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw data;
  }
  return data;
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function actionButton(text, handler, className = "btn-secondary") {
  return `<button class="btn ${className}" data-action="${text}">${text}</button>`;
}

async function loadProjects() {
  const projects = await requestJson("/api/projects");
  tbody.innerHTML = "";

  projects.forEach((p) => {
    const tr = document.createElement("tr");
    tr.dataset.id = p.id;
    tr.innerHTML = `
      <td>${p.id}</td>
      <td>${escapeHtml(p.name)}</td>
      <td>${escapeHtml(p.repo_url)}</td>
      <td><pre>${escapeHtml(p.build_script || "")}</pre></td>
      <td>${escapeHtml(p.repo_local_path)}</td>
      <td>
        <div class="actions">
          ${actionButton("同步")}
          ${actionButton("构建")}
          <div class="menu-wrap">
            ${actionButton("...", null, "btn-ghost")}
            <div class="menu">
              ${actionButton("修改", null, "btn-secondary")}
              ${actionButton("删除", null, "btn-danger")}
            </div>
          </div>
        </div>
      </td>
    `;

    const buttons = tr.querySelectorAll("button[data-action]");
    buttons[0].onclick = () => onSync(p.id);
    buttons[1].onclick = () => onBuild(p.id);

    const dotBtn = buttons[2];
    const menu = tr.querySelector(".menu");
    dotBtn.onclick = (event) => {
      event.stopPropagation();
      menu.classList.toggle("show");
    };

    const editBtn = buttons[3];
    const deleteBtn = buttons[4];
    editBtn.onclick = () => onEdit(p);
    deleteBtn.onclick = () => onDelete(p);

    tbody.appendChild(tr);
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());

  closeProjectModal();
  openModal("创建中", "<p>正在创建工程并执行 clone，请稍候...</p>");

  try {
    const data = await requestJson("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    openModal("创建完成", `<p>${escapeHtml(data.message)}</p><pre>${escapeHtml(data.output || "")}</pre>`);
    form.reset();
    await loadProjects();
  } catch (err) {
    openModal("创建失败", `<p>${escapeHtml(err.message || "操作失败")}</p><pre>${escapeHtml(err.output || "")}</pre>`);
  }
});

async function onSync(projectId) {
  openModal("同步中", "<p>正在同步远程仓库...</p>");
  try {
    const data = await requestJson(`/api/projects/${projectId}/sync`, { method: "POST" });
    openModal(data.ok ? "同步成功" : "同步失败", `<p>${escapeHtml(data.message)}</p><pre>${escapeHtml(data.output || "")}</pre>`);
  } catch (err) {
    openModal("同步失败", `<p>${escapeHtml(err.message || "请求失败")}</p>`);
  }
}

async function onBuild(projectId) {
  openModal("构建中", "<p>正在执行构建，请稍候...</p>");
  try {
    const data = await requestJson(`/api/projects/${projectId}/build`, { method: "POST" });
    openModal(data.ok ? "构建成功" : "构建失败", `
      <p>${escapeHtml(data.message)}</p>
      <p><strong>构建产出目录：</strong> ${escapeHtml(data.output_dir || "-")}</p>
      <pre>${escapeHtml(data.output || "")}</pre>
    `);
  } catch (err) {
    openModal("构建失败", `<p>${escapeHtml(err.message || "请求失败")}</p><pre>${escapeHtml(err.output || "")}</pre>`);
  }
}

function onEdit(project) {
  openModal(
    "修改仓库配置",
    `
      <p>允许修改远程仓库地址、用户名、密码/Token、构建脚本。</p>
      <label>远程仓库地址<input id="edit-repo-url" value="${escapeHtml(project.repo_url)}" /></label>
      <label>用户名<input id="edit-username" value="${escapeHtml(project.git_username)}" /></label>
      <label>密码/Token<input id="edit-token" type="password" value="${escapeHtml(project.git_token)}" /></label>
      <label>构建脚本<textarea id="edit-build-script" rows="5">${escapeHtml(project.build_script || "")}</textarea></label>
    `,
    [
      {
        text: "保存",
        className: "btn-primary",
        onClick: async () => {
          const payload = {
            repo_url: document.getElementById("edit-repo-url")?.value?.trim(),
            git_username: document.getElementById("edit-username")?.value?.trim(),
            git_token: document.getElementById("edit-token")?.value?.trim(),
            build_script: document.getElementById("edit-build-script")?.value,
          };
          try {
            const result = await requestJson(`/api/projects/${project.id}/credentials`, {
              method: "PUT",
              body: JSON.stringify(payload),
            });
            openModal("修改成功", `<p>${escapeHtml(result.message)}</p>`);
            await loadProjects();
          } catch (err) {
            openModal("修改失败", `<p>${escapeHtml(err.message || "请求失败")}</p>`);
          }
        },
      },
    ]
  );
}

function onDelete(project) {
  openModal(
    "删除工程",
    `<p>确认删除工程 <strong>${escapeHtml(project.name)}</strong> 及其所有相关数据和记录吗？</p>`,
    [
      {
        text: "确认删除",
        className: "btn-danger",
        onClick: async () => {
          try {
            const result = await requestJson(`/api/projects/${project.id}`, { method: "DELETE" });
            openModal("删除成功", `<p>${escapeHtml(result.message)}</p>`);
            await loadProjects();
          } catch (err) {
            openModal("删除失败", `<p>${escapeHtml(err.message || "请求失败")}</p>`);
          }
        },
      },
    ]
  );
}

loadProjects().catch((err) => {
  openModal("初始化失败", `<p>${escapeHtml(err.message || "加载数据失败")}</p>`);
});
