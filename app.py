"""Agent Tools Studio: pedidos/cupom sintéticos, SQL local e tool calling opcional."""
import json, os, re, sqlite3, secrets
from contextlib import contextmanager
from datetime import date,datetime,timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal
import httpx
BASE=Path(__file__).resolve().parent
app=FastAPI(title='Agent Tools Studio | dados sintéticos',version='2.0')
app.mount('/static',StaticFiles(directory=BASE/'static'),name='static')
MENU=[('p1','Bowl Tropical',2990,'Açaí, banana, granola','Leve'),('p2','Wrap Picante',2450,'Frango, pimenta, alface','Salgado'),('p3','Salada Cítrica',2200,'Folhas, laranja, cenoura','Vegano')]
def db_path():return Path(os.getenv('DB_PATH',str(BASE/'data'/'orders.sqlite3')))
@contextmanager
def database():
 path=db_path();path.parent.mkdir(exist_ok=True,parents=True)
 c=sqlite3.connect(path,timeout=10);c.row_factory=sqlite3.Row
 c.executescript("""CREATE TABLE IF NOT EXISTS menu (id TEXT PRIMARY KEY,name TEXT NOT NULL,price_cents INTEGER NOT NULL,ingredients TEXT NOT NULL,category TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS coupons (code TEXT PRIMARY KEY,percent INTEGER NOT NULL,min_cents INTEGER NOT NULL,expires TEXT NOT NULL,active INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS orders (code TEXT PRIMARY KEY,status TEXT NOT NULL,subtotal_cents INTEGER NOT NULL,discount_cents INTEGER NOT NULL,total_cents INTEGER NOT NULL,coupon TEXT,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS order_items (order_code TEXT NOT NULL,menu_id TEXT NOT NULL,quantity INTEGER NOT NULL,unit_price_cents INTEGER NOT NULL);""")
 c.executemany('INSERT OR IGNORE INTO menu VALUES (?,?,?,?,?)',MENU)
 c.executemany('INSERT OR IGNORE INTO coupons VALUES (?,?,?,?,?)',[('BEMVINDO10',10,2000,'2099-12-31',1),('COMBO15',15,3500,'2099-12-31',1),('EXPIRADO',20,2000,'2020-01-01',1)])
 c.execute('INSERT OR IGNORE INTO orders VALUES (?,?,?,?,?,?,?)',('DEMO-101','em preparo',2990,0,2990,None,datetime.now(timezone.utc).isoformat()))
 c.execute('INSERT OR IGNORE INTO orders VALUES (?,?,?,?,?,?,?)',('DEMO-102','a caminho',2450,0,2450,None,datetime.now(timezone.utc).isoformat()))
 c.execute('INSERT OR IGNORE INTO order_items VALUES (?,?,?,?)',('DEMO-101','p1',1,2990)) if not c.execute('SELECT 1 FROM order_items WHERE order_code=?',('DEMO-101',)).fetchone() else None
 c.execute('INSERT OR IGNORE INTO order_items VALUES (?,?,?,?)',('DEMO-102','p2',1,2450)) if not c.execute('SELECT 1 FROM order_items WHERE order_code=?',('DEMO-102',)).fetchone() else None
 c.commit()
 try:yield c;c.commit()
 except:c.rollback();raise
 finally:c.close()
def cents_to_real(n):return float((Decimal(n)/100).quantize(Decimal('0.01')))
def consultar_cardapio():
 with database() as c:rows=c.execute('SELECT * FROM menu ORDER BY id').fetchall()
 return {'itens':[{'id':r['id'],'nome':r['name'],'preco':cents_to_real(r['price_cents']),'ingredientes':r['ingredients'].split(', '),'categoria':r['category']} for r in rows],'dados':'sinteticos'}
def consultar_pedido(codigo):
 codigo=codigo.upper().strip()
 if not re.fullmatch(r'DEMO-[A-Z0-9]{3,16}',codigo):return {'erro':'Código inválido; use DEMO-101, DEMO-102 ou um código gerado nesta demo.'}
 with database() as c:
  r=c.execute('SELECT * FROM orders WHERE code=?',(codigo,)).fetchone()
  if not r:return {'erro':'Pedido demonstrativo não encontrado'}
  rows=c.execute('SELECT menu_id,quantity FROM order_items WHERE order_code=?',(codigo,)).fetchall()
 return {'codigo':r['code'],'status':r['status'],'subtotal':cents_to_real(r['subtotal_cents']),'desconto':cents_to_real(r['discount_cents']),'total':cents_to_real(r['total_cents']),'itens':[{'id':x['menu_id'],'quantidade':x['quantity']} for x in rows],'dados':'sinteticos'}
