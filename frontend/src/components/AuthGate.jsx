import { useCallback, useEffect, useId, useState } from 'react';
import { LockKeyhole } from 'lucide-react';
import { apiErrorMessage, apiFetch, apiJsonFetch } from '../utils/api.js';
import './AuthGate.css';


function LoginScreen({ onAuthenticated }) {
  const usernameId = useId();
  const passwordId = useId();
  const [username, setUsername] = useState('connie');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const response = await apiJsonFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(apiErrorMessage(payload, '暂时无法登录，请稍后再试。'));
        return;
      }
      setPassword('');
      onAuthenticated(payload.data);
    } catch {
      setError('没有连接上我们的小窝，请检查网络后重试。');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-mark" aria-hidden="true"><LockKeyhole size={21} strokeWidth={1.5} /></div>
        <p className="auth-eyebrow">OUR NEST</p>
        <h1 id="auth-title">回到我们的小窝</h1>
        <p className="auth-intro">这是只属于两个人的空间。确认是你，我们就继续上次的故事。</p>

        <form className="auth-form" onSubmit={submit}>
          <label htmlFor={usernameId}>名字</label>
          <input
            id={usernameId}
            name="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
          <label htmlFor={passwordId}>暗号</label>
          <input
            id={passwordId}
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            autoFocus
          />
          <div className="auth-message" role="alert" aria-live="polite">{error}</div>
          <button type="submit" disabled={submitting}>
            {submitting ? '正在开门…' : '回到小窝'}
          </button>
        </form>
        <p className="auth-footnote">登录状态只保存在这台设备，密码不会留在浏览器里。</p>
      </section>
    </main>
  );
}


export default function AuthGate({ children }) {
  const [status, setStatus] = useState('checking');

  const requireLogin = useCallback(() => setStatus('anonymous'), []);

  useEffect(() => {
    let active = true;
    apiFetch('/auth/me')
      .then((response) => {
        if (active) setStatus(response.ok ? 'authenticated' : 'anonymous');
      })
      .catch(() => {
        if (active) setStatus('anonymous');
      });
    window.addEventListener('remoire-auth-required', requireLogin);
    return () => {
      active = false;
      window.removeEventListener('remoire-auth-required', requireLogin);
    };
  }, [requireLogin]);

  if (status === 'checking') {
    return <div className="auth-loading" role="status" aria-label="正在确认登录状态"><span /></div>;
  }
  if (status === 'anonymous') {
    return <LoginScreen onAuthenticated={() => setStatus('authenticated')} />;
  }
  return children;
}
