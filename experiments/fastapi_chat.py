from datetime import datetime, timezone
from fastapi import FastAPI, Path, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError
app = FastAPI(title="Чат")
# --- Модель повідомлення -----------------------------------------------------
# Pydantic одночасно: валідує вхід, серіалізує у JSON і описує схему в /docs.
# У Flask це були б ручні перевірки if/len() або окрема бібліотека (marshmallow).
class Message(BaseModel):
    id: int
    nick: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=500)
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MessageCreate(BaseModel):
    nick: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=500)

history: list[Message] = []
message_id_counter: int = 1
# --- Хаб з'єднань ------------------------------------------------------------
class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
    async def join(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)
    def leave(self, ws: WebSocket) -> None:
        self.clients.discard(ws)
    async def broadcast(self, msg: Message) -> None:
        payload = msg.model_dump_json()
        for ws in list(self.clients):
            try:
                await ws.send_text(payload)
            except Exception:
                self.leave(ws)
    async def update_message(self, old_time:datetime, new_text: str):
        for i, msg in enumerate(history):
            if msg.time == old_time:
                updated = Message(nick=msg.nick, text=new_text)
                history[i] = updated
                await self.broadcast(updated)
                return True
        return False
hub = Hub()
# --- Маршрути ----------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return PAGE
@app.post("/api/messages", response_model=Message, status_code=201)
async def create_message(msg: MessageCreate):
    global message_id_counter
    message = Message(id=message_id_counter, nick=msg.nick, text=msg.text)
    message_id_counter += 1
    history.append(message)
    await hub.broadcast(message)
    return message
# Параметри з type hints: limit перетворюється на int і перевіряється (1..200)
# автоматично. Відповідь фільтрується і документується через response_model.
@app.get("/api/messages", response_model=list[Message])
async def messages(limit: int = Query(50, ge=1, le=200)):
    return history[-limit:]
# WebSocket як рідна можливість фреймворку (у Flask потрібен flask-sock
# або Flask-SocketIO + окремий async-режим).
@app.websocket("/ws/{nick}")
async def chat(ws: WebSocket, nick: str = Path(min_length=1, max_length=20)):
    await hub.join(ws)
    try:
        while True:
            text = await ws.receive_text()
            try:
                msg = Message(nick=nick, text=text)
            except ValidationError:
                continue
# задовге або порожнє — ігноруємо
            history.append(msg)
            del history[:-200]
# тримаємо останні 200
            await hub.broadcast(msg)
    except WebSocketDisconnect:
        hub.leave(ws)
@app.post("/api/messages/update")
async def messages_update(old_time: datetime, new_text: str):
    for i, msg in enumerate(history):
        if msg.time == old_time:
            try:
                history[i] = msg.model_copy(update={"text": new_text})
                await hub.broadcast(history[i])
                return {"success": True}
            except ValidationError:
                return {"success": False}
        return {"success": False, "error": "Message not found"}

@app.post("/api/messages/delete")
async def delete_message(msg_time: datetime):
    for i, msg in enumerate(history):
        if msg.time == msg_time:
            history.pop(i)
            return {"success": True}
        return {"success": False, "error": "Message not found"}
# --- Сторінка ----------------------------------------------------------------
PAGE = """<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Чат</title>
<style>
  body { font: 15px/1.4 Georgia, serif; max-width: 640px; margin: 2em auto; padding: 0 1em; color: #222; background: #fafaf7; }
  h1 { font-size: 1.2em; font-weight: normal; border-bottom: 1px solid #999; padding-bottom: .3em; }
  #log { height: 360px; overflow-y: auto; border: 1px solid #999; background: #fff; padding: .5em; font-family: monospace; font-size: 14px; }
  #log div { margin-bottom: .2em; word-wrap: break-word; }
  .t { color: #888; }
  form { display: flex; gap: .4em; margin-top: .6em; }
  input { font: inherit; padding: .3em; border: 1px solid #999; }
  #nick { width: 8em; }
  #text { flex: 1; }
  button { font: inherit; padding: .3em .8em; }
  small { color: #777; }
</style>
</head>
<body>
<h1>Чат</h1>
<div id="log"></div>
<form id="f">
  <input id="nick" placeholder="нік" maxlength="20" required>
  <input id="text" placeholder="повідомлення" maxlength="500" autocomplete="off" required>
  <button>Надіслати</button>
</form>
<small id="status">не підключено</small> · <small><a href="/docs">/docs</a></small>
<script>
const log = document.getElementById('log');
const status = document.getElementById('status');
const nick = document.getElementById('nick');
const text = document.getElementById('text');
let ws = null;
nick.value = localStorage.getItem('nick') || '';
function add(m) {
  const row = document.createElement('div');
  row.dataset.time = m.time;

  const t = document.createElement('span');
  t.className = 't';
  t.textContent = '[' + new Date(m.time).toLocaleTimeString().slice(0, 5) + '] ';

  const content = document.createElement('span');
  content.textContent = m.nick + ': ' + m.text + ' ';

  const edit = document.createElement('button');
  edit.textContent = 'Edit';
  edit.type = 'button';
  edit.onclick = async () => {
    const newText = prompt('Edit message:', m.text);
    if (!newText || !newText.trim()) return;

    const r = await fetch('/api/messages/update?old_time=' +
      encodeURIComponent(m.time) + '&new_text=' + encodeURIComponent(newText),
      { method: 'POST' });

    if ((await r.json()).success) {
      content.textContent = m.nick + ': ' + newText + ' ';
      m.text = newText;
    }
  };
  const del = document.createElement('button');
  del.textContent = 'Delete';
  del.type = 'button';
  del.onclick = async () => {
    if (!confirm('Delete this message?')) return;

    const r = await fetch('/api/messages/delete?msg_time=' +
      encodeURIComponent(m.time), { method: 'POST' });

    if ((await r.json()).success) row.remove();
  };

  row.append(t, content, edit, del);
  log.append(row);
  log.scrollTop = log.scrollHeight;
}

}
function connect() {
  if (ws) ws.close();
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto + '://' + location.host + '/ws/' + encodeURIComponent(nick.value));
  ws.onopen = () => status.textContent = 'підключено як ' + nick.value;
  ws.onclose = () => status.textContent = 'не підключено';
  ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.nick === 'SYSTEM' && m.text.startsWith('Message deleted:')) return;

  const old = [...log.children].find(row => row.dataset.time === m.time);
  if (old) old.remove();

  add(m);
};

}
document.getElementById('f').onsubmit = e => {
  e.preventDefault();
  if (!ws || ws.readyState !== 1 || localStorage.getItem('nick') !== nick.value) {
    localStorage.setItem('nick', nick.value);
    connect();
    ws.addEventListener('open', () => { ws.send(text.value); text.value = ''; }, { once: true });
  } else {
    ws.send(text.value);
    text.value = '';
  }
};
fetch('/api/messages').then(r => r.json()).then(list => list.forEach(add));
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)