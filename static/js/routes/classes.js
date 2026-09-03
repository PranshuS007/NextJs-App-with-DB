import { getJson, getSession, htmlEscape, postJson, renderIfChanged } from "../utils.js";

function messageNode() {
  return document.querySelector("#booking-message") || document.querySelector("#payment-message");
}

async function reserve(button) {
  const message = messageNode();
  const original = button.innerHTML;
  try {
    const session = await getSession();
    if (!session.user) {
      if (message) message.innerHTML = 'Please <a href="/login">log in</a> or <a href="/register">create an account</a> to reserve a class.';
      return;
    }
    button.disabled = true;
    button.textContent = "Reserving...";
    const data = await postJson("/api/bookings", { occurrence_id: Number(button.dataset.occurrence) });
    if (message) message.textContent = data.booking.status === "confirmed" ? "Your spot is confirmed. A confirmation email has been queued." : `Class is full. You are waitlisted at position ${data.booking.waitlist_position}.`;
    await init();
  } catch (error) {
    if (message) message.textContent = error.message || "Unable to reserve this class.";
    button.disabled = false;
    button.innerHTML = original;
  }
}

async function checkout(button) {
  const paymentMessage = document.querySelector("#payment-message");
  const original = button.innerHTML;
  try {
    const session = await getSession();
    if (!session.user) {
      if (paymentMessage) paymentMessage.innerHTML = 'Please <a href="/login">log in</a> or <a href="/register">create an account</a> to reserve a class.';
      return;
    }
    button.disabled = true;
    button.textContent = "Opening checkout...";
    if (paymentMessage) paymentMessage.textContent = "";
    const data = await postJson("/api/checkout", { plan: button.dataset.plan });
    if (!data.url) throw new Error("Checkout is unavailable.");
    location.href = data.url;
  } catch (error) {
    if (paymentMessage) paymentMessage.textContent = error.message || "Checkout is unavailable.";
    button.disabled = false;
    button.innerHTML = original;
  }
}

export async function init() {
  const stylesList = document.querySelector("#styles-list");
  const scheduleList = document.querySelector("#schedule-list");
  const priceGrid = document.querySelector("#price-grid");
  if (!stylesList || !scheduleList || !priceGrid) return;
  const [{ styles, schedule }, { plans }] = await Promise.all([getJson("/api/classes"), getJson("/api/pricing")]);
  renderIfChanged(stylesList, styles.map((style, index) => `<article><span>${String(index + 1).padStart(2, "0")}</span><h2>${htmlEscape(style.name)}</h2><p>${htmlEscape(style.description)}</p><small>${htmlEscape(style.level)} · ${style.duration_minutes} min</small></article>`).join(""));
  renderIfChanged(scheduleList, schedule.map(item => `<div><strong>${htmlEscape(item.day)} · ${htmlEscape(item.date)}</strong><span>${htmlEscape(item.time)} · ${htmlEscape(item.timezone)}</span><span>${htmlEscape(item.title)}</span><span>${htmlEscape(item.instructor)} · ${item.duration_minutes} min · ${item.spots_remaining} open · ${item.waitlist_count} waitlisted</span><button class="text-link book-class" data-occurrence="${item.occurrence_id}">Reserve Your Spot →</button></div>`).join(""));
  renderIfChanged(priceGrid, plans.map(plan => `<article class="${plan.is_featured ? "featured" : ""}"><p>${htmlEscape(plan.name)}</p><strong>${htmlEscape(plan.price)}</strong><span>${htmlEscape(plan.description)}</span><button class="button checkout" data-plan="${htmlEscape(plan.slug)}">Reserve Your Spot <span>→</span></button></article>`).join(""));
  scheduleList.onclick = event => {
    const button = event.target.closest(".book-class");
    if (button) reserve(button);
  };
  priceGrid.onclick = event => {
    const button = event.target.closest(".checkout");
    if (button) checkout(button);
  };
}
