import { useState } from 'react';
import { Card } from './Card.tsx';

export function AccessGate({ telegram, rejected, onSubmit }: {
  telegram: boolean;
  rejected: boolean;
  onSubmit: (key: string) => void;
}) {
  const [key, setKey] = useState('');
  return <Card className="access-gate">
    <div className="card-heading">
      <div>
        <p className="eyebrow">Protected backend</p>
        <h1 className="section-title">Access required</h1>
      </div>
    </div>
    <p className="card-copy">{telegram
      ? 'This Telegram account is not on the allowed list. Ask the owner to add your user ID, or enter the access key.'
      : 'Enter the access key from the server setting API_ACCESS_TOKEN. It is stored only in this browser.'}</p>
    <form onSubmit={event => {
      event.preventDefault();
      if (key.trim()) onSubmit(key);
    }}>
      <label className="field">
        <span>Access key</span>
        <input
          type="password"
          autoComplete="current-password"
          value={key}
          aria-invalid={rejected}
          onChange={event => setKey(event.target.value)}
        />
        {rejected && <small className="field-error">That key was not accepted.</small>}
      </label>
      <button type="submit" className="button button--primary" disabled={!key.trim()}>Unlock</button>
    </form>
  </Card>;
}