def verificar_cupom(codigo,subtotal_cents=None):
 code=codigo.upper().strip()
 if not re.fullmatch(r'[A-Z0-9]{3,24}',code):return {'ativo':False,'motivo':'Código inválido'}
 with database() as c:r=c.execute('SELECT * FROM coupons WHERE code=?',(code,)).fetchone()
 if not r:return {'ativo':False,'motivo':'Cupom não encontrado'}
 active=bool(r['active']) and date.fromisoformat(r['expires'])>=date.today()
 if not active:return {'ativo':False,'motivo':'Cupom expirado ou inativo'}
 valid_cart=subtotal_cents is None or subtotal_cents>=r['min_cents']
 result={'ativo':valid_cart,'codigo':code,'desconto_percentual':r['percent'],'valor_minimo':cents_to_real(r['min_cents']),'dados':'sinteticos'}
 if not valid_cart:result['motivo']='Valor mínimo não atingido'
 return result
TOOLS={'consultar_cardapio':consultar_cardapio,'consultar_pedido':consultar_pedido,'verificar_cupom':verificar_cupom}
class ToolRequest(BaseModel):
 ferramenta:str
 argumentos:dict=Field(default_factory=dict)
class AskRequest(BaseModel):
 mensagem:str=Field(min_length=2,max_length=500)
class OrderItem(BaseModel):
 id:Literal['p1','p2','p3']
 quantidade:int=Field(ge=1,le=8)
class OrderRequest(BaseModel):
 itens:list[OrderItem]=Field(min_length=1,max_length=10)
 cupom:str|None=Field(None,max_length=24)

