import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icon.tsx';
export function ConfirmDialog({ title, children, confirmLabel, acknowledgement, danger = false, onConfirm, onCancel }:
  { title: string; children: React.ReactNode; confirmLabel: string; acknowledgement?: string;
    danger?: boolean; onConfirm: () => void; onCancel: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  useEffect(() => {
    const element = dialog.current;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    element?.showModal();
    cancel.current?.focus();
    return () => { element?.close(); previouslyFocused?.focus(); };
  }, []);
  return <dialog ref={dialog} className="confirm-dialog" aria-labelledby="dialog-title"
    onCancel={event => { event.preventDefault(); onCancel(); }}
    onClick={event => { if (event.target === event.currentTarget) onCancel(); }}>
    <div className="dialog-body">
      <div className={danger ? 'dialog-symbol danger-text' : 'dialog-symbol'}><Icon name="warning" size={26}/></div>
      <h2 id="dialog-title">{title}</h2>
      <div className="dialog-copy">{children}</div>
      {acknowledgement && <label className="acknowledgement">
        <input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)}/>
        <span>{acknowledgement}</span>
      </label>}
      <div className="dialog-actions">
        <button ref={cancel} type="button" className="button button--secondary" onClick={onCancel}>Cancel</button>
        <button type="button" className={'button ' + (danger ? 'button--danger' : 'button--primary')}
          disabled={Boolean(acknowledgement) && !acknowledged} onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </div>
  </dialog>;
}
