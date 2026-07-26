import json,re,urllib.request,time
from collections import Counter
UA={'User-Agent':'Mozilla/5.0'}
def get(u,t=90):
    for i in range(4):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t).read().decode('utf-8','replace')
        except Exception:
            if i==3: return ''
            time.sleep(8)
HOSTS=[('Virginia Cavaliers','static.virginiasports.com'),('Idaho State Bengals','isubengals.com'),
 ('Princeton Tigers','static.goprincetontigers.com'),('USC Trojans','static.usctrojans.com'),
 ('Boise State Broncos','static.broncosports.com'),('NJIT Highlanders','njithighlanders.com'),
 ('Iowa Hawkeyes','static.hawkeyesports.com'),('Portland State Vikings','goviks.com'),
 ('San Jose State Spartans','static.sjsuspartans.com'),('Wagner Seahawks','static.wagnerathletics.com'),
 ('North Carolina Central Eagles','nccueaglepride.com'),('Oregon Ducks','static.goducks.com'),
 ('Robert Morris Colonials','rmucolonials.com'),('Houston Christian Huskies','hbuhuskies.com'),
 ('Chicago State Cougars','gocsucougars.com'),('Kentucky Wildcats','static.ukathletics.com'),
 ('Maryland Terrapins','static.umterps.com'),('Washington Huskies','static.gohuskies.com')]
# broad men's-basketball dir names; exclude women's
MEN=re.compile(r"(?i)^(m[-_]?(baskbl|bask|bball|bb|bkb|basketball|ball)|mens?%?2?0?basketball|men's%20basketball|mbk\w*|m-baskbl)$")
WOM=re.compile(r"(?i)wom|^w[-_]|wbb|wball|wbkb|wbask")
out={}
for name,host in HOSTS:
    lines=get(f'http://web.archive.org/cdx/search/cdx?url={host}/custompages/*&fl=original&filter=statuscode:200&collapse=urlkey&limit=40000').splitlines()
    segs=Counter()
    for l in lines:
        for s in re.findall(r'/([^/?]+)(?=/)',l):
            segs[s]+=1
    cands=[(s,n) for s,n in segs.most_common() if MEN.match(s) and not WOM.search(s)]
    print(f"{name[:28]:28s} {host[:30]:30s} urls={len(lines):5d} cands={cands[:3]}")
    if cands:
        sub=cands[0][0]
        # exact deepest prefix containing that segment
        pref=Counter()
        for l in lines:
            m=re.search(rf'(?i)(https?://[^/]+/custompages/(?:[^/?]+/)*?{re.escape(sub)})/',l)
            if m: pref[re.sub(r'^https?://','',m.group(1)).replace(':80','').replace('www.','')]+=1
        if pref:
            best=max(pref,key=pref.get)
            out[name]={'host':host,'sub':sub,'prefix':best,'files':pref[best]}
            print(f"    -> {best}  ({pref[best]} files)")
json.dump(out,open('_custompages_round2.json','w'),indent=1)
print('\nsaved _custompages_round2.json:',len(out),'programs')
