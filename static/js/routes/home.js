import { getJson, htmlEscape, renderIfChanged } from "../utils.js";

export async function init() {
  const classes = document.querySelector("#home-classes");
  const journal = document.querySelector("#home-journal");
  if (!classes || !journal) return;
  const data = await getJson("/api/home");
  const classRows = [...data.classes].reverse().map(item => `<div class="class-row"><span>${htmlEscape(item.day)} · ${htmlEscape(item.date)} · ${htmlEscape(item.time)}</span><strong>${htmlEscape(item.title)}</strong></div>`).join("");
  const classHtml = `<p class="eyebrow">This week at Still</p><h2>Practice for every season of life.</h2>${classRows}<a class="button button-light" href="/classes">View all classes <span>→</span></a>`;
  const posts = data.posts.map(post => `<div class="post-preview"><p>${htmlEscape(post.category)} · ${post.read_time_minutes} min read</p><h3>${htmlEscape(post.title)}</h3><a class="text-link" href="/blog">Read the journal →</a></div>`).join("");
  renderIfChanged(classes, classHtml);
  renderIfChanged(journal, `<div><p class="eyebrow">From the journal</p><h2>Small rituals.<br>Lasting change.</h2></div>${posts}`);
}
