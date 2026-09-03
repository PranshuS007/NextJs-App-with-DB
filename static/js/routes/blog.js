import { formValues, getJson, htmlEscape, initLazyBackgrounds, postJson, renderIfChanged } from "../utils.js";

const imageUrls = {
  "blog-one": "https://images.unsplash.com/photo-1591228127791-8e2eaef098d3?auto=format&fit=crop&w=900&q=70&fm=webp",
  "blog-two": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=900&q=70&fm=webp",
  "blog-three": "https://images.unsplash.com/photo-1545389336-cf090694435e?auto=format&fit=crop&w=900&q=70&fm=webp"
};

function articleHtml(post) {
  const paragraphs = htmlEscape(post.body).split("\n\n").map(paragraph => `<p>${paragraph}</p>`).join("");
  return `<p class="eyebrow">${htmlEscape(post.category)} · ${post.read_time_minutes} min read</p><h2>${htmlEscape(post.title)}</h2><p>${htmlEscape(post.excerpt)}</p><button class="text-link article-toggle" aria-expanded="false">Read article →</button><div class="article-body">${paragraphs}</div>`;
}

function attachArticleToggles(root) {
  root.onclick = event => {
    const button = event.target.closest(".article-toggle");
    if (!button) return;
    const article = button.nextElementSibling;
    if (!article) return;
    const open = article.classList.toggle("open");
    button.textContent = open ? "Close article ↑" : "Read article →";
    button.setAttribute("aria-expanded", String(open));
  };
}

function imageDiv(post) {
  return `<div class="blog-image" data-bg="${imageUrls[post.image_class] || imageUrls["blog-one"]}"></div>`;
}

async function initNewsletter() {
  const newsletter = document.querySelector("#newsletter-form");
  if (!newsletter) return;
  newsletter.addEventListener("submit", async event => {
    event.preventDefault();
    const message = newsletter.querySelector(".form-message");
    if (message) message.textContent = "Saving...";
    try {
      const data = await postJson("/api/newsletter", { email: formValues(newsletter).email || newsletter.querySelector("input[type='email']").value });
      if (message) message.textContent = data.message || "You are subscribed.";
      newsletter.reset();
    } catch (error) {
      if (message) message.textContent = error.message || "Unable to subscribe.";
    }
  });
}

export async function init() {
  const featuredPost = document.querySelector("#featured-post");
  const blogGrid = document.querySelector("#blog-grid");
  if (!featuredPost || !blogGrid) return;
  const { posts } = await getJson("/api/blog");
  const [featured, ...rest] = posts;
  renderIfChanged(featuredPost, featured ? `${imageDiv(featured)}<article>${articleHtml(featured)}</article>` : "");
  renderIfChanged(blogGrid, rest.map(post => `<article>${imageDiv(post)}${articleHtml(post)}</article>`).join(""));
  attachArticleToggles(document.querySelector("main"));
  initLazyBackgrounds(document);
  await initNewsletter();
}
