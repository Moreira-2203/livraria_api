import os
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Localizar o arquivo .env
caminho_env = Path(__file__).resolve().parent / ".env"

# Carregar as variaveis
load_dotenv(dotenv_path=caminho_env, override=True)

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

print("Arquivo .env encontrado:", caminho_env.exists())
print("URI:", URI)
print("Usuario:", USER)
print("Senha configurada:", bool(PASSWORD))

try:
    with GraphDatabase.driver(
        URI,
        auth=(USER, PASSWORD)
    ) as driver:

        driver.verify_connectivity()

        print("CONEXAO COM NEO4J REALIZADA COM SUCESSO!")

except Exception as erro:
    print("Falha na conexao:")
    print(type(erro).__name__)
    print(str(erro))