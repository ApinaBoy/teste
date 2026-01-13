from flask import Flask, request, jsonify, send_from_directory
import requests
from bs4 import BeautifulSoup
import sympy as sp
import re
import os
from dotenv import load_dotenv
from openai import OpenAI

app = Flask(__name__)
app.static_folder = 'static'

load_dotenv()

# Carrega a chave Groq
api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    print("ERRO: GROQ_API_KEY não encontrada no arquivo .env")
    groq_client = None
else:
    print("Groq API key carregada com sucesso!")
    groq_client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

# Headers para Wikipedia
wiki_headers = {
    'User-Agent': 'VerificadorTeorias/1.0 (contato: exemplo@email.com)'
}

def buscar_informacoes_wikipedia(query):
    url = "https://pt.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query
    }
    try:
        response = requests.get(url, params=params, headers=wiki_headers)
        if response.status_code != 200:
            return f"Erro Wikipedia busca: Status {response.status_code}"
        
        data = response.json()
        if 'search' in data['query'] and data['query']['search']:
            title = data['query']['search'][0]['title']
            
            params_extract = {
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "titles": title,
                "exintro": True,
                "explaintext": True
            }
            resp_extract = requests.get(url, params=params_extract, headers=wiki_headers)
            if resp_extract.status_code != 200:
                return f"Erro extrato Wikipedia: Status {resp_extract.status_code}"
            
            extract_data = resp_extract.json()
            pages = extract_data['query']['pages']
            page_id = list(pages.keys())[0]
            conteudo = pages[page_id].get('extract', 'Sem conteúdo.')
            return conteudo
        return "Nenhum resultado encontrado na Wikipedia."
    except Exception as e:
        return f"Erro ao acessar Wikipedia: {str(e)}"

def extrair_dados_numericos(texto):
    return re.findall(r'\d+\.?\d*', texto)

def analisar_teoria(teoria):
    dados = buscar_informacoes_wikipedia(teoria)
    numeros = extrair_dados_numericos(dados)
    
    conclusao = "Inconclusivo."
    calculo = None
    
    if "evidência" in dados.lower() or "confirmado" in dados.lower():
        conclusao = "Verdadeiro"
    elif "falso" in dados.lower() or "desmentido" in dados.lower():
        conclusao = "Falso"
    
    if "universo" in teoria.lower() and "expans" in teoria.lower():
        H0, v, d = sp.symbols('H0 v d')
        equacao = sp.Eq(v, H0 * d)
        resultado = equacao.subs({H0: 70, d: 1})
        calculo = f"Lei de Hubble: v = {resultado.rhs} km/s para d=1 Mpc. Suporta expansão."
    
    return {
        "teoria": teoria,
        "dados": dados[:500] + "..." if len(dados) > 500 else dados,
        "numeros_extraidos": numeros,
        "calculo": calculo,
        "conclusao": conclusao,
        "fonte": "Wikipedia API"
    }

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/analisar', methods=['POST'])
def analisar():
    try:
        data = request.json
        teoria = data.get('teoria')
        if not teoria:
            return jsonify({"erro": "Teoria não fornecida"}), 400
        resultado = analisar_teoria(teoria)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

@app.route('/assistente', methods=['POST'])
def assistente():
    if groq_client is None:
        return jsonify({"erro": "Chave Groq não configurada no .env"}), 503

    try:
        data = request.json
        pergunta = data.get('pergunta')
        if not pergunta:
            return jsonify({"erro": "Pergunta não fornecida"}), 400

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Você é um assistente útil. Responda em português quando a pergunta for em português. Seja direto e claro."},
                {"role": "user", "content": pergunta}
            ],
            temperature=0.7,
            max_tokens=1200
        )
        resposta = response.choices[0].message.content
        return jsonify({"resposta": resposta})
    except Exception as e:
        return jsonify({"erro": f"Erro na Groq API: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)