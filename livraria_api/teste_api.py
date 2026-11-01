import requests
BASE='http://127.0.0.1:8000'
for rota in ['/livros','/livros/1','/livros/999999','/relatorios/mais-vendidos','/livros/busca?titulo=Segredo']:
    r=requests.get(BASE+rota,timeout=10)
    print(rota, 'HTTP',r.status_code,str(r.json())[:500])
