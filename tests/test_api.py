from fastapi.testclient import TestClient
from app import app
c=TestClient(app)
def test_health(): assert c.get('/health').status_code==200
def test_cardapio(): assert len(c.post('/tools',json={'ferramenta':'consultar_cardapio','argumentos':{}}).json()['resultado']['itens'])==3
def test_reject_unknown(): assert c.post('/tools',json={'ferramenta':'executar_shell','argumentos':{}}).status_code==400
def test_reject_extra_args(): assert c.post('/tools',json={'ferramenta':'consultar_pedido','argumentos':{'codigo':'DEMO-101','admin':1}}).status_code==422
def test_demo(): assert c.post('/ask',json={'mensagem':'quero ver o cardápio'}).json()['modo']=='regras-sem-llm'
