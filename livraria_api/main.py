import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from dotenv import load_dotenv

# Carregar configuracoes do Neo4j
load_dotenv(
    dotenv_path=Path(__file__).resolve().parent / ".env",
    override=True
)

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not PASSWORD:
        raise RuntimeError('Configure NEO4J_PASSWORD no arquivo .env')
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    app.state.driver = driver
    yield
    driver.close()

app = FastAPI(title='API Livraria Neo4j', version='1.0.0', lifespan=lifespan)

class ClienteEntrada(BaseModel):
    nome: str = Field(min_length=2)
    email: str = Field(min_length=5)
    cidade: str
    estado: str = Field(min_length=2, max_length=2)

class ItemPedido(BaseModel):
    livro_id: int = Field(gt=0)
    quantidade: int = Field(gt=0)

class PedidoEntrada(BaseModel):
    cliente_id: int = Field(gt=0)
    itens: list[ItemPedido] = Field(min_length=1)


def ler(tx, query, **params):
    return [r.data() for r in tx.run(query, **params)]

@app.get('/livros')
def listar_livros(limite: Annotated[int, Query(ge=1, le=5000)] = 100):
    q = '''MATCH (l:Livro)
           RETURN l.id AS id, l.titulo AS titulo, l.preco AS preco,
                  l.isbn AS isbn ORDER BY id LIMIT $limite'''
    with app.state.driver.session(database=DATABASE) as s:
        return s.execute_read(ler, q, limite=limite)

@app.get('/livros/busca')
def buscar_livros(titulo: Annotated[str, Query(min_length=1)]):
    q = '''MATCH (l:Livro)
           WHERE toLower(l.titulo) CONTAINS toLower($titulo)
           RETURN l.id AS id, l.titulo AS titulo, l.preco AS preco
           ORDER BY titulo LIMIT 100'''
    with app.state.driver.session(database=DATABASE) as s:
        return s.execute_read(ler, q, titulo=titulo)

@app.get('/livros/{id}')
def detalhar_livro(id: int):
    q = '''MATCH (l:Livro {id:$id})
           OPTIONAL MATCH (l)-[:ESCRITO_POR]->(a:Autor)
           OPTIONAL MATCH (l)-[:PERTENCE_A]->(c:Categoria)
           RETURN l.id AS id, l.titulo AS titulo, l.preco AS preco,
                  l.isbn AS isbn, l.ano_publicacao AS ano_publicacao,
                  a.nome AS autor, c.nome AS categoria'''
    with app.state.driver.session(database=DATABASE) as s:
        linhas = s.execute_read(ler, q, id=id)
    if not linhas:
        raise HTTPException(404, 'Livro não encontrado')
    return linhas[0]

@app.post('/clientes', status_code=201)
def criar_cliente(cliente: ClienteEntrada):
    def gravar(tx):
        email = cliente.email.strip().lower()
        if tx.run('MATCH (c:Cliente {email:$email}) RETURN c.id AS id LIMIT 1', email=email).single():
            return None
        # contador singleton: requer que as escritas de clientes passem por esta API
        tx.run('MERGE (seq:Sequencia {nome:"cliente"}) ON CREATE SET seq.valor=0')
        row = tx.run('''MATCH (seq:Sequencia {nome:"cliente"})
                        SET seq.valor = CASE WHEN seq.valor < $base THEN $base + 1 ELSE seq.valor + 1 END
                        WITH seq
                        CREATE (c:Cliente {id:seq.valor, nome:$nome, email:$email,
                                          cidade:$cidade, estado:$estado, membro_desde:toString(date())})
                        RETURN c.id AS id, c.nome AS nome, c.email AS email''',
                     base=tx.run('MATCH (c:Cliente) RETURN coalesce(max(c.id),0) AS maior').single()['maior'],
                     nome=cliente.nome, email=email, cidade=cliente.cidade,
                     estado=cliente.estado.upper()).single()
        return row.data()
    with app.state.driver.session(database=DATABASE) as s:
        resultado=s.execute_write(gravar)
    if resultado is None: raise HTTPException(409,'E-mail já cadastrado')
    return resultado

@app.post('/pedidos', status_code=201)
def criar_pedido(pedido: PedidoEntrada):
    ids = [i.livro_id for i in pedido.itens]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, 'Não repita livro_id no mesmo pedido; ajuste a quantidade')
    def gravar(tx):
        if not tx.run('MATCH (c:Cliente {id:$id}) RETURN c',id=pedido.cliente_id).single():
            return ('cliente',None)
        encontrados = tx.run('MATCH (l:Livro) WHERE l.id IN $ids RETURN collect(l.id) AS ids',ids=ids).single()['ids']
        ausentes=sorted(set(ids)-set(encontrados))
        if ausentes: return ('livros',ausentes)
        tx.run('MERGE (seq:Sequencia {nome:"pedido"}) ON CREATE SET seq.valor=0')
        maior=tx.run('MATCH (p:Pedido) RETURN coalesce(max(p.id),0) AS maior').single()['maior']
        row=tx.run('''MATCH (seq:Sequencia {nome:"pedido"})
                      SET seq.valor=CASE WHEN seq.valor<$base THEN $base+1 ELSE seq.valor+1 END
                      WITH seq
                      MATCH (c:Cliente {id:$cliente_id})
                      CREATE (p:Pedido {id:seq.valor, data_pedido:toString(datetime()),
                                        total:0.0, status:'processando'})
                      CREATE (p)-[:FEITO_POR]->(c)
                      RETURN p.id AS id''',base=maior,cliente_id=pedido.cliente_id).single()
        pedido_id=row['id']
        itens=[i.model_dump() for i in pedido.itens]
        total=tx.run('''MATCH (p:Pedido {id:$pedido_id})
                        UNWIND $itens AS item
                        MATCH (l:Livro {id:item.livro_id})
                        CREATE (p)-[:CONTEM {livro_id:item.livro_id,
                                quantidade:item.quantidade, preco_unitario:l.preco}]->(l)
                        WITH p, sum(item.quantidade*l.preco) AS total
                        SET p.total=total
                        RETURN p.total AS total''',pedido_id=pedido_id,itens=itens).single()['total']
        return ('ok',{'pedido_id':pedido_id, 'cliente_id':pedido.cliente_id,'total':total})
    with app.state.driver.session(database=DATABASE) as s:
        tipo,valor=s.execute_write(gravar)
    if tipo=='cliente':raise HTTPException(404,'Cliente não encontrado')
    if tipo=='livros':raise HTTPException(404,{'livros_nao_encontrados':valor})
    return valor

@app.get('/relatorios/mais-vendidos')
def mais_vendidos(limite: Annotated[int,Query(ge=1,le=100)] = 10):
    q = '''MATCH (p:Pedido)-[r:CONTEM]->(l:Livro)
           WHERE p.status <> 'cancelado'
           RETURN l.id AS livro_id, l.titulo AS titulo,
                  sum(r.quantidade) AS unidades_vendidas,
                  round(sum(r.quantidade * r.preco_unitario),2) AS faturamento
           ORDER BY unidades_vendidas DESC, faturamento DESC LIMIT $limite'''
    with app.state.driver.session(database=DATABASE) as s:
        return s.execute_read(ler,q,limite=limite)
