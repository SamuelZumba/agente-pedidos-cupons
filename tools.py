"""Compatibilidade para quem importava tools.py na versão API.
As ferramentas agora são implementadas com SQLite em app.py.
"""
from app import TOOLS,consultar_cardapio,consultar_pedido,verificar_cupom
