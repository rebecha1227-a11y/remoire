import { useEffect, useRef, useState } from 'react';
import { Download, X } from 'lucide-react';

function ImageViewer({ src, onClose }) {
  const dialog = useRef(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    const element = dialog.current;
    const previousOverflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = 'hidden';
    return () => {
      element.close();
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  async function save() {
    setSaving(true);
    setError('');
    try {
      const response = await fetch(src, { credentials: 'include' });
      if (!response.ok) throw new Error('download');
      const blob = await response.blob();
      if (!blob.type.startsWith('image/')) throw new Error('image');
      const extension = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif' }[blob.type] || 'png';
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `remoire-${Date.now()}.${extension}`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch {
      setError('暂时无法下载，请长按图片保存，或打开原图后保存。');
    } finally {
      setSaving(false);
    }
  }

  return (
    <dialog ref={dialog} className="r-image-viewer" aria-label="查看原图" onCancel={onClose}
      onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
      <header className="r-image-toolbar">
        <span>原图</span>
        <div>
          <button type="button" onClick={save} disabled={saving} aria-label="保存原图">
            <Download size={19} strokeWidth={1.5} /><span>{saving ? '保存中…' : '保存原图'}</span>
          </button>
          <button type="button" onClick={onClose} aria-label="关闭图片" autoFocus><X size={22} strokeWidth={1.5} /></button>
        </div>
      </header>
      <div className="r-image-stage" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
        <img src={src} alt="聊天原图" />
      </div>
      <footer className="r-image-footer">
        <span role="status">{error || '手机可长按图片保存；下载按钮保存到设备文件。'}</span>
        <a href={src} target="_blank" rel="noreferrer">打开原图</a>
      </footer>
    </dialog>
  );
}

export default function ChatImage({ src }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="r-chat-image" onMouseDown={event => event.stopPropagation()} onTouchStart={event => event.stopPropagation()}>
      <button type="button" className="r-chat-photo-button" onClick={() => setOpen(true)} aria-label="放大查看图片">
        <img src={src} alt="聊天图片" className="r-chat-photo" loading="lazy" decoding="async" />
      </button>
      {open && <ImageViewer src={src} onClose={() => setOpen(false)} />}
    </div>
  );
}
