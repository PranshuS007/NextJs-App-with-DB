import { formValues, getSession, postJson } from "../utils.js";

function formMessage(form) {
  return form.querySelector(".form-message") || form.parentElement.querySelector(".form-message");
}

function bindAuthForm(selector, url, loadingText) {
  const form = document.querySelector(selector);
  if (!form) return;
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const message = formMessage(form);
    if (message) message.textContent = loadingText;
    try {
      await postJson(url, formValues(form));
      location.href = "/dashboard";
    } catch (error) {
      if (message) message.textContent = error.message;
    }
  });
}

async function bindForgotPassword() {
  const form = document.querySelector("#forgot-form");
  if (!form) return;
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const message = formMessage(form);
    if (message) message.textContent = "Preparing reset link...";
    try {
      const data = await postJson("/api/auth/forgot-password", formValues(form));
      if (message) message.innerHTML = data.reset_url ? `${data.message} <a href="${data.reset_url}">Reset password</a>` : data.message;
    } catch (error) {
      if (message) message.textContent = error.message;
    }
  });
}

function bindResetPassword() {
  const form = document.querySelector("#reset-form");
  if (!form) return;
  const token = new URLSearchParams(location.search).get("token");
  form.style.display = token ? "block" : "none";
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const message = formMessage(form);
    if (message) message.textContent = "Updating password...";
    try {
      const data = await postJson("/api/auth/reset-password", { token, password: form.password.value });
      if (message) message.textContent = data.message;
      form.reset();
    } catch (error) {
      if (message) message.textContent = error.message;
    }
  });
}

function bindLogout() {
  const button = document.querySelector("#logout-button");
  if (!button) return;
  button.addEventListener("click", async () => {
    await postJson("/api/auth/logout", {});
    location.href = "/";
  });
}

async function loadMemberGreeting() {
  const greeting = document.querySelector("#member-greeting");
  if (!greeting) return;
  const data = await getSession();
  if (!data.user) location.href = "/login";
  else greeting.textContent = `Welcome back, ${data.user.email}. Settle in with a simple sequence, breath practice, or reserve your next class.`;
}

export async function init() {
  bindAuthForm("#login-form", "/api/auth/login", "Logging in...");
  bindAuthForm("#register-form", "/api/auth/register", "Creating your account...");
  await bindForgotPassword();
  bindResetPassword();
  bindLogout();
  await loadMemberGreeting();
}
