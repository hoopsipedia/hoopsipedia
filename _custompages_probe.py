import json,re,harvest_statcrew as H
PROG=[
 ('hofstra-pride','Hofstra Pride','gohofstra.com','mbb'),
 ('bowling-green-falcons','Bowling Green Falcons','bgsufalcons.com','mbasketball'),
 ('troy-trojans','Troy Trojans','troytrojans.com','mbb'),
 ('eastern-michigan-eagles','Eastern Michigan Eagles','emueagles.com','mbball'),
 ('uc-riverside-highlanders','UC Riverside Highlanders','gohighlanders.com','MBasketball'),
 ('purdue-fort-wayne-mastodons','Purdue Fort Wayne Mastodons','gomastodons.com','MBB'),
 ('longwood-lancers','Longwood Lancers','longwoodlancers.com','mbasket'),
 ('iupui-jaguars','IU Indianapolis Jaguars','iupuijags.com','M-Basketball'),
]
for key,name,host,sub in PROG:
    u=f'http://web.archive.org/cdx/search/cdx?url={host}/custompages/*&fl=timestamp,original&filter=statuscode:200&collapse=urlkey&limit=8000'
    all_rows=[l.split(' ',1) for l in H.get_retry(u).decode().splitlines() if l.strip()]
    rows=[r for r in all_rows if re.search(rf'/{re.escape(sub)}/',r[1],re.I)]
    # test-parse a spread, note which parse (game) vs not (teamstat/roster)
    ok=fail=0; games=[]; nongames=[]
    test=rows[:8]+rows[len(rows)//2:len(rows)//2+8]+rows[-6:]
    for ts,orig in test:
        fn=orig.split('/')[-1].split('?')[0]
        try: t=H.get(f'http://web.archive.org/web/{ts}id_/{orig}',timeout=40).decode('utf-8','replace')
        except: continue
        r=H.parse_statcrew(t)
        if r: ok+=1; games.append(fn)
        else: fail+=1; nongames.append(fn)
    print(f"{name[:24]:24s} {sub:12s} files={len(rows):4d} parsed {ok}/{ok+fail}")
    print(f"    GAMES: {games[:6]}")
    print(f"    non:   {nongames[:6]}")
