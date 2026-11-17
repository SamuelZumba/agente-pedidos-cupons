from fastapi.testclient import TestClient
from app import app
client=TestClient(app)
def test_menu_create_order_and_lookup(tmp_path,monkeypatch):
 monkeypatch.setenv('DB_PATH',str(tmp_path/'orders.sqlite'))
 assert client.get('/').status_code==200
 assert len(client.get('/api/menu').json()['itens'])==3
 invalid=client.post('/api/orders',json={'itens':[{'id':'p1','quantidade':1}],'cupom':'EXPIRADO'})
 assert invalid.status_code==422
 created=client.post('/api/orders',json={'itens':[{'id':'p1','quantidade':2}],'cupom':'BEMVINDO10'})
 assert created.status_code==201
 order=created.json();assert order['total']<order['subtotal']
 assert client.get('/api/orders/'+order['codigo']).json()['status']=='recebido'
 assert client.post('/tools',json={'ferramenta':'consultar_pedido','argumentos':{'codigo':order['codigo']}}).status_code==200
 assert client.get('/api/orders/DEMO-000').status_code==404
 assert client.post('/api/orders',json={'itens':[{'id':'p3','quantidade':0}]}).status_code==422

def test_rule_uses_requested_id():
 assert 'DEMO-102' in client.post('/ask',json={'mensagem':'status do pedido DEMO-102'}).json()['resposta']

def test_optional_tool_calling_monkeypatched(monkeypatch,tmp_path):
 from app import httpx
 monkeypatch.setenv('OPENAI_API_KEY','FAKE_FOR_TEST_ONLY')
 monkeypatch.setenv('DB_PATH',str(tmp_path/'toolcall.sqlite3'))
 class Response:
  def __init__(self,data):self.data=data
  def raise_for_status(self):pass
  def json(self):return {'choices':[{'message':self.data}]}
 count=[0]
 def mock_post(*args,**kwargs):
  count[0]+=1
  if count[0]==1:
   return Response({'role':'assistant','tool_calls':[{'id':'demo-call','type':'function','function':{'name':'consultar_pedido','arguments':'{"codigo":"DEMO-101"}'}}]})
  return Response({'role':'assistant','content':'O pedido DEMO-101 está em preparo.'})
 monkeypatch.setattr(httpx,'post',mock_post)
 r=client.post('/ask-llm',json={'mensagem':'Status do pedido DEMO-101'})
 assert r.status_code==200
 assert r.json()['modo']=='llm-tool-calling' and r.json()['ferramentas'][0]['ferramenta']=='consultar_pedido'
 assert count[0]==2


def test_static_assets():
 assert client.get('/static/style.css').status_code==200
 assert client.get('/static/app.js').status_code==200
