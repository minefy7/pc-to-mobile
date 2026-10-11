"use strict";

const CLIENT_ID_KEY = "lan_chat_client_id";
const NAME_KEY = "lan_chat_name";

const messagesEl = document.getElementById("messages");
const textInput = document.getElementById("text-input");
const nameInput = document.getElementById("name-input");
const sendBtn = document.getElementById("send");
const presenceEl = document.getElementById("presence");
const typingEl = document.getElementById("typing");
const bannerEl = document.getElementById("reconnect-banner");
const loadMoreBtn = document.getElementById("load-more");

// crypto.randomUUID() доступен только в secure context (https или localhost).
// Телефон заходит по обычному http://<ip>:8000 — там crypto.randomUUID есть,
// но может отсутствовать, и страница падала бы ещё до создания WebSocket.
// Поэтому используем безопасный фоллбэк.
function randomId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  }
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
}

let clientId = localStorage.getItem(CLIENT_ID_KEY) || randomId();
localStorage.setItem(CLIENT_ID_KEY, clientId);
let name = localStorage.getItem(NAME_KEY) || "";
nameInput.value = name;

let socket = null;
let retryDelay = 1000;
let loadingOlder = false;
let atBottom = true;
const typingUsers = new Set();

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatSize(bytes) {
  if (!Number.isFinite(bytes)) return "";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function atBottomNow() {
  return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 60;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderMessage(msg, { prepend = false } = {}) {
  const mine = msg.sender === name && name !== "";
  const el = document.createElement("div");
  el.className = "msg" + (mine ? " self" : "");
  el.dataset.id = msg.id;

  const metaLine = document.createElement("div");
  metaLine.className = "meta-line";
  const sender = document.createElement("span");
  sender.className = "sender";
  sender.textContent = mine ? "Я" : msg.sender;
  const time = document.createElement("span");
  time.className = "time";
  time.textContent = formatTime(msg.created_at);
  metaLine.append(sender, time);
  el.append(metaLine);

  if (msg.kind === "file" && msg.file_id) {
    const box = document.createElement("div");
    box.className = "file";
    const href = `/files/${msg.file_id}`;
    const mime = msg.mime_type || "";
    if (mime.startsWith("image/")) {
      const img = document.createElement("img");
      img.src = href;
      img.loading = "lazy";
      img.alt = msg.file_name || "изображение";
      box.append(img);
    } else if (mime.startsWith("video/") || mime.startsWith("audio/")) {
      const media = document.createElement(mime.startsWith("video/") ? "video" : "audio");
      media.src = href;
      media.controls = true;
      box.append(media);
    }
    const link = document.createElement("a");
    link.className = "download-link";
    link.href = href;
    link.download = msg.file_name || "file";
    link.textContent = `⬇ ${msg.file_name || "Файл"}`;
    const size = document.createElement("span");
    size.className = "size";
    size.textContent = formatSize(msg.file_size);
    link.append(size);
    box.append(link);
    el.append(box);
  } else if (msg.text) {
    const text = document.createElement("div");
    text.textContent = msg.text;
    el.append(text);
  }

  if (prepend) {
    messagesEl.prepend(el);
  } else {
    messagesEl.append(el);
    if (atBottom) scrollToBottom();
  }
  return el;
}

function updatePresence(users) {
  presenceEl.textContent = users.length ? `онлайн: ${users.join(", ")}` : "никого нет";
  updateTypingLine();
}

function updateTypingLine() {
  const others = [...typingUsers].filter((n) => n !== name);
  if (others.length === 0) {
    typingEl.textContent = "";
  } else if (others.length === 1) {
    typingEl.textContent = `${others[0]} печатает…`;
  } else {
    typingEl.textContent = "печатают несколько…";
  }
}

function sendWs(payload) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload));
  }
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/ws?name=${encodeURIComponent(name || "Гость")}&id=${clientId}`;
  socket = new WebSocket(url);

  socket.onopen = () => {
    retryDelay = 1000;
    bannerEl.classList.add("hidden");
  };

  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    switch (payload.type) {
      case "message":
        renderMessage(payload.message);
        break;
      case "presence":
        updatePresence(payload.users || []);
        break;
      case "typing":
        if (payload.active) typingUsers.add(payload.sender);
        else typingUsers.delete(payload.sender);
        updateTypingLine();
        break;
      case "error":
        console.warn("Ошибка сервера:", payload.detail);
        break;
      case "shutdown":
        bannerEl.textContent = "Сервер перезапускается…";
        bannerEl.classList.remove("hidden");
        break;
    }
  };

  socket.onclose = () => {
    bannerEl.textContent = "Переподключение…";
    bannerEl.classList.remove("hidden");
    setTimeout(connect, retryDelay);
    retryDelay = Math.min(retryDelay * 2, 30000);
  };

  socket.onerror = () => socket.close();
}

async function loadHistory(before = null) {
  const query = before ? `?before=${encodeURIComponent(before)}` : "";
  const response = await fetch(`/api/history${query}`);
  if (!response.ok) throw new Error("Не удалось загрузить историю");
  const data = await response.json();
  const items = data.messages || [];
  if (before) {
    const prevHeight = messagesEl.scrollHeight;
    items.forEach((msg) => renderMessage(msg, { prepend: true }));
    messagesEl.scrollTop = messagesEl.scrollHeight - prevHeight;
  } else {
    items.forEach((msg) => renderMessage(msg));
    scrollToBottom();
  }
  loadMoreBtn.classList.toggle("hidden", items.length === 0);
}

messagesEl.addEventListener("scroll", () => {
  atBottom = atBottomNow();
  if (messagesEl.scrollTop < 80 && !loadingOlder && !loadMoreBtn.classList.contains("hidden")) {
    const first = messagesEl.firstElementChild;
    if (first) {
      loadingOlder = true;
      loadHistory(first.dataset.id).finally(() => (loadingOlder = false));
    }
  }
});

loadMoreBtn.addEventListener("click", () => {
  const first = messagesEl.firstElementChild;
  if (first) loadHistory(first.dataset.id);
});

let typingSentAt = 0;
textInput.addEventListener("input", () => {
  const now = Date.now();
  if (now - typingSentAt > 1500) {
    typingSentAt = now;
    sendWs({ type: "typing", active: true });
  }
});

textInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendBtn.click();
  }
});

sendBtn.addEventListener("click", () => {
  const text = textInput.value.trim();
  if (text) {
    sendWs({ type: "message", text });
    textInput.value = "";
    typingSentAt = 0;
  }
  textInput.focus();
});

nameInput.addEventListener("change", () => {
  name = nameInput.value.trim().slice(0, 40) || "Гость";
  nameInput.value = name;
  localStorage.setItem(NAME_KEY, name);
  socket?.close();
});

loadHistory()
  .catch((error) => console.error(error.message))
  .finally(() => {
    textInput.focus();
    connect();
  });
