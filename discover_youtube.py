#!/usr/bin/env python3
"""Discover recent videos from channels.txt using public YouTube RSS feeds.
No YouTube Data API key is needed. YouTube exposes the latest public uploads
for a channel through its public Atom feed (typically up to 15 recent videos).
"""
import argparse, html, json, os, re, sys, urllib.request, urllib.error, xml.etree.ElementTree as ET
HERE=os.path.dirname(os.path.abspath(__file__))
TECH=re.compile(r'python|program|coding|code\b|software|algorithm|data structure|compiler|interpreter|database|distributed|operating system|neural|deep learning|machine learning|\bml\b|\bai\b|llm|gpt|transformer|attention|backprop|gradient|reinforcement|pytorch|tensorflow|linear algebra|calculus|statistic|probability|lecture|course|rust|c\+\+|golang|javascript|typescript|system design|architecture|kernel|linux',re.I)
CLICKBAIT=re.compile(r'#shorts?|\bshorts?\b|you won.t believe|make money|passive income|get rich|chatgpt prompts?|ai tools? (you|that)|game[- ]?changer|insane|\b10x\b|mind[- ]?blow|secret (trick|to)|side hustle|crypto|trading bot',re.I)
NS={'yt':'http://www.youtube.com/xml/schemas/2015','atom':'http://www.w3.org/2005/Atom','media':'http://search.yahoo.com/mrss/'}
def read_channels():
    out=[]
    for line in open(os.path.join(HERE,'channels.txt'),encoding='utf-8'):
        line=line.split('#',1)[0].strip()
        if not line: continue
        a,_,b=line.partition('|')
        out.append((a.strip().lstrip('@'),[x.strip() for x in b.split(',') if x.strip()]))
    return out
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; HexTube/1.0)','Accept-Language':'en-US,en;q=0.8'})
    with urllib.request.urlopen(req,timeout=20) as r:return r.read()
def resolve(handle):
    page=fetch('https://www.youtube.com/@'+urllib.parse.quote(handle))
    text=page.decode('utf-8','replace')
    for pat in (r'"externalId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"',r'"channelId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"'):
        m=re.search(pat,text)
        if m:return m.group(1)
    raise RuntimeError('could not resolve channel ID')
def topic_list(title,defaults):
    t=list(defaults)
    for name,rx in [('Python',r'\bpython\b|pycon|numpy|pandas'),('DSA',r'algorithm|data structure|dynamic programming|leetcode'),('LLMs',r'\bgpt|llm|language model|transformer|attention'),('AI & ML',r'neural|deep learning|machine learning|\bai\b|pytorch'),('Web',r'javascript|typescript|react|node\.js'),('Systems & performance',r'rust|c\+\+|kernel|linux|performance')]:
        if re.search(rx,title,re.I) and name not in t:t.append(name)
    if 'LLMs' in t and 'AI & ML' not in t:t.append('AI & ML')
    return t or ['Software design & craft']
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dry-run',action='store_true')
    args=ap.parse_args()
    videos_path=os.path.join(HERE,'data','videos.json')
    extra_path=os.path.join(HERE,'data','extra_videos.json')
    hn=json.load(open(videos_path,encoding='utf-8'))
    extra=json.load(open(extra_path,encoding='utf-8')) if os.path.exists(extra_path) else []
    known={v['vid'] for v in hn+extra}
    titles={re.sub(r'[^a-z0-9]+',' ',v.get('title','').lower()).strip() for v in hn+extra}
    found=[]
    for handle,defaults in read_channels():
        try:
            channel_id=resolve(handle)
            root=ET.fromstring(fetch('https://www.youtube.com/feeds/videos.xml?channel_id='+channel_id))
            for entry in root.findall('atom:entry',NS):
                vid=entry.findtext('yt:videoId',default='',namespaces=NS)
                title=html.unescape(entry.findtext('atom:title',default='',namespaces=NS))
                if not vid or vid in known or not title or not TECH.search(title) or CLICKBAIT.search(title):continue
                norm=re.sub(r'[^a-z0-9]+',' ',title.lower()).strip()
                if norm in titles:continue
                channel=entry.findtext('atom:author/atom:name',default=handle,namespaces=NS)
                published=entry.findtext('atom:published',default='',namespaces=NS)
                desc=entry.findtext('media:group/media:description',default='',namespaces=NS)
                year=int(published[:4]) if published[:4].isdigit() else None
                found.append({'vid':vid,'title':title,'channel':channel,'summary':' '.join(desc.split())[:240],
                    'why':None,'type':'video','level':'general','score':5,'topics':topic_list(title,defaults),
                    'recs':0,'years':[year,year],'quote':None,'quote_url':None,'source':'youtube',
                    'embeddable':True,'ref':'@'+handle,'src':'channel'})
                known.add(vid);titles.add(norm)
            print('  channel @%s: scanned public RSS feed'%handle)
        except Exception as e:print('  ! @%s: %s'%(handle,str(e)[:160]))
    print('%d new videos found'%len(found))
    if args.dry_run:
        for v in found:print('  '+v['channel']+' — '+v['title'])
        return
    extra.extend(found)
    with open(extra_path,'w',encoding='utf-8') as f:json.dump(extra,f,ensure_ascii=False,indent=2)
    print('Saved %d total YouTube finds to data/extra_videos.json'%(len(extra)))
if __name__=='__main__':
    import urllib.parse
    main()
