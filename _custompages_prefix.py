import json,re,urllib.request,time
UA={'User-Agent':'Mozilla/5.0'}
def get(u,t=90):
    for i in range(4):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t).read().decode('utf-8','replace')
        except Exception as e:
            if i==3: return ''
            time.sleep(8)
src=json.load(open('_extra_sources.json'))
NEW=[('hofstra-pride','gohofstra.com','mbb'),('bowling-green-falcons','bgsufalcons.com','mbasketball'),
 ('troy-trojans','troytrojans.com','mbb'),('eastern-michigan-eagles','emueagles.com','mbball'),
 ('uc-riverside-highlanders','gohighlanders.com','MBasketball'),('purdue-fort-wayne-mastodons','gomastodons.com','MBB'),
 ('longwood-lancers','longwoodlancers.com','mbasket'),('iupui-jaguars','iupuijags.com','M-Basketball')]
for key,host,sub in NEW:
    lines=get(f'http://web.archive.org/cdx/search/cdx?url={host}/custompages/*&fl=original&filter=statuscode:200&collapse=urlkey&limit=40000').splitlines()
    # find actual directory path segment matching sub (case-insensitive)
    prefixes={}
    for l in lines:
        m=re.search(rf'(?i)(https?://[^/]+/custompages/(?:[^/?]+/)*?{re.escape(sub)})/',l)
        if m:
            p=re.sub(r'^https?://','',m.group(1)); prefixes[p]=prefixes.get(p,0)+1
    if not prefixes: print(f"{key}: NO MATCH ({len(lines)} custompages urls)"); continue
    best=max(prefixes,key=prefixes.get)
    src[key][3]['cdx']=best+'/*'
    print(f"{key:30s} -> {best}  ({prefixes[best]} files, {len(lines)} total custompages)")
json.dump(src,open('_extra_sources.json','w'),indent=1)
print('updated _extra_sources.json')
