import json,re,urllib.request,time,os
from collections import Counter
UA={'User-Agent':'Mozilla/5.0'}
def get(u,t=90):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t).read().decode('utf-8','replace')
        except Exception:
            if i==2: return ''
            time.sleep(6)
cen=json.load(open('_domain_census_results.json'))
def box(e,k):
    v=e['patterns'].get(k,{}).get('boxes',0); return v or 0
done={'hawaiiathletics.com','gohofstra.com','bgsufalcons.com','static.virginiasports.com','rmucolonials.com',
'isubengals.com','iupuijags.com','static.goprincetontigers.com','gohighlanders.com','static.umterps.com',
'static.usctrojans.com','static.broncosports.com','static.gohuskies.com','njithighlanders.com',
'static.hawkeyesports.com','goviks.com','static.sjsuspartans.com','static.hawaiiathletics.com',
'gomastodons.com','troytrojans.com','emueagles.com','hbuhuskies.com','static.goviks.com',
'static.wagnerathletics.com','nccueaglepride.com','static.rmucolonials.com','static.gohofstra.com',
'static.ukathletics.com','bamastatesports.com','gocsucougars.com','static.goducks.com','longwoodlancers.com'}
todo=[]
for e in cen:
    cp=box(e,'custompages'); sport=max(box(e,'m-baskbl'),box(e,'bko'),box(e,'mbb-boxes'))
    if cp>=15 and sport==0 and e['host'] not in done:
        todo.append((cp,e['host'],(e['programs'] or ['?'])[0]))
todo.sort(reverse=True)
print(f'{len(todo)} unexplored custompages hosts\n')
MEN=re.compile(r"(?i)^(m[-_ ]?(baskbl|bask|bball|bb|bkb|basketball|ball)|mens?%?2?0?basketball|men's%20basketball|mbk\w*|mbb\w*)$")
WOM=re.compile(r"(?i)wom|^w[-_]|wbb|wball|wbkb|wbask|wvb")
out={}
for cp,host,prog in todo:
    lines=get(f'http://web.archive.org/cdx/search/cdx?url={host}/custompages/*&fl=original&filter=statuscode:200&collapse=urlkey&limit=40000').splitlines()
    segs=Counter()
    for l in lines:
        for s in re.findall(r'/([^/?]+)(?=/)',l): segs[s]+=1
    cands=[(s,n) for s,n in segs.most_common() if MEN.match(s) and not WOM.search(s)]
    if not cands:
        print(f'{prog[:26]:26s} {host[:28]:28s} urls={len(lines):5d} -> none'); continue
    sub=cands[0][0]; pref=Counter()
    for l in lines:
        m=re.search(rf'(?i)(https?://[^/]+/custompages/(?:[^/?]+/)*?{re.escape(sub)})/',l)
        if m: pref[re.sub(r'^https?://','',m.group(1)).replace(':80','').replace('www.','')]+=1
    if not pref: continue
    best=max(pref,key=pref.get)
    out[prog]={'host':host,'sub':sub,'prefix':best,'files':pref[best]}
    print(f'{prog[:26]:26s} {host[:28]:28s} -> {best[:52]:52s} ({pref[best]} files)')
json.dump(out,open('_custompages_round3.json','w'),indent=1)
print(f'\nsaved _custompages_round3.json: {len(out)} programs, {sum(v["files"] for v in out.values())} files')