def build_order(q:OrderRequest):
 ids=[x.id for x in q.itens]
 if len(ids)!=len(set(ids)):raise HTTPException(422,'Envie cada produto apenas uma vez.')
 with database() as c:
  menu={x['id']:x for x in c.execute('SELECT * FROM menu').fetchall()}
 subtotal=sum(menu[x.id]['price_cents']*x.quantidade for x in q.itens)
 coupon=None;discount=0
 if q.cupom:
  coupon=verificar_cupom(q.cupom,subtotal)
  if not coupon['ativo']:raise HTTPException(422,coupon.get('motivo','Cupom inválido'))
  discount=int((Decimal(subtotal)*Decimal(coupon['desconto_percentual'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
 code='DEMO-'+secrets.token_hex(4).upper()
 with database() as c:
  c.execute('INSERT INTO orders VALUES (?,?,?,?,?,?,?)',(code,'recebido',subtotal,discount,subtotal-discount,coupon['codigo'] if coupon else None,datetime.now(timezone.utc).isoformat()))
  c.executemany('INSERT INTO order_items VALUES (?,?,?,?)',[(code,x.id,x.quantidade,menu[x.id]['price_cents']) for x in q.itens])
 return consultar_pedido(code)

@app.middleware('http')
async def headers(request,call_next):
 r=await call_next(request)
 r.headers['X-Content-Type-Options']='nosniff';r.headers['X-Frame-Options']='DENY'
 r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
 return r
@app.get('/')
def homepage():return FileResponse(BASE/'templates'/'index.html')
@app.get('/health')
def health():return {'status':'ok','modo':'sintetico'}
@app.get('/api/menu')
def menu():return consultar_cardapio()
@app.get('/api/orders/{code}')
def get_order(code:str):
 r=consultar_pedido(code)
 if 'erro' in r:raise HTTPException(404,r['erro'])
 return r
@app.post('/api/orders',status_code=201)
def create_order(payload:OrderRequest):return build_order(payload)
@app.get('/api/coupons/{code}')
def get_coupon(code:str):return verificar_cupom(code)
@app.post('/tools')
def call_tool(req:ToolRequest):
 fn=TOOLS.get(req.ferramenta)
 if not fn:raise HTTPException(400,'Ferramenta não permitida')
 expected={'consultar_cardapio':set(),'consultar_pedido':{'codigo'},'verificar_cupom':{'codigo'}}[req.ferramenta]
 if set(req.argumentos)!=expected:raise HTTPException(422,'Argumentos incompatíveis')
 try:res=fn(**req.argumentos)
 except (TypeError,ValueError) as e:raise HTTPException(422,'Argumentos inválidos') from e
 return {'ferramenta':req.ferramenta,'resultado':res}
@app.post('/ask')
def ask(req:AskRequest):
 msg=req.mensagem.lower().strip()
 if 'cardapio' in msg or 'cardápio' in msg or 'menu' in msg:
  res=consultar_cardapio();fn='consultar_cardapio';reply='Encontrei 3 pratos no cardápio demonstrativo.'
 elif 'cupom' in msg or 'desconto' in msg:
  codes=re.findall(r'\b(?:BEMVINDO10|COMBO15|EXPIRADO)\b',req.mensagem.upper())
  code=codes[0] if codes else 'BEMVINDO10';res=verificar_cupom(code);fn='verificar_cupom';reply=f'Consultei o cupom {code}. '+('Está ativo nesta demo.' if res.get('ativo') else res.get('motivo','Não está ativo.'))
 elif 'pedido' in msg or 'status' in msg:
  codes=re.findall(r'DEMO-[A-Z0-9]+',req.mensagem.upper());code=codes[0] if codes else 'DEMO-101'
  res=consultar_pedido(code);fn='consultar_pedido';reply=f'Pedido {code}: '+(res.get('status') or res.get('erro','Não encontrado'))
 else:return {'resposta':'Posso consultar cardápio, status do pedido DEMO-101 ou cupom BEMVINDO10.','modo':'regras-sem-llm','ferramenta':None,'resultado':None}
 return {'resposta':reply,'ferramenta':fn,'resultado':res,'modo':'regras-sem-llm'}
@app.post('/ask-llm')
def ask_llm(req:AskRequest):
 """Tool calling real com provedor OpenAI-compatível; nunca executa ações de compra."""
 key=os.getenv('OPENAI_API_KEY')
 if not key:raise HTTPException(503,'Configure OPENAI_API_KEY para ativar o modelo externo.')
 schemas=[{'type':'function','function':{'name':name,'description':desc,'parameters':{'type':'object','properties':props,'required':list(props),'additionalProperties':False}}} for name,desc,props in [
  ('consultar_cardapio','Consultar cardápio da demonstração',{}),('consultar_pedido','Consultar pedido fictício por código',{'codigo':{'type':'string'}}),('verificar_cupom','Consultar cupom fictício por código',{'codigo':{'type':'string'}})]]
 url=os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1').rstrip('/')+'/chat/completions'
 messages=[{'role':'system','content':'Você é um assistente para DEMONSTRAÇÕES. Utilize apenas ferramentas para afirmar dados de cardápio, pedido ou cupons. Não invente valores, não faça pedidos nem processe pagamentos.'},{'role':'user','content':req.mensagem}]
 def post(msgs,tools=None):
  payload={'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'messages':msgs,'temperature':0}
  if tools:payload['tools']=tools
  try:
   resp=httpx.post(url,headers={'Authorization':'Bearer '+key},json=payload,timeout=25);resp.raise_for_status()
   return resp.json()['choices'][0]['message']
  except (httpx.HTTPError,KeyError,IndexError,ValueError) as e:raise HTTPException(502,'Falha no provedor externo de IA.') from e
 first=post(messages,schemas);calls=first.get('tool_calls',[])
 if not calls:return {'resposta':first.get('content') or 'Sem resposta.','modo':'llm-tool-calling','ferramentas':[]}
 if len(calls)>3:raise HTTPException(502,'O modelo solicitou ferramentas demais.')
 messages.append(first);traces=[]
 for call in calls:
  name=call.get('function',{}).get('name','')
  params=call.get('function',{}).get('arguments','{}')
  try:args=json.loads(params)
  except (ValueError,TypeError):args={}
  if not isinstance(args,dict) or name not in TOOLS or set(args)!={'consultar_cardapio':set(),'consultar_pedido':{'codigo'},'verificar_cupom':{'codigo'}}.get(name,set()):res={'erro':'Ferramenta ou argumentos inválidos'}
  else:
   try:res=TOOLS[name](**args)
   except (TypeError,ValueError):res={'erro':'Argumentos inválidos'}
  traces.append({'ferramenta':name,'resultado':res})
  messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(res,ensure_ascii=False)})
 answer=post(messages)
 return {'resposta':answer.get('content') or 'Sem resposta.','modo':'llm-tool-calling','ferramentas':traces}
