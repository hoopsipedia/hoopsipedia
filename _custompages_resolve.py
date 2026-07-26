import harvest_statcrew as H,re,json
CHK=[('hofstra-pride','Hofstra Pride','2275','gohofstra.com','mbb','0220hof.htm'),
 ('bowling-green-falcons','Bowling Green Falcons','189','bgsufalcons.com','mbasketball','bg-mich.htm'),
 ('troy-trojans','Troy Trojans','2653','troytrojans.com','mbb','game1.htm'),
 ('eastern-michigan-eagles','Eastern Michigan Eagles','2199','emueagles.com','mbball','mgame-13.htm'),
 ('uc-riverside-highlanders','UC Riverside Highlanders','27','gohighlanders.com','MBasketball','UCRMBK06.HTM'),
 ('purdue-fort-wayne-mastodons','Purdue Fort Wayne Mastodons','2870','gomastodons.com','MBB','0102fwpn.htm'),
 ('longwood-lancers','Longwood Lancers','2344','longwoodlancers.com','mbasket','bc1208.htm'),
 ('iupui-jaguars','IU Indianapolis Jaguars','85','iupuijags.com','M-Basketball','110213.htm')]
def q(u):
    import urllib.request
    try: return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=45).read().decode('utf-8','replace')
    except: return ''
cfg={}
for key,name,tid,host,sub,fn in CHK:
    prefix=None
    for pfx in (f'custompages/{sub}',f'custompages/stats/{sub}',f'custompages/Stats/{sub}'):
        r=q(f'http://web.archive.org/cdx/search/cdx?url={host}/{pfx}/{fn}&fl=timestamp,original&filter=statuscode:200&limit=1')
        if r.strip(): prefix=pfx; row=r.split('\n')[0].split(' ',1); break
    if not prefix: print(f"{name}: NO PATH"); continue
    ts,orig=row
    t=q(f'http://web.archive.org/web/{ts}id_/{orig}')
    g=H.parse_statcrew(t)
    boxname=g['teams'][0]['name'] if g else '?'
    # cdx path uses the actual case of prefix as found; keep {sub} case
    cfg[key]=[tid,name,f"{host} (Wayback)",{'cdx':f"{host}/{prefix}/*","file_re":rf"(?i)/{re.escape(sub)}/(?!team|report|roster|index|schedule|plyr|cume|high|gbg|tow)[^/]+\.html?$","mode":"wayback"}]
    print(f"{name:26s} path={prefix:26s} box_team0={boxname!r}  date={g['date'] if g else None}")
json.dump(cfg,open('_custompages_new_sources.json','w'),indent=1)
print('\nsaved _custompages_new_sources.json ('+str(len(cfg))+' programs)')
