const apiCache = new Map();
let sessionPromise;

export async function getJson(url) {
  if (!apiCache.has(url)) {
    apiCache.set(url, fetch(url).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Content is unavailable.");
      return data;
    }));
  }
  return apiCache.get(url);
}

export async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Something went wrong.");
  apiCache.clear();
  sessionPromise = undefined;
  return data;
}

export function getSession() {
  if (!sessionPromise) sessionPromise = getJson("/api/auth/me");
  return sessionPromise;
}

export function htmlEscape(value) {
  return String(value || "").replace(/[&<>"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
}

export function renderIfChanged(element, html) {
  if (element && element.innerHTML !== html) element.innerHTML = html;
}

export function formValues(form) {
  return Object.fromEntries(new FormData(form).entries());
}

export function initLazyBackgrounds(root = document) {
  const elements = [...root.querySelectorAll("[data-bg]")].filter(element => !element.dataset.loaded);
  const load = element => {
    element.style.backgroundImage = `url("${element.dataset.bg}")`;
    element.dataset.loaded = "true";
  };
  if (!("IntersectionObserver" in window)) {
    elements.forEach(load);
    return;
  }
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    load(entry.target);
    observer.unobserve(entry.target);
  }), { rootMargin: "300px" });
  elements.forEach(element => observer.observe(element));
}
