/**
 * Thin wrapper around the gameplay backend's WebSocket /play endpoint.
 *
 * Usage:
 *   const client = createGameClient({
 *     url: "ws://127.0.0.1:8001/play",
 *     onEvent(ev) { ... },           // every mjai event (annotated with _cans/_your_turn)
 *     onOpen() { ... },
 *     onClose() { ... },
 *     onError() { ... },
 *   });
 *   client.connect();
 *   client.send({ type: "dahai", actor: 0, pai: "5p", tsumogiri: false });
 *   client.disconnect();
 */
export function createGameClient({
  url,
  onEvent = () => {},
  onOpen = () => {},
  onClose = () => {},
  onError = () => {},
} = {}) {
  let ws = null;

  function connect() {
    if (ws) {
      try { ws.close(); } catch (_) {}
    }
    ws = new WebSocket(url);
    ws.addEventListener("open", () => onOpen());
    ws.addEventListener("close", () => onClose());
    ws.addEventListener("error", (e) => onError(e));
    ws.addEventListener("message", (msg) => {
      let ev;
      try { ev = JSON.parse(msg.data); } catch { return; }
      onEvent(ev);
    });
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
    }
  }

  function disconnect() {
    if (ws) {
      try { ws.close(); } catch (_) {}
      ws = null;
    }
  }

  return { connect, send, disconnect };
}
