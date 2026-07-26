import json,re,sys,urllib.request,time
from collections import Counter
UA={'User-Agent':'Mozilla/5.0'}
def get(u,t=90):
    for i in range(4):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t).read().decode('utf-8','replace')
        except Exception as e:
            if i==3: return ''
            time.sleep(8)
targets=json.load(open('_custompages_targets.json'))
# dedupe by program, keep highest-count host
best={}
for r in targets:
    p=r['program']
    if p not in best or r['custompages']>best[p]['custompages']: best[p]=r
MBB=re.compile(r'(m).{0,2}(bb|bsk|bkb|bball|basket)',re.I)
VB=re.compile(r'v.?b|vball|volley',re.I)
out=[]
for p,r in sorted(best.items(),key=lambda x:-x[1]['custompages']):
    host=r['host']
    u=f'http://web.archive.org/cdx/search/cdx?url={host}/custompages/*&fl=original&filter=statuscode:200&collapse=urlkey&limit=8000'
    lines=get(u).splitlines()
    seg=Counter()
    for l in lines:
        m=re.search(r'/custompages/(?:stats/)?([^/?]+)/',l,re.I)
        if m: seg[m.group(1)]+=1
    # find MBB subdir: matches MBB pattern, not volleyball
    cands=[(c,n) for c,n in seg.most_common() if MBB.search(c) and not VB.search(c)]
    pick=cands[0] if cands else None
    sample=''
    if pick:
        for l in lines:
            if re.search(rf'/{re.escape(pick[0])}/',l,re.I): sample=l.split('id_/')[-1] if 'id_' in l else l; break
    out.append({'program':p,'host':host,'mbb_subdir':pick[0] if pick else None,'mbb_files':pick[1] if pick else 0,'sample':sample.split('/')[-3:] if sample else None,'all_subdirs':[c for c,_ in seg.most_common(8)]})
    print(f"{r['custompages']:5d} {p[:28]:28s} {host[:30]:30s} -> {pick[0] if pick else 'NONE':12s} ({pick[1] if pick else 0} files)  {sample.split('/')[-1] if sample else ''}")
json.dump(out,open('_custompages_discovered.json','w'),indent=1)
print('\nsaved _custompages_discovered.json')
