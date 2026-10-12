import { useEffect, useRef, useState } from 'react';
import { Search, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { apiFetch, API_BASE } from '../utils/api';
import { ImageViewer } from './ChatImage';
import './StickerPicker.css';

function StickerTile({ item, disabled, onSend, onPreview }) {
  const timer = useRef(null);
  const start = useRef(null);
  const held = useRef(false);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => () => clearTimeout(timer.current), []);
  const cancel = () => clearTimeout(timer.current);
  return <button type="button" className="sticker-tile" disabled={disabled || failed || !loaded}
    aria-label={`发送表情：${item.label}`} title={item.label}
    onPointerDown={e => {
      held.current = false;
      start.current = [e.clientX, e.clientY];
      timer.current = setTimeout(() => { held.current = true; onPreview(item); }, 550);
    }}
    onPointerMove={e => { if (start.current && Math.hypot(e.clientX-start.current[0], e.clientY-start.current[1]) > 8) { cancel(); held.current = true; } }}
    onPointerUp={cancel} onPointerCancel={cancel} onPointerLeave={cancel}
    onContextMenu={e => { e.preventDefault(); cancel(); held.current = true; onPreview(item); }}
    onClick={() => { if (!held.current) onSend(item); held.current = false; }}>
    {failed ? <span className="sticker-unavailable">图片暂不可用</span> : <img src={`${API_BASE}/chat/stickers/${item.id}/image`} alt={item.label} loading="lazy" draggable="false" onLoad={() => setLoaded(true)} onError={() => setFailed(true)} />}
  </button>;
}

export default function StickerPicker({ disabled, onSend, onClose }) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState({ items: [], total: 0, categories: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(null);
  const [reload, setReload] = useState(0);
  const scroller = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await apiFetch(`/chat/stickers?${new URLSearchParams({ q: query, category, offset, limit: 24 })}`, { signal: controller.signal });
        const payload = await response.json();
        if (!response.ok || !payload.ok) throw new Error();
        if (!controller.signal.aborted) { setData(payload.data); setError(''); scroller.current?.scrollTo(0, 0); }
      } catch {
        if (!controller.signal.aborted) setError('图库暂时打不开，请重试');
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, category, offset, reload]);
  const change = (setter, value) => { setLoading(true); setError(''); setOffset(0); setter(value); };
  return <section className="sticker-picker" aria-label="表情包图库" onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); onClose(); } }}>
    <div className="sticker-picker-head">
      <label className="sticker-search"><Search size={17} strokeWidth={1.5} /><input aria-label="搜索表情包" placeholder="搜心情、动作、小动物…" value={query} maxLength={100} onChange={e => change(setQuery,e.target.value)} /></label>
      <button className="sticker-icon" aria-label="关闭表情包图库" onClick={onClose}><X size={20} strokeWidth={1.5}/></button>
    </div>
    <div className="sticker-categories" aria-label="表情分类">
      {['', ...data.categories].map(c => <button key={c} aria-pressed={category === c} onClick={() => { if (category !== c) change(setCategory,c); }}>{c || '全部'}</button>)}
    </div>
    <div className="sticker-grid-scroll" ref={scroller} aria-busy={loading}>
      {loading ? <p className="sticker-empty" role="status">正在找表情…</p> : error ? <p className="sticker-empty" role="alert">{error}<button onClick={() => {setLoading(true);setReload(n=>n+1);}}>重试</button></p> : data.items.length ? <div className="sticker-grid">
        {data.items.map(item => <StickerTile key={item.id} item={item} disabled={disabled} onSend={onSend} onPreview={setPreview} />)}
      </div> : <p className="sticker-empty">没有找到，换个关键词试试</p>}
    </div>
    <footer className="sticker-picker-foot"><span>{disabled ? '等 Connie 回完再发' : '轻点发送 · 长按预览'}</span><div>
      <button className="sticker-icon" aria-label="上一页表情" disabled={!offset || loading} onClick={() => {setLoading(true);setOffset(n=>Math.max(0,n-24));}}><ChevronLeft size={18}/></button>
      <span>{Math.floor(offset/24)+1} / {Math.max(1,Math.ceil(data.total/24))}</span>
      <button className="sticker-icon" aria-label="下一页表情" disabled={offset+24>=data.total || loading} onClick={() => {setLoading(true);setOffset(n=>n+24);}}><ChevronRight size={18}/></button>
    </div></footer>
    {preview && <ImageViewer src={`${API_BASE}/chat/stickers/${preview.id}/image`} onClose={() => setPreview(null)} />}
  </section>;
}
