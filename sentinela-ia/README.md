# Sentinela IA

Backend que busca automaticamente o artigo de estudo d'A Sentinela da
semana atual (www.jw.org), extrai perguntas/parágrafos/imagens e gera
respostas parafraseadas com o Gemini.

## Estrutura

```
sentinela-ia/
├── main.py
├── requirements.txt
├── .env.example
└── app/
    └── services/
        ├── article_finder.py     # acha a URL do artigo da semana atual
        ├── sentinela_parser.py   # extrai perguntas + parágrafos + imagens
        └── gemini_client.py      # gera a resposta parafraseada via Gemini
```

## Rodar localmente

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt

# copie .env.example para .env e coloque sua chave do Gemini
cp .env.example .env

uvicorn main:app --reload
```

Depois abra http://127.0.0.1:8000/docs para testar.

## Endpoints

- `GET /artigo?url=...` — processa um artigo específico, dado o link.
- `GET /semana` — acha sozinho o artigo da semana atual, processa e
  (por padrão) já gera as respostas via Gemini. Use
  `?com_respostas=false` pra pular a etapa do Gemini.

## Deploy no Render

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Configure a variável de ambiente `GEMINI_API_KEY` em
  Environment → Environment Variables.
