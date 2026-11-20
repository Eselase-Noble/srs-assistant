import { useState } from "react";

interface Props {
  onClose: () => void;
  onStart: (name: string, source: "both" | "mic", consent: string) => Promise<void>;
}

export function RecordDialog({ onClose, onStart }: Props) {
  const [name, setName] = useState("");
  const [source, setSource] = useState<"both" | "mic">("both");
  const [agreed, setAgreed] = useState(false);
  const [who, setWho] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onStart(name.trim() || "Session", source, who.trim() ? `Agreed: ${who.trim()}` : "Participants agreed to recording");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="dialog" onSubmit={submit} role="dialog" aria-labelledby="rec-title">
        <div className="dialog-head">
          <h2 id="rec-title">New session</h2>
          <p>Recording starts right away. Audio is saved to this computer every few seconds.</p>
        </div>
        <div className="dialog-body">
          <div className="field">
            <label htmlFor="rec-name">Session name</label>
            <input id="rec-name" className="input" autoFocus placeholder="e.g. Warehouse operations, Ama"
              value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label>Where is the conversation happening?</label>
            <div className="choice">
              <button type="button" aria-pressed={source === "both"} onClick={() => setSource("both")}>
                <strong>Online call</strong>
                <span>Microphone and computer audio, labelled Room and Remote</span>
              </button>
              <button type="button" aria-pressed={source === "mic"} onClick={() => setSource("mic")}>
                <strong>In person</strong>
                <span>Microphone only</span>
              </button>
            </div>
            {source === "both" && <div className="field-help">Wear headphones so the microphone does not record the call twice.</div>}
          </div>
          <div className="field">
            <label className="check">
              <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
              <span>Everyone in this conversation knows it is being recorded and has agreed.</span>
            </label>
            {agreed && (
              <input className="input" style={{ marginTop: 8 }} placeholder="Who agreed (optional)"
                value={who} onChange={(e) => setWho(e.target.value)} />
            )}
          </div>
          {error && <div className="error">{error}</div>}
        </div>
        <div className="dialog-foot">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn danger" disabled={!agreed || busy}>
            <span className="dot" style={{ background: "#fff" }} /> {busy ? "Starting…" : "Start recording"}
          </button>
        </div>
      </form>
    </div>
  );
}
