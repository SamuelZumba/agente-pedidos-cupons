# Agent Tools Studio — agente de pedidos e cupons

Aplicação web para demonstrar **desenvolvimento Python, tool calling e integrações controladas**. Dados de menu, pedidos e cupons 100% sintéticos.

## Recursos funcionando
- Chat web responsivo com consultas por regras: cardápio, status de pedido por código e cupons.
- Cardápio de demonstração, carrinho com quantidades, cálculo de subtotal, aplicação de cupons com validade/valor mínimo, criação e consulta de pedido fictício em SQLite.
- Rotas `/tools`, `/ask`, `/api/menu`, `/api/orders`, `/api/coupons/{code}` e `/docs`.
- `/ask-llm` permite **tool calling real** com provedor OpenAI-compatível quando a variável `OPENAI_API_KEY` está configurada. Ferramentas e argumentos limitados; o LLM não faz compras nem pagamento.

## Executar
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8002
```
Abra `http://127.0.0.1:8002`. Testes: `.\.venv\Scripts\python.exe -m pytest -q`.

## Dados de teste
Pedidos `DEMO-101`, `DEMO-102`; cupons `BEMVINDO10`, `COMBO15`, `EXPIRADO`. Novos pedidos geram código DEMO-*. Nada é enviado a restaurantes.

## Arquitetura
HTML/CSS/JS → API FastAPI → whitelist de ferramentas → SQLite; ramo opcional LLM com chamadas de ferramenta autorizadas e resultado rastreável.

## Limitações / segurança
Sem autenticação de usuário porque opera somente com dados fictícios. Para publicar na internet, adicione limite por IP, proteção de endpoints de escrita e logs apropriados. Não exponha chave de API no frontend.

## Próximos passos
Autenticação, estados de pedido simulados configuráveis, avaliação de respostas de LLM, testes com provedor externo.
