import { useEffect, useRef, useState } from "react";
import type { Requirement } from "../types";
import { TYPES } from "../format";
import { Icon } from "./Icon";

interface Props {
  req: Requirement;
  selected: boolean;
  editing: boolean;
  onSelect: () => void;
  onPlay: () => void;
  onStatus: (status: Requirement["status"]) => void;
  onEdit: (open: boolean) => void;
  onSave: (statement: string, note: string) => void;
}

const STATUS_LABEL = { pending: "To review", accepted: "Accepted", rejected: "Rejected" } as const;

export function RequirementRow({ req, selected, editing, onSelect, onPlay, onStatus, onEdit, onSave }: Props) {
  const row = useRef<HTMLDivElement>(null);
  const [text, setText] = useState(req.edited_statement ?? req.statement);
  const [note, setNote] = useState(req.note ?? "");
  const t = TYPES[req.type] ?? { code: "?", label: req.type };
  const statement = req.edited_statement ?? req.statement;

  useEffect(() => {
    if (selected) row.current?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  useEffect(() => {
    if (editing) {
      setText(req.edited_statement ?? req.statement);
      setNote(req.note ?? "");
    }
  }, [editing, req]);

  return (
    <div ref={row} className={`req is-${req.status}`} aria-selected={selected} onClick={onSelect} role="option">
      <div className="req-code">
        <span title={t.label}>{t.code}</span>
        <span className="id">{req.id.replace("REQ-", "")}</span>
      </div>

      <div>
        <div className="req-statement">{statement}</div>
        {req.edited_statement && <span className="edited-mark">Edited</span>}
      </div>

      <div className="req-actions" onClick={(e) => e.stopPropagation()}>
        {req.status === "pending" ? (
          <>
            <button className="btn sm icon act-accept" title="Accept (A)" aria-label="Accept" onClick={() => onStatus("accepted")}>
              <Icon name="check" size={14} />
            </button>
            <button className="btn sm icon act-reject" title="Reject (R)" aria-label="Reject" onClick={() => onStatus("rejected")}>
              <Icon name="x" size={14} />
            </button>
          </>
        ) : (
          <button className={`status ${req.status}`} style={{ border: 0, cursor: "pointer" }} title="Undo (U)"
            onClick={() => onStatus("pending")}>
            <Icon name={req.status === "accepted" ? "check" : "x"} size={12} /> {STATUS_LABEL[req.status]}
          </button>
        )}
        <button className="btn sm icon ghost" title="Edit (E)" aria-label="Edit" onClick={() => onEdit(!editing)}>
          <Icon name="edit" size={14} />
        </button>
      </div>

      {editing ? (
        <div className="edit-box" onClick={(e) => e.stopPropagation()}>
          <textarea autoFocus value={text} onChange={(e) => setText(e.target.value)} aria-label="Statement"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) onSave(text, note);
              if (e.key === "Escape") onEdit(false);
            }} />
          <input className="input" placeholder="Note for yourself (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="row">
            <span className="faint" style={{ fontSize: 12, marginRight: "auto" }}>Ctrl+Enter to save, Esc to cancel</span>
            <button className="btn sm" onClick={() => onEdit(false)}>Cancel</button>
            <button className="btn sm primary" onClick={() => onSave(text, note)}>Save</button>
          </div>
        </div>
      ) : (
        <>
          <div className="req-quote">“{req.quote}”</div>
          <div className="req-foot">
            <button className="linkish" onClick={(e) => { e.stopPropagation(); onPlay(); }} title="Play this moment">
              <Icon name="play" size={10} /> {req.speaker ?? "Unknown"}, {req.time ?? "?"}
            </button>
            {req.quality_category && <span>{req.quality_category}</span>}
            {req.flags?.map((f) => (
              <span key={f} className="flag"><Icon name="warn" size={12} /> {f.replace("vague wording: ", "Vague: ")}</span>
            ))}
            {req.note && <span title={req.note}>Note: {req.note}</span>}
          </div>
        </>
      )}
    </div>
  );
}
