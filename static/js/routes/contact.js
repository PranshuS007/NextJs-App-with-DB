import { formValues, postJson } from "../utils.js";

export async function init() {
  const contact = document.querySelector("#contact-form");
  if (!contact) return;
  contact.addEventListener("submit", async event => {
    event.preventDefault();
    const message = contact.querySelector(".form-message");
    if (message) message.textContent = "Sending...";
    try {
      const data = await postJson("/api/contact", formValues(contact));
      if (message) message.textContent = data.message || "Your message was sent.";
      contact.reset();
    } catch (error) {
      if (message) message.textContent = error.message || "Unable to send your message. Please try again.";
    }
  });
}
