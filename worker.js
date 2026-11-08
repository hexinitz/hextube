const JSON_HEADERS = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' };
const TECH = /python|program|coding|code\b|software|algorithm|data structure|compiler|interpreter|database|distributed|operating system|neural|deep learning|machine learning|\bml\b|\bai\b|llm|gpt|transformer|attention|backprop|gradient|reinforcement|pytorch|tensorflow|linear algebra|calculus|statistic|probability|lecture|course|rust|c\+\+|golang|javascript|typescript|system design|architecture|kernel|linux/i;
const CLICKBAIT = /#shorts?|\bshorts?\b|you won't believe|make money|passive income|get rich|chatgpt prompts?|ai tools? (you|that)|game[- ]?changer|insane|\b10x\b|mind[- ]?blow|secret (trick|to)|side hustle|crypto|trading bot/i;
function response(data, status=200) { return new Response(JSON.stringify(data), {status, headers: JSON_HEADERS}); }
function decodeXml(s) {
  return (s || '').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&#39;/g,"'").replace(/&#(\d+);/g,(_,n)=>String.fromCodePoint(Number(n))).replace(/&#x([0-9a-f]+);/gi,(_,n)=>String.fromCodePoint(parseInt(n,16)));
}
function tag(xml, name) {
  const escaped=name.replace(':','\\:');
  const m=new RegExp('<'+escaped+'(?:\\s[^>]*)?>([\\s\\S]*?)</'+escaped+'>','i').exec(xml);
  return m ? decodeXml(m[1].replace(/<[^>]+>/g,'').trim()) : '';
}
function normTitle(s) { return (s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim(); }
function parseConfig(text) {
  const out=[];
  for(const raw of (text||'').split(/\r?\n/)) {
    const line=raw.split('#',1)[0].trim(); if(!line) continue;
    const [left,...right]=line.split('|'); const value=left.trim(); if(!value) continue;
    out.push({value,topics:right.join('|').split(',').map(x=>x.trim()).filter(Boolean)});
  }
  return out;
}
async function readAsset(env,path) {
  const r=await env.ASSETS.fetch(new Request('https://hextube-assets.invalid/'+path));
  if(!r.ok) throw new Error(`Missing ${path} static configuration (${r.status})`);
  return r.text();
}
async function resolveChannelId(handle) {
  const r=await fetch('https://www.youtube.com/@'+encodeURIComponent(handle),{
    headers:{'user-agent':'Mozilla/5.0 (compatible; HexTube/1.0)','accept-language':'en-US,en;q=0.8'},
    redirect:'follow', signal:AbortSignal.timeout(12000)
  });
  if(!r.ok) throw new Error(`YouTube channel page returned ${r.status}`);
  const html=await r.text();
  const patterns=[/"externalId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"/,/"channelId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"/,/<meta[^>]+itemprop=["']channelId["'][^>]+content=["'](UC[A-Za-z0-9_-]{22})["']/i,/<meta[^>]+content=["'](UC[A-Za-z0-9_-]{22})["'][^>]+itemprop=["']channelId["']/i];
  for(const re of patterns){const m=re.exec(html);if(m)return m[1];}
  throw new Error('Could not find channel ID for @'+handle);
}
async function channelFeed(channelId) {
  const r=await fetch('https://www.youtube.com/feeds/videos.xml?channel_id='+encodeURIComponent(channelId),{
    headers:{'user-agent':'Mozilla/5.0 (compatible; HexTube/1.0)','accept':'application/atom+xml,application/xml,text/xml'},
    signal:AbortSignal.timeout(12000)
  });
  if(!r.ok) throw new Error(`YouTube RSS returned ${r.status}`);
  const xml=await r.text(), entries=[...xml.matchAll(/<entry>([\s\S]*?)<\/entry>/gi)].map(m=>m[1]);
  return entries.map(e=>{
    const vid=tag(e,'yt:videoId'), title=tag(e,'title'), channel=tag(e,'name');
    const published=tag(e,'published'), summary=tag(e,'media:description')||tag(e,'summary');
    return {vid,title,channel,published,summary};
  }).filter(v=>/^[A-Za-z0-9_-]{11}$/.test(v.vid)&&v.title);
}
function topics(title, defaults) {
  const t=[...defaults], add=(n,re)=>{if(re.test(title)&&!t.includes(n))t.push(n);};
  add('Python',/\bpython\b|pycon|numpy|pandas/i); add('DSA',/algorithm|data structure|dynamic programming|leetcode/i);
  add('LLMs',/\bgpt|llm|language model|transformer|attention/i); add('AI & ML',/neural|deep learning|machine learning|\bai\b|pytorch/i);
  add('Web',/javascript|typescript|react|node\.js/i); add('Systems & performance',/rust|c\+\+|kernel|linux|performance/i);
  if(t.includes('LLMs')&&!t.includes('AI & ML'))t.push('AI & ML');
  return t.length?t:['Software design & craft'];
}
async function listVideos(env) {
  const rows=await env.DB.prepare('SELECT payload FROM videos ORDER BY source ASC, score DESC').all();
  const videos=(rows.results||[]).map(x=>JSON.parse(x.payload));
  return {videos,total_curated:videos.filter(v=>v.source!=='youtube').length,extra:videos.filter(v=>v.source==='youtube').length};
}
async function syncYouTube(env) {
  const [channelText,current]=await Promise.all([
    readAsset(env,'channels.txt'),env.DB.prepare('SELECT vid,source,payload FROM videos').all()
  ]);
  const rows=current.results||[], ids=new Set(rows.map(x=>x.vid));
  const titles=new Set(rows.map(x=>{try{return normTitle(JSON.parse(x.payload).title);}catch{return '';}}));
  const channels=parseConfig(channelText).filter(x=>/^@?[A-Za-z0-9._-]+$/.test(x.value));
  const warnings=[], additions=[];
  for(const entry of channels) {
    const handle=entry.value.replace(/^@/,'');
    try {
      const channelId=await resolveChannelId(handle);
      const feed=await channelFeed(channelId);
      for(const item of feed) {
        if(ids.has(item.vid)||!TECH.test(item.title)||CLICKBAIT.test(item.title))continue;
        const norm=normTitle(item.title); if(!norm||titles.has(norm))continue;
        const year=Number((item.published||'').slice(0,4))||null;
        const desc=(item.summary||'').replace(/\s+/g,' ').trim();
        const v={vid:item.vid,title:item.title,channel:item.channel||handle,summary:desc.slice(0,240),why:null,type:'video',level:'general',score:5,topics:topics(item.title,entry.topics),recs:0,years:[year,year],quote:null,quote_url:null,source:'youtube',embeddable:true,ref:'@'+handle,src:'channel'};
        additions.push(v); ids.add(item.vid); titles.add(norm);
      }
    } catch(e) { warnings.push('@'+handle+': '+String(e.message||e).slice(0,140)); }
  }
  for(let i=0;i<additions.length;i+=50) {
    const batch=additions.slice(i,i+50);
    await env.DB.batch(batch.map(v=>env.DB.prepare('INSERT OR IGNORE INTO videos (vid,source,score,payload,added_at) VALUES (?, ?, ?, ?, ?)').bind(v.vid,v.source,v.score,JSON.stringify(v),Date.now())));
  }
  return {ok:true,channels:channels.length,channel_warnings:warnings,candidates:additions.length,added:additions.length,method:'public YouTube RSS feeds; no API key'};
}
export default {
  async fetch(request,env) {
    const url=new URL(request.url),path=url.pathname;
    if(request.method==='GET'&&path==='/api/videos'){try{return response(await listVideos(env));}catch(e){return response({error:'Could not load video library'},500);}}
    if(request.method==='GET'&&path==='/api/watched'){const r=await env.DB.prepare('SELECT vid,watched_at FROM watched').all();return response(Object.fromEntries((r.results||[]).map(x=>[x.vid,x.watched_at])));}
    if(request.method==='POST'&&path==='/api/watched'){
      const origin=request.headers.get('Origin');if(origin&&new URL(origin).host!==url.host)return response({error:'origin not allowed'},403);
      if(!(request.headers.get('content-type')||'').includes('application/json'))return response({error:'JSON required'},415);
      const len=Number(request.headers.get('content-length')||0);if(len>2048)return response({error:'request too large'},413);
      const body=await request.json().catch(()=>null);if(!body||!/^[A-Za-z0-9_-]{11}$/.test(body.vid||'')||typeof body.watched!=='boolean')return response({error:'invalid request'},400);
      if(body.watched)await env.DB.prepare('INSERT INTO watched (vid,watched_at) VALUES (?,?) ON CONFLICT(vid) DO NOTHING').bind(body.vid,Date.now()).run();
      else await env.DB.prepare('DELETE FROM watched WHERE vid=?').bind(body.vid).run();
      const r=await env.DB.prepare('SELECT vid,watched_at FROM watched').all();return response(Object.fromEntries((r.results||[]).map(x=>[x.vid,x.watched_at])));
    }
    return path.startsWith('/api/')?response({error:'not found'},404):env.ASSETS.fetch(request);
  },
  async scheduled(event,env,ctx){ctx.waitUntil(syncYouTube(env).catch(err=>console.error('Daily YouTube RSS sync failed:',err)));}
};
