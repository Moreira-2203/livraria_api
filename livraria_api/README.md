# API REST da Livraria Neo4j

Este projeto reutiliza o banco do notebook migracao_pg_neo4j.ipynb. Nunca execute a limpeza do banco após cadastrar dados novos.

## Preparação no Windows / VS Code

1. Certifique-se de que o Neo4j está ligado na porta 7687 e foi populado pelo notebook.
2. Abra a pasta `livraria_api` no VS Code.
3. Terminal PowerShell: `py -m venv .venv`
4. Ative: `.\.venv\Scripts\Activate.ps1` (alternativa sem ativar: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`).
5. Instale: `python -m pip install -r requirements.txt`
6. Copie `.env.example` para `.env` e informe sua senha real do Neo4j.
7. Execute: `python -m uvicorn main:app --reload`
8. Acesse: http://127.0.0.1:8000/docs

## Rotas

- GET `/livros`
- GET `/livros/{id}`
- POST `/clientes`
- POST `/pedidos`
- GET `/relatorios/mais-vendidos`
- GET `/livros/busca?titulo=Segredo`

Exemplo POST /clientes:

```json
{"nome":"Ana Souza","email":"ana.teste@example.com","cidade":"Saquarema","estado":"RJ"}
```

Exemplo POST /pedidos (substitua os IDs pelos existentes):

```json
{"cliente_id":1,"itens":[{"livro_id":1,"quantidade":2},{"livro_id":2,"quantidade":1}]}
```

## Teste básico

Com a API rodando em um terminal, execute em outro: `python teste_api.py`.

## Observações

- O relatório não conta pedidos com status `cancelado`.
- A rota /livros tem limite padrão de 100 itens; use `?limite=500` para listar 500. Aumente até 5000 se necessário.
- O cadastro gera IDs sequenciais por contadores no próprio grafo; evite escrever clientes/pedidos diretamente fora desta API depois de adotá-la.
- Não suba seu arquivo `.env` com a senha para repositórios públicos.
- O servidor deve usar Neo4j já migrado; o PostgreSQL não é consultado pela API.
