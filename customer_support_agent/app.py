from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent.graph import run_agent


app = FastAPI(title="Support Copilot")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Support Copilot</title>
        <style>
          body { font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; }
          form { display: flex; gap: 8px; }
          input { flex: 1; padding: 10px 12px; }
          button { padding: 10px 14px; cursor: pointer; }
          pre { background: #f5f5f5; padding: 16px; white-space: pre-wrap; }
        </style>
      </head>
      <body>
        <h1>Support Copilot</h1>
        <form id="chat-form">
          <input id="message" name="message" value="hello agent" />
          <button type="submit">Send</button>
        </form>
        <pre id="output"></pre>
        <script>
          const form = document.getElementById("chat-form");
          const output = document.getElementById("output");
          form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const message = document.getElementById("message").value;
            const res = await fetch("/chat", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ message })
            });
            output.textContent = JSON.stringify(await res.json(), null, 2);
          });
        </script>
      </body>
    </html>
    """


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(response=run_agent(request.message))

