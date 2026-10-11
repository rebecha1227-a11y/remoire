// Local-only synthetic data; never use this script to serve production.
import { createServer } from 'vite';
import { fileURLToPath } from 'node:url';
process.env.VITE_API_BASE='/api';
const messages=[{id:'preview-user',role:'user',content:'这是本地预览，不是真实聊天记录。',created_at:'2026-10-05T10:00:00'}, {id:'preview-ai',role:'assistant',content:'我在这里。\n今天也要好好的呀。',created_at:'2026-10-05T10:01:00'}];
const server=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),server:{host:'127.0.0.1',port:4175,strictPort:true},plugins:[{name:'private-local-preview',configureServer(s){s.middlewares.use((req,res,next)=>{
if(!req.url.startsWith('/api/'))return next();
const path=req.url.split('?')[0]; let data={};
if(path==='/api/auth/me')data={username:'本地预览'};
else if(path==='/api/chat/latest')data={conversation_id:'preview'};
else if(path.includes('/chat/') && (path.includes('history')||path.includes('messages')))data={messages,conversation_id:'preview'};
else if(path==='/api/chat/status')data={presence_text:'本地视觉预览 · 虚构数据'};
else if(path==='/api/note/unread')data={note:null};
else if(path==='/api/diary')data=[{id:'preview-diary',author:req.url.includes('connie')?'connie':'jinger',title:'本地示例日记',content:'这是用于检查颜色和排版的示例。',created_at:'2026-10-05T10:00:00',locked:false,interactions:[]}];
else if(path==='/api/settings/autonomous')data={enabled:true};
else if(path==='/api/autonomous/dates')data=[`${new URL(req.url,'http://localhost').searchParams.get('month')}-05`];
else if(path==='/api/autonomous/logs')data=[{id:'preview-log',created_at:`${new URL(req.url,'http://localhost').searchParams.get('date')}T10:00:00`,action_type:'none',action_summary:'本地虚构生活日志，仅用于视觉预览'}];
else if(path==='/api/chat/latest-conversation')data={conversation_id:'preview'};
else if(path.includes('presets')||path.includes('reminder')||path.includes('note')||path.includes('special-dates'))data=[];
if(req.method!=='GET'){res.statusCode=409;res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({ok:false,error:'本地视觉预览不保存数据，也不调用模型'}));}
res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,data,error:null}));
});}}]});await server.listen();console.log('Local-only fixture preview: http://127.0.0.1:4175');
