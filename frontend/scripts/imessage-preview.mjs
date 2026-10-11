// Read-only synthetic preview; never connects to a backend, model, or Photon.
import { createServer } from 'vite';
import { fileURLToPath } from 'node:url';
process.env.VITE_API_BASE = '/api';
const previewPort = Number(process.env.PREVIEW_PORT || 4190);
const messages = [
 {id:'m1',role:'assistant',content:'傍晚出去走走？\n\n等天凉一点。',created_at:'2026-10-10T09:00:00',channel:'imessage',display_mode:'split',imessage_bubbles:[
 {external_id:'a1',body:'傍晚出去走走？',quote:'',reactions:[]},
 {external_id:'a2',body:'等天凉一点。',quote:'',reactions:[]}]},
 {id:'m2',role:'user',content:'好呀，就去河边。\n带上相机',created_at:'2026-10-10T09:01:00',channel:'imessage',imessage_bubbles:[
 {external_id:'u1',body:'好呀，就去河边。',quote:'傍晚出去走走？',reactions:[]},
 {external_id:'u2',body:'带上相机',quote:'',reactions:[]}]},
 {id:'m3',role:'assistant',content:'好，我记着。',created_at:'2026-10-10T09:02:00',channel:'imessage',display_mode:'split',imessage_bubbles:[
 {external_id:'a3',body:'好，我记着。',quote:'带上相机',reactions:[]}]},
];
const server=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),server:{host:'127.0.0.1',port:previewPort,strictPort:true},plugins:[{name:'imessage-fixture',configureServer(s){s.middlewares.use((req,res,next)=>{
if(!req.url.startsWith('/api/')) return next();
res.setHeader('Content-Type','application/json');
if(req.method!=='GET'){res.statusCode=409;return res.end(JSON.stringify({ok:false,error:'本地预览不发送消息，也不保存修改。'}));}
const path=req.url.split('?')[0];let data={};
if(path==='/api/auth/me') data={username:'本地预览'};
else if(path==='/api/chat/latest') data={conversation_id:'imessage-fixture'};
else if(path==='/api/chat/history') data={messages,conversation_id:'imessage-fixture'};
else if(path==='/api/chat/status') data={presence_text:'iMessage 交互预览 · 虚构数据'};
else if(path==='/api/note/unread') data={note:null};
else if(path==='/api/settings/slots') data=[];
else if(path.includes('presets')||path.includes('reminder')||path.includes('note')||path.includes('special-dates')) data=[];
res.end(JSON.stringify({ok:true,data,error:null}));
});}}]});await server.listen();console.log(`Read-only iMessage preview: http://127.0.0.1:${previewPort}/`);
