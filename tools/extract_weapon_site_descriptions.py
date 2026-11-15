import sys,re,json,zipfile,collections,html
from html.parser import HTMLParser
sys.path.insert(0,'tools');from weapons2cards import Companion
c=Companion();ids=sum([json.load(open('data/weapons/'+p)) for p in ['small-guns-order.json','heavy-guns-order.json','energy-guns-order.json','melee-original-order.json']],[])+sum(json.load(open('data/weapons/remaining-order.json')).values(),[])
with zipfile.ZipFile('jos_sppagebuilder.zip') as z:d=json.loads(z.read('jos_sppagebuilder.json'))[2]['data']
def norm(s):return re.sub(r'[^а-яa-z0-9]','',s.lower().replace('ё','е'))
by=collections.defaultdict(list); by_id={x['id']:x for x in d}
for x in d:by[norm(x['title'])].append(x)
alias={'weapon_44_pistol':'94','weapon_combat_rifle':'99','weapon_submachine_gun':'105','weapon_25mm_grenade_apw':'142','weapon_battle_rifle':'145','weapon_black_powder_rifle':'148','weapon_pistol_injector':'185','weapon_sten_injector':'359','weapon_alien_atomizer':'263','weapon_alien_disintegrator':'264','weapon_alien_blaster':'271','weapon_arc_welder':'265','weapon_baseball_bat_aluminum':'165','weapon_institute_laser':'140','weapon_pulse_mine':'210','weapon_mining_drill':'369','weapon_cryogenic_grenade':'211'}
class Parser(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
 def handle_data(self,data):self.parts.append(data)
 def handle_starttag(self,tag,attrs):
  if tag in ('p','br','li','h3','h4'):self.parts.append('\n')
 def handle_endtag(self,tag):
  if tag in ('p','li','h3','h4'):self.parts.append('\n')
 def text(self):
  v=''.join(self.parts).replace('\xa0',' ').replace('{/CD}',' БК ')
  return '\n\n'.join(re.sub(r'\s+',' ',x).strip() for x in re.split(r'\n+',v) if x.strip()).strip()
result={};mapping={};skipped={}
for wid in ids:
 matches=by[norm(c.weapon_name(wid))];row=by_id.get(alias[wid]) if wid in alias else matches[0] if len(matches)==1 else None
 if not row or not row.get('content'): skipped[wid]='нет однозначной страницы';continue
 try:
  sections=json.loads(row['content']);texts=[]
  for col in sections[2].get('columns',[]):
   for addon in col.get('addons',[]):
    t=addon.get('settings',{}).get('text','')
    if isinstance(t,str) and len(t)>=40 and '<table' not in t.lower():
     p=Parser();p.feed(t);v=p.text()
     if len(v)>30:texts.append(v)
  if len(texts)!=1:skipped[wid]=f'найдено текстовых блоков: {len(texts)}';continue
  v=texts[0]
  # Special rules for these are already maintained separately by the renderer.
  if wid in ('weapon_laser_musket','weapon_alien_blaster','weapon_assaultron_head_laser'):
   v=re.split(r'Особенности?\s*:',v, maxsplit=1, flags=re.I)[0].strip()
  if re.search(r'\{[^}]+\}',v):skipped[wid]='обнаружен шорткод';continue
  if wid == 'weapon_mining_drill':
   v = v.replace('горнодобывающая дрель', 'шахтёрский бур').replace('В дрель встроена', 'В бур встроена')
  result[wid]=v;mapping[wid]={'site_page_id':row['id'],'site_title':row['title'].strip()}
 except (ValueError,IndexError,AttributeError,TypeError) as e:skipped[wid]=str(e)
open('data/weapons/descriptions-site-candidates.ru.json','w').write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
open('data/weapons/descriptions-site-map.json','w').write(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
print('imported',len(result),'skipped',len(skipped));print(skipped)
