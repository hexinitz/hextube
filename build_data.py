#!/usr/bin/env python3
"""Curate the HackerTube dump down to programming / Python / DSA / AI-ML / Karpathy videos.
Usage: python3 build_data.py [path/to/hackertube-data]   -> writes data/videos.json + data/curated_list.csv"""
import json, re, sys, csv, collections, os
SRC = sys.argv[1] if len(sys.argv) > 1 else 'hackertube-data'
HERE = os.path.dirname(os.path.abspath(__file__))
vids = [json.loads(l) for l in open(os.path.join(SRC, 'videos.jsonl'), encoding='utf-8')]

PROG = {'programming-language-design','functional-programming','systems-programming-languages','scripting-languages',
 'software-architecture-design','software-performance','compilers-interpreters','testing-debugging-tools','web-development',
 'algorithms-data-structures','computational-theory','databases-storage','distributed-systems','operating-systems'}
AI = {'machine-learning','llms-generative-ai','computer-vision-speech','ai-data-other','ai-safety-impact','data-science-statistics'}
KEEP_TYPES = {'talk','lecture','course','tutorial','explainer','demo','interview','podcast'}
re_i = lambda p: re.compile(p, re.I)
BLOCK_CH = re_i(r'cgp grey|veritasium|stand-up maths|numberphile|practical engineering|minutephysics|^ted$|ted-ed|mark rober|corridor|gapminder|ezra klein|daily show|perimeter institute|concordia|cambridge university|humane tech|mediaarttube|huygens|geoff cumming|london mathematical|cool bug facts|suckerpinch|sethbling|denis shiryaev|ishikawa|mm648230|elizr|themcphearson|tripflag|george hotz archive|shortcircuit|algorythmics|because science|phillip bradbury|omnray|koyhoge|thoughtupquick|tom wildenhain')
BLOCK_TITLE = re_i(r"dasher|e\^\(i|wolfram|gan theft auto|beos demo|tabs outliner|trump|biden|election|climate|excel|benford|wordle|magic: the gathering|seasoning")
AI_KW = re_i(r'\b(ai|artificial intelligence|machine learning|deep learning|neural|gpt|llm|language model|transformer|attention|backprop|gradient|reinforcement|tensorflow|pytorch|keras|diffusion|embedding|nlp|computer vision|deep ?mind|openai|agi|alphago|alphafold|bayes|kalman|statistic|data science|learning)\b')
PY = re_i(r'\bpython\b|pycon|pydata|scipy|numpy|pandas|jupyter|django|flask|cpython|raymond hettinger|david beazley')
DSA = re_i(r'algorithm|data structure|dynamic programming|sorting|big[- ]?o\b|hash ?(table|map)|binary (tree|search)|b-?tree|recursion|linked list|quicksort')
ML_MATH = re_i(r'linear algebra|neural network|deep learning|machine learning|backprop|gradient descent|transformer|essence of calculus|statistics 110|probability and counting|bayes|information theory')
LLM = re_i(r'\bgpt|llm|language model|transformer|attention|chatgpt|tokeniz|sparks of agi')
KARPATHY_EXTRA = {'State of GPT | BRK216HFS'}

norm = lambda t: re.sub(r'[^a-z0-9]+', ' ', t.lower()).strip()
def blob(v): return ' '.join([v['title'], v['channel'], v['primary_topic'], ' '.join(v['tags'])])

def keep(v):
    t = blob(v); prim = v['categories'][0]['id'] if v['categories'] else ''
    if re.search('karpathy', v['title'] + v['channel'], re.I) or v['title'] in KARPATHY_EXTRA:
        return v['shelf_life'] != 'news'
    if v['shelf_life'] == 'news' or v['content_type'] not in KEEP_TYPES: return False
    if BLOCK_CH.search(v['channel']) or BLOCK_TITLE.search(v['title']): return False
    if v['hn']['recommenders'] < 2 or v['score'] < 2.0: return False
    if v['shelf_life'] == 'dated' and v['score'] < 3.0: return False
    if v['content_type'] in ('interview', 'podcast') and v['score'] < 3.0: return False
    if v['content_type'] == 'demo' and v['score'] < 5.0: return False
    if PY.search(t) and prim in PROG | AI: return True
    if prim in AI: return bool(AI_KW.search(t + ' ' + v['summary']))
    if prim in PROG: return True
    return prim in {'pure-mathematics','recreational-math','probability-game-theory','information-theory'} and \
        bool(ML_MATH.search(v['title'] + ' ' + v['primary_topic'] + ' ' + ' '.join(v['tags'])))

TOPIC_BY_CAT = {
 'programming-language-design':'Languages & compilers','functional-programming':'Languages & compilers','compilers-interpreters':'Languages & compilers',
 'scripting-languages':'Languages & compilers','systems-programming-languages':'Systems & performance','software-performance':'Systems & performance',
 'operating-systems':'Systems & performance','web-development':'Web','software-architecture-design':'Software design & craft',
 'testing-debugging-tools':'Software design & craft','databases-storage':'Databases & distributed','distributed-systems':'Databases & distributed',
 'algorithms-data-structures':'DSA','computational-theory':'Math & theory','machine-learning':'AI & ML','llms-generative-ai':'AI & ML',
 'computer-vision-speech':'AI & ML','ai-data-other':'AI & ML','data-science-statistics':'AI & ML','ai-safety-impact':'AI & ML'}

def topics(v):
    t = blob(v); T = []
    if re.search('karpathy', v['title'] + v['channel'], re.I) or v['title'] in KARPATHY_EXTRA: T.append('Karpathy')
    if PY.search(t): T.append('Python')
    if v['categories'] and v['categories'][0]['id'] == 'algorithms-data-structures' or DSA.search(v['title'] + ' ' + ' '.join(v['tags'])): T.append('DSA')
    for c in v['categories'][:2]:
        x = TOPIC_BY_CAT.get(c['id'])
        if x and x not in T: T.append(x)
    if LLM.search(v['title'] + ' ' + v['primary_topic'] + ' ' + ' '.join(v['tags'])): T.append('LLMs')
    if ML_MATH.search(v['title'] + ' ' + v['primary_topic']) and 'AI & ML' not in T: T.append('Math for ML')
    if 'AI & ML' in T or 'LLMs' in T or 'Karpathy' in T:
        if 'AI & ML' not in T: T.append('AI & ML')
    return T or ['Software design & craft']

out, seen = [], set()
for v in vids:                       # best-scored first, so de-duping keeps the better copy
    if not keep(v): continue
    k = norm(v['title'])
    if k in seen: continue
    seen.add(k)
    out.append({'vid': v['vid'], 'title': v['title'], 'channel': v['channel'], 'summary': v['summary'], 'why': v['why_hn'],
                'type': v['content_type'], 'level': v['level'], 'score': v['score'], 'topics': topics(v),
                'recs': v['hn']['recommenders'], 'years': [v['hn']['first_year'], v['hn']['last_year']],
                'quote': (v['quote'] or {}).get('text'), 'quote_url': ('https://news.ycombinator.com/item?id=%s' % v['quote']['hn_comment_id']) if v.get('quote') else None})
json.dump(out, open(os.path.join(HERE, 'data/videos.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
with open(os.path.join(HERE, 'data/curated_list.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['vid','title','channel','topics','score','url'])
    for x in out: w.writerow([x['vid'], x['title'], x['channel'], '|'.join(x['topics']), x['score'], 'https://www.youtube.com/watch?v=' + x['vid']])
c = collections.Counter(t for x in out for t in x['topics'])
print('TOTAL', len(out)); [print(f'  {k:26s}{n}') for k, n in c.most_common()]
