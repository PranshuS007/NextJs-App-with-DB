import { initLazyBackgrounds } from "./utils.js";

const page = document.body.dataset.page;
const header = document.querySelector("#site-header");
const footer = document.querySelector("#site-footer");
const links = [["home", "/", "Home"], ["about", "/about", "About"], ["classes", "/classes", "Classes"], ["blog", "/blog", "Blog"], ["contact", "/contact", "Contact"], ["dashboard", "/dashboard", "Members"]];
const routeModules = {
  home: () => import("./routes/home.js"),
  classes: () => import("./routes/classes.js"),
  blog: () => import("./routes/blog.js"),
  contact: () => import("./routes/contact.js"),
  login: () => import("./routes/auth.js"),
  register: () => import("./routes/auth.js"),
  forgot: () => import("./routes/auth.js"),
  dashboard: () => import("./routes/auth.js")
};

if (header) header.innerHTML = `<header class="site-header"><a class="logo" href="/">still<i>.</i></a><button class="menu-button" aria-label="Open menu" aria-expanded="false">☰</button><nav class="nav">${links.map(([key, href, label]) => `<a class="${page === key ? "active" : ""}" href="${href}">${label}</a>`).join("")}<a class="nav-cta" href="/classes">Book a class</a></nav></header>`;
if (footer) footer.innerHTML = `<footer class="site-footer"><a class="logo" href="/">still<i>.</i></a><div><p>Mindful movement.<br>Meaningful connection.</p></div><div><p>1428 SE Division Street<br>Portland, OR 97202</p></div><div><a href="mailto:hello@stillstudio.com">hello@stillstudio.com</a><br><a href="tel:+15035550142">(503) 555-0142</a></div><small>© ${new Date().getFullYear()} Still Studio</small></footer>`;

const menuButton = document.querySelector(".menu-button");
const nav = document.querySelector(".nav");
if (menuButton && nav) menuButton.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(open));
});

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    entry.target.classList.add("visible");
    observer.unobserve(entry.target);
  }), { threshold: .12 });
  document.querySelectorAll(".reveal").forEach(element => observer.observe(element));
} else {
  document.querySelectorAll(".reveal").forEach(element => element.classList.add("visible"));
}

initLazyBackgrounds(document);

const paymentMessage = document.querySelector("#payment-message");
const paymentParams = new URLSearchParams(location.search);
if (paymentParams.has("success") && paymentMessage) paymentMessage.textContent = "Thank you. Your class reservation payment was received.";
if (paymentParams.has("cancelled") && paymentMessage) paymentMessage.textContent = "Checkout was cancelled. Your place has not been reserved.";

if (routeModules[page]) {
  routeModules[page]().then(module => module.init()).catch(error => console.error(error));
}
