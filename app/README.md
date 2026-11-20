# The app

This is the review app: record a session, go through what the model found, and export the result. It is built with Next.js and TypeScript, exported as static files and served by a small local FastAPI server.

## Running it

From the repo root, once:

```powershell
cd app\frontend
npm install
npm run build
cd ..\..
```

Then every time:

```powershell
uv run --project spike python app/backend/server.py
```

and open http://localhost:8765. Ollama needs to be running for the extraction step.

While working on the UI itself, run the server as above and `npm run dev` in `app\frontend`, then use http://localhost:5173. Changes show up straight away, and calls to `/api` are forwarded to the server.

## Shortcuts on the review screen

| Key | Does |
|---|---|
| J or Down | Next item |
| K or Up | Previous item |
| A | Accept and move on |
| R | Reject and move on |
| E | Edit the wording |
| U | Back to "to review" |
| Enter | Play the moment it was said |
| Space | Play or pause |

The design thinking is in [docs/04-ui-design.md](../docs/04-ui-design.md).
