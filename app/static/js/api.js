/* FoundRisk Edge — thin fetch wrapper. No framework, vanilla JS only. */

const Api = (() => {
    async function request(path, options = {}) {
        const opts = Object.assign({ headers: {} }, options);
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta && ["POST", "PATCH", "PUT", "DELETE"].includes((opts.method || "GET").toUpperCase())) {
            opts.headers["X-CSRFToken"] = csrfMeta.content;
        }
        if (opts.json) {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(opts.json);
            delete opts.json;
        }
        const res = await fetch(`/api${path}`, opts);
        let data = null;
        try { data = await res.json(); } catch (e) { /* no body */ }
        if (!res.ok) {
            const message = (data && data.message) ? data.message : `Request failed (${res.status})`;
            const err = new Error(message);
            err.status = res.status;
            err.data = data;
            throw err;
        }
        return data;
    }

    return {
        health: () => request("/health"),

        listProjects: () => request("/projects"),
        createProject: (name) => request("/projects", { method: "POST", json: { name } }),
        getProject: (id) => request(`/projects/${id}`),

        listDocuments: (projectId) => request(`/documents?project_id=${projectId}`),
        getDocument: (id) => request(`/documents/${id}`),
        uploadDocument: (projectId, file) => {
            const form = new FormData();
            form.append("project_id", projectId);
            form.append("file", file);
            return request("/documents", { method: "POST", body: form });
        },
        processDocument: (id) => request(`/documents/${id}/process`, { method: "POST" }),

        listEvidence: (projectId, params = {}) => {
            const qs = new URLSearchParams(Object.assign({ project_id: projectId }, params));
            return request(`/evidence?${qs.toString()}`);
        },
        getEvidence: (id) => request(`/evidence/${id}`),

        analysisSummary: (projectId) => request(`/analysis/summary?project_id=${projectId}`),
        analysisContradictions: (projectId) => request(`/analysis/contradictions?project_id=${projectId}`),
    };
})();


/* FoundRisk API CSRF bridge: all page-level fetch() calls get the current session token.
   If a tab was left open across sign-in/session rotation, refresh the token and retry once. */
(() => {
    const nativeFetch = window.fetch.bind(window);
    const writeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
    const csrfMeta = () => document.querySelector('meta[name="csrf-token"]');
    const isApiRequest = (input) => {
        try {
            const raw = typeof input === "string" || input instanceof URL ? String(input) : input.url;
            const url = new URL(raw, window.location.href);
            return url.origin === window.location.origin && url.pathname.startsWith("/api/");
        } catch (_) { return false; }
    };
    const methodOf = (input, init) => String((init && init.method) || (input && input.method) || "GET").toUpperCase();
    const withToken = (input, init, token) => {
        const next = Object.assign({}, init || {});
        const headers = new Headers((init && init.headers) || (input instanceof Request ? input.headers : undefined));
        if (token && writeMethods.has(methodOf(input, init))) headers.set("X-CSRFToken", token);
        next.headers = headers;
        if (!next.credentials) next.credentials = "same-origin";
        return next;
    };
    window.fetch = async (input, init) => {
        if (!isApiRequest(input)) return nativeFetch(input, init);
        const tokenMeta = csrfMeta();
        const token = tokenMeta ? tokenMeta.content : "";
        let response = await nativeFetch(input, withToken(input, init, token));
        if (!writeMethods.has(methodOf(input, init)) || response.status !== 400) return response;
        let payload = null;
        try { payload = await response.clone().json(); } catch (_) {}
        if (!payload || payload.error !== "csrf_failed") return response;
        try {
            const refresh = await nativeFetch("/api/auth/csrf-token", {
                method: "GET", credentials: "same-origin", cache: "no-store",
                headers: { "Accept": "application/json" }
            });
            if (!refresh.ok) return response;
            const refreshed = await refresh.json();
            if (!refreshed.csrf_token) return response;
            if (tokenMeta) tokenMeta.content = refreshed.csrf_token;
            response = await nativeFetch(input, withToken(input, init, refreshed.csrf_token));
        } catch (_) { /* Preserve the original API response if recovery itself fails. */ }
        return response;
    };
})();
