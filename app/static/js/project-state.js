/* FoundRisk Edge — shared project selection state (localStorage-backed). */

const ProjectState = (() => {
    const STORAGE_KEY = "foundrisk_active_project_id";

    function get() {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? parseInt(raw, 10) : null;
    }

    function set(id) {
        localStorage.setItem(STORAGE_KEY, String(id));
    }

    async function ensureAndPopulateSelector(selectEl, onChange) {
        let { projects } = await Api.listProjects();

        if (projects.length === 0) {
            const created = await Api.createProject("Untitled Startup Analysis");
            projects = [created.project];
        }

        let activeId = get();
        if (!activeId || !projects.some(p => p.id === activeId)) {
            activeId = projects[0].id;
            set(activeId);
        }

        selectEl.innerHTML = "";
        projects.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p.id;
            opt.textContent = p.name;
            if (p.id === activeId) opt.selected = true;
            selectEl.appendChild(opt);
        });

        selectEl.addEventListener("change", () => {
            set(parseInt(selectEl.value, 10));
            if (onChange) onChange(parseInt(selectEl.value, 10));
        });

        return activeId;
    }

    return { get, set, ensureAndPopulateSelector };
})();
