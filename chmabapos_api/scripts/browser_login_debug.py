from __future__ import annotations

import json
import time
import urllib.request

import websocket


def main() -> None:
    pages = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list"))
    page = next(item for item in pages if item.get("type") == "page")
    socket = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=5)
    counter = 0

    def send(method: str, params: dict | None = None) -> int:
        nonlocal counter
        counter += 1
        socket.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
        return counter

    def wait(seconds: float = 1.0) -> list[dict]:
        events = []
        socket.settimeout(0.15)
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                events.append(json.loads(socket.recv()))
            except websocket.WebSocketTimeoutException:
                pass
        return events

    send("Runtime.enable")
    send("Log.enable")
    send("Network.enable")
    send("Page.navigate", {"url": "http://127.0.0.1:5173/login"})
    wait(1.5)
    expression = """
    (() => {
      localStorage.clear();
      sessionStorage.clear();
      const inputs = [...document.querySelectorAll('input')];
      const setValue = (input, value) => {
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(input, value);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      };
      setValue(inputs.find(input => input.type === 'email'), 'duke@chmaba.com');
      setValue(inputs.find(input => input.type === 'password'), 'YiROLvC9PQnX5oVG0SNUQqcJ');
      document.querySelector('form button[type="submit"]')?.click();
      return JSON.stringify({ inputs: inputs.map(input => ({ type: input.type, value: input.type === 'password' ? 'redacted' : input.value })) });
    })()
    """
    evaluate_id = send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    events = wait(5)
    result = next((event.get("result", {}).get("result", {}).get("value") for event in events if event.get("id") == evaluate_id), None)
    print("filled", result)
    evaluate_id = send("Runtime.evaluate", {"expression": "JSON.stringify({href:location.href,text:document.body.innerText.slice(-700),token:Boolean(localStorage.getItem('chmaba.access_token'))})", "returnByValue": True})
    events = wait(4)
    result = next((event.get("result", {}).get("result", {}).get("value") for event in events if event.get("id") == evaluate_id), None)
    print("after", result)
    for event in events:
        if event.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}:
            print(json.dumps(event, default=str))
    socket.close()


if __name__ == "__main__":
    main()
