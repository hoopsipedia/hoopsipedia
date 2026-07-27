import json,re,urllib.request,time
from collections import Counter
UA={'User-Agent':'Mozilla/5.0'}
def get(u,t=90):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t).read().decode('utf-8','replace')
        except Exception:
            if i==2: return ''
            time.sleep(6)
cen=json.load(open('_domain_census_results.json'))
src=json.load(open('_extra_sources.json'))
used={re.sub(r'^(https?://)?(www\.)?','',v[3]['cdx']).split('/')[0].replace(':80','') for v in src.values()}
def box(e,k):
    v=e['patterns'].get(k,{}).get('boxes',0); return v or 0
todo=[]
for e in cen:
    h=e['host']
    if h in used: continue
    if box(e,'custompages')>=20 and max(box(e,'m-baskbl'),box(e,'bko'),box(e,'mbb-boxes'))==0:
        todo.append((box(e,'custompages'),h,(e['programs'] or ['?'])[0]))
todo.sort(reverse=True)
# PREFIX match (was anchored before, which missed season-suffixed dirs like
# "MBB1011", "mbbsco_200304", "MBB1314")
MEN=re.compile(r'(?i)^(m[-_ ]?(baskbl|bask|bball|bb|bkb|basketball)|mens?[-_ %20]*basketball)')
WOM=re.compile(r'(?i)wom|^w[-_]|^wb|wvb|wten')
out={}
print(f'{len(todo)} hosts to probe\n')
for cp,host,prog in todo:
    lines=get(f'http://web.archive.org/cdx/search/cdx?url={host}/custompages/*&fl=original&filter=statuscode:200&collapse=urlkey&limit=40000').splitlines()
    if not lines: continue
    segs=Counter()
    for l in lines:
        for s in re.findall(r'/([^/?]+)(?=/)',l):
            if MEN.match(s) and not WOM.search(s): segs[s]+=1
    if not segs: print(f'{prog[:24]:24s} {host[:28]:28s} -> none'); continue
    # group by the PARENT dir holding these season dirs, so one source covers all
    parents=Counter()
    for l in lines:
        m=re.search(r'(?i)(https?://[^/]+/custompages/(?:[^/?]+/)*?)(' + '|'.join(re.escape(s) for s in list(segs)[:40]) + r')/',l)
        if m: parents[re.sub(r'^https?://','',m.group(1)).replace(':80','').replace('www.','').rstrip('/')]+=1
    if not parents: continue
    best=max(parents,key=parents.get)
    out[prog]={'host':host,'prefix':best,'files':parents[best],'dirs':list(segs)[:5]}
    print(f'{prog[:24]:24s} {host[:28]:28s} -> {best[:50]:50s} ({parents[best]} files) dirs={list(segs)[:3]}')
json.dump(out,open('_custompages_round4.json','w'),indent=1)
print(f'\nsaved: {len(out)} programs, {sum(v["files"] for v in out.values())} files')
