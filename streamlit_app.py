import streamlit as st
import pandas as pd
import datetime
import json
import requests
from io import BytesIO
import base64

# Configuração da página
st.set_page_config(
    page_title="Auxiliar Pré-Operatório",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Função para estilizar a aplicação
def local_css():
    st.markdown("""
    <style>
        .main {
            background-color: #f5f7fa;
        }
        .st-emotion-cache-18ni7ap {
            background-color: #e8eef7;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .stButton>button {
            background-color: #3498db;
            color: white;
            border-radius: 5px;
            padding: 0.5rem 1rem;
            border: none;
        }
        .stButton>button:hover {
            background-color: #2980b9;
        }
        .risk-high {
            color: #e74c3c;
            font-weight: bold;
        }
        .risk-medium {
            color: #f39c12;
            font-weight: bold;
        }
        .risk-low {
            color: #2ecc71;
            font-weight: bold;
        }
        .info-box {
            background-color: #d4edff;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        }
        .warning-box {
            background-color: #ffe0d4;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        }
        .success-box {
            background-color: #d4ffec;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)

# Aplicar o CSS
local_css()

# Função para consultar a API do Gemini (será usada quando necessário)
def consultar_gemini(prompt, api_key):
    """
    Função para consultar a API do Gemini
    """
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    # Adicionar a chave API como parâmetro na URL
    full_url = f"{url}?key={api_key}"
    
    response = requests.post(full_url, headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    else:
        return f"Erro ao consultar a API: {response.status_code} - {response.text}"

# Função para calcular o risco cirúrgico baseado nas respostas
def calcular_risco_cirurgico(respostas):
    """
    Calcula o risco cirúrgico com base nas respostas fornecidas
    """
    pontos = 0
    fatores_graves = 0
    
    # Idade
    if respostas['idade'] >= 70:
        pontos += 3
    elif respostas['idade'] >= 60:
        pontos += 2
    elif respostas['idade'] >= 50:
        pontos += 1
    
    # Comorbidades
    for comorbidade in respostas['comorbidades']:
        if comorbidade in ['Diabetes descompensada', 'Insuficiência cardíaca', 'Doença coronariana grave', 'DPOC grave']:
            pontos += 3
            fatores_graves += 1
        elif comorbidade in ['Hipertensão não controlada', 'Diabetes controlada', 'Obesidade mórbida']:
            pontos += 2
        elif comorbidade in ['Hipertensão controlada', 'Asma', 'Hipotireoidismo']:
            pontos += 1
    
    # Medicações
    if respostas['usa_anticoagulantes']:
        pontos += 2
    
    if respostas['uso_corticoides']:
        pontos += 1
    
    # ASA
    if respostas['asa'] == 'ASA IV':
        pontos += 4
    elif respostas['asa'] == 'ASA III':
        pontos += 3
    elif respostas['asa'] == 'ASA II':
        pontos += 1
    
    # Cirurgia recente
    if respostas['cirurgia_recente']:
        pontos += 2
    
    # Complexidade da cirurgia
    if respostas['complexidade_cirurgia'] == 'Alta':
        pontos += 3
    elif respostas['complexidade_cirurgia'] == 'Média':
        pontos += 2
    elif respostas['complexidade_cirurgia'] == 'Baixa':
        pontos += 1
    
    # Avaliar risco total
    if pontos >= 10 or fatores_graves >= 2:
        return "Alto", pontos
    elif pontos >= 6:
        return "Médio", pontos
    else:
        return "Baixo", pontos

# Função para determinar o tempo de jejum
def determinar_jejum(tipo_cirurgia, tipo_anestesia):
    """
    Determina o tempo de jejum com base no tipo de cirurgia e anestesia
    """
    # Padrão de jejum para sólidos
    jejum_solidos = 8  # horas
    
    # Padrão de jejum para líquidos claros
    if tipo_anestesia == "Geral" or tipo_anestesia == "Regional":
        jejum_liquidos_claros = 2  # horas
    else:
        jejum_liquidos_claros = 1  # hora
        
    # Ajuste com base no tipo de cirurgia
    if tipo_cirurgia == "Cirurgia abdominal":
        jejum_solidos = 10
    elif tipo_cirurgia == "Cirurgia ambulatorial simples" and tipo_anestesia == "Local":
        jejum_solidos = 6
    
    return {
        "solidos": jejum_solidos,
        "liquidos_claros": jejum_liquidos_claros
    }

# Função para gerar recomendações personalizadas
def gerar_recomendacoes(respostas, risco, api_key=None):
    """
    Gera recomendações personalizadas com base nas respostas e no risco calculado
    """
    recomendacoes = []
    
    # Recomendações baseadas na idade
    if respostas['idade'] >= 70:
        recomendacoes.append("Considere uma avaliação geriátrica pré-operatória.")
    
    # Recomendações baseadas em comorbidades
    for comorbidade in respostas['comorbidades']:
        if comorbidade == 'Diabetes descompensada':
            recomendacoes.append("É importante controlar seus níveis de glicose antes da cirurgia. Agende uma consulta com seu endocrinologista.")
        elif comorbidade == 'Hipertensão não controlada':
            recomendacoes.append("Sua pressão arterial deve ser controlada antes do procedimento. Continue tomando seus medicamentos conforme orientação médica.")
        elif comorbidade == 'Insuficiência cardíaca':
            recomendacoes.append("Mantenha-se em dia com suas medicações cardíacas e informe a equipe médica sobre todos os sintomas recentes.")
    
    # Recomendações baseadas no uso de medicamentos
    if respostas['usa_anticoagulantes']:
        recomendacoes.append("Você precisará interromper o uso de anticoagulantes antes da cirurgia. Consulte seu médico para um plano de interrupção segura.")
    
    # Recomendações baseadas no risco
    if risco == "Alto":
        recomendacoes.append("Seu risco cirúrgico é elevado. É altamente recomendável uma avaliação cardiológica completa antes do procedimento.")
    elif risco == "Médio":
        recomendacoes.append("Seu risco cirúrgico é moderado. Considere realizar exames pré-operatórios adicionais conforme orientação médica.")
    
    # Se tiver API key do Gemini, pode personalizar ainda mais as recomendações
    if api_key:
        try:
            prompt = f"""
            Com base no paciente com as seguintes características:
            - Idade: {respostas['idade']} anos
            - Comorbidades: {', '.join(respostas['comorbidades']) if respostas['comorbidades'] else 'Nenhuma'}
            - Classificação ASA: {respostas['asa']}
            - Usa anticoagulantes: {'Sim' if respostas['usa_anticoagulantes'] else 'Não'}
            - Usa corticoides: {'Sim' if respostas['uso_corticoides'] else 'Não'}
            - Tipo de cirurgia: {respostas['tipo_cirurgia']}
            - Complexidade da cirurgia: {respostas['complexidade_cirurgia']}
            
            Forneça 3 recomendações específicas para este paciente no período pré-operatório, considerando que seu risco cirúrgico foi classificado como {risco}.
            Dê recomendações objetivas e práticas, sem introduções ou conclusões.
            """
            
            recomendacoes_ia = consultar_gemini(prompt, api_key)
            # Processar e adicionar as recomendações da IA
            for linha in recomendacoes_ia.strip().split('\n'):
                if linha and not linha.startswith('Recomendações:'):
                    # Remover numeração e pontos se existirem
                    linha_limpa = ' '.join(linha.split('. ')[1:]) if '. ' in linha else linha
                    linha_limpa = linha_limpa.strip('- ').strip()
                    if linha_limpa and len(linha_limpa) > 10:  # Verificar se é uma recomendação válida
                        recomendacoes.append(linha_limpa)
        except Exception as e:
            recomendacoes.append(f"Não foi possível gerar recomendações personalizadas adicionais. Erro: {str(e)}")
    
    return recomendacoes

# Função para gerar um PDF de relatório
def gerar_relatorio_pdf(respostas, risco, pontos, jejum, recomendacoes):
    """
    Função para criar um relatório em HTML que pode ser convertido para PDF
    """
    html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1, h2 {{ color: #3498db; }}
                .risco-alto {{ color: #e74c3c; font-weight: bold; }}
                .risco-medio {{ color: #f39c12; font-weight: bold; }}
                .risco-baixo {{ color: #2ecc71; font-weight: bold; }}
                .info-box {{ background-color: #d4edff; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Relatório de Avaliação Pré-Operatória</h1>
            <p><strong>Data de geração:</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            
            <h2>Informações do Paciente</h2>
            <table>
                <tr><th>Idade</th><td>{respostas['idade']} anos</td></tr>
                <tr><th>Comorbidades</th><td>{', '.join(respostas['comorbidades']) if respostas['comorbidades'] else 'Nenhuma'}</td></tr>
                <tr><th>Classificação ASA</th><td>{respostas['asa']}</td></tr>
                <tr><th>Uso de anticoagulantes</th><td>{'Sim' if respostas['usa_anticoagulantes'] else 'Não'}</td></tr>
                <tr><th>Uso de corticoides</th><td>{'Sim' if respostas['uso_corticoides'] else 'Não'}</td></tr>
                <tr><th>Cirurgia recente (últimos 3 meses)</th><td>{'Sim' if respostas['cirurgia_recente'] else 'Não'}</td></tr>
            </table>
            
            <h2>Informações da Cirurgia</h2>
            <table>
                <tr><th>Tipo de Cirurgia</th><td>{respostas['tipo_cirurgia']}</td></tr>
                <tr><th>Tipo de Anestesia</th><td>{respostas['tipo_anestesia']}</td></tr>
                <tr><th>Complexidade</th><td>{respostas['complexidade_cirurgia']}</td></tr>
            </table>
            
            <h2>Avaliação de Risco</h2>
    """
    
    if risco == "Alto":
        html += f'<p>Risco Cirúrgico: <span class="risco-alto">ALTO</span> (Pontuação: {pontos})</p>'
    elif risco == "Médio":
        html += f'<p>Risco Cirúrgico: <span class="risco-medio">MÉDIO</span> (Pontuação: {pontos})</p>'
    else:
        html += f'<p>Risco Cirúrgico: <span class="risco-baixo">BAIXO</span> (Pontuação: {pontos})</p>'
    
    html += f"""
            <div class="info-box">
                <h3>Orientações de Jejum</h3>
                <p><strong>Alimentos sólidos:</strong> {jejum['solidos']} horas antes da cirurgia</p>
                <p><strong>Líquidos claros:</strong> {jejum['liquidos_claros']} horas antes da cirurgia</p>
                <p><small>Nota: Líquidos claros incluem água, chá sem leite, suco de fruta sem polpa.</small></p>
            </div>
            
            <h2>Recomendações Personalizadas</h2>
            <ul>
    """
    
    for recomendacao in recomendacoes:
        html += f"<li>{recomendacao}</li>"
    
    html += """
            </ul>
            
            <p style="margin-top: 40px; font-style: italic;">
                Este relatório foi gerado automaticamente e não substitui a avaliação médica.
                Consulte seu médico para orientações específicas relacionadas ao seu caso.
            </p>
        </body>
    </html>
    """
    
    return html

# Função para converter HTML em PDF (simplificada - apenas retorna o HTML)
def html_para_download(html_string):
    """
    Converte HTML para um link de download
    """
    # Nesta implementação, retornaremos apenas o HTML para download
    # Em um ambiente real, você usaria uma biblioteca como weasyprint ou reportlab para gerar um PDF
    
    encoded = base64.b64encode(html_string.encode()).decode()
    return f'data:text/html;base64,{encoded}'

# Definir estrutura da aplicação
def main():
    st.title("🏥 Auxiliar Pré-Operatório")
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        api_key = st.text_input("API Key do Gemini (opcional)", type="password")
        st.write("---")
        st.write("Desenvolvido com ❤️ para auxílio pré-operatório")
    
    # Abas da aplicação
    tab1, tab2, tab3 = st.tabs(["📋 Avaliação de Risco", "ℹ️ Informações", "❓ Dúvidas Frequentes"])
    
    with tab1:
        st.header("Avaliação de Risco Cirúrgico")
        st.write("Preencha o formulário abaixo para avaliar seu risco cirúrgico e receber orientações personalizadas.")
        
        # Inicializar variáveis de sessão se necessário
        if 'respostas' not in st.session_state:
            st.session_state.respostas = {
                'idade': 0,
                'comorbidades': [],
                'asa': 'ASA I',
                'usa_anticoagulantes': False,
                'uso_corticoides': False,
                'cirurgia_recente': False,
                'tipo_cirurgia': 'Cirurgia geral',
                'tipo_anestesia': 'Geral',
                'complexidade_cirurgia': 'Média'
            }
        
        if 'resultado_calculado' not in st.session_state:
            st.session_state.resultado_calculado = False
            
        if 'relatorio_html' not in st.session_state:
            st.session_state.relatorio_html = ""
        
        # Formulário de avaliação
        with st.form("formulario_avaliacao"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Dados do Paciente")
                st.session_state.respostas['idade'] = st.number_input("Idade", min_value=0, max_value=120, value=st.session_state.respostas['idade'])
                
                st.session_state.respostas['comorbidades'] = st.multiselect(
                    "Comorbidades",
                    options=[
                        "Hipertensão controlada", 
                        "Hipertensão não controlada", 
                        "Diabetes controlada", 
                        "Diabetes descompensada",
                        "Insuficiência cardíaca",
                        "Doença coronariana grave",
                        "DPOC grave",
                        "Asma",
                        "Obesidade mórbida",
                        "Hipotireoidismo",
                        "Doença renal crônica",
                        "Cirrose hepática"
                    ],
                    default=st.session_state.respostas['comorbidades']
                )
                
                st.session_state.respostas['asa'] = st.selectbox(
                    "Classificação ASA",
                    options=["ASA I", "ASA II", "ASA III", "ASA IV", "ASA V"],
                    index=["ASA I", "ASA II", "ASA III", "ASA IV", "ASA V"].index(st.session_state.respostas['asa']),
                    help="ASA I: Paciente saudável; ASA II: Doença sistêmica leve; ASA III: Doença sistêmica grave; ASA IV: Doença sistêmica grave com risco de vida; ASA V: Paciente moribundo"
                )
                
                st.session_state.respostas['usa_anticoagulantes'] = st.checkbox(
                    "Utiliza anticoagulantes", 
                    value=st.session_state.respostas['usa_anticoagulantes'],
                    help="Ex: Varfarina, Heparina, Aspirina, Clopidogrel"
                )
                
                st.session_state.respostas['uso_corticoides'] = st.checkbox(
                    "Utiliza corticoides", 
                    value=st.session_state.respostas['uso_corticoides'],
                    help="Ex: Prednisona, Dexametasona"
                )
                
                st.session_state.respostas['cirurgia_recente'] = st.checkbox(
                    "Realizou cirurgia nos últimos 3 meses", 
                    value=st.session_state.respostas['cirurgia_recente']
                )
            
            with col2:
                st.subheader("Dados da Cirurgia")
                st.session_state.respostas['tipo_cirurgia'] = st.selectbox(
                    "Tipo de Cirurgia",
                    options=[
                        "Cirurgia geral", 
                        "Cirurgia cardíaca", 
                        "Cirurgia vascular", 
                        "Neurocirurgia",
                        "Cirurgia ortopédica",
                        "Cirurgia abdominal",
                        "Cirurgia ambulatorial simples"
                    ],
                    index=["Cirurgia geral", "Cirurgia cardíaca", "Cirurgia vascular", "Neurocirurgia", "Cirurgia ortopédica", "Cirurgia abdominal", "Cirurgia ambulatorial simples"].index(st.session_state.respostas['tipo_cirurgia'])
                )
                
                st.session_state.respostas['tipo_anestesia'] = st.selectbox(
                    "Tipo de Anestesia",
                    options=["Geral", "Regional", "Local", "Sedação"],
                    index=["Geral", "Regional", "Local", "Sedação"].index(st.session_state.respostas['tipo_anestesia'])
                )
                
                st.session_state.respostas['complexidade_cirurgia'] = st.select_slider(
                    "Complexidade da Cirurgia",
                    options=["Baixa", "Média", "Alta"],
                    value=st.session_state.respostas['complexidade_cirurgia']
                )
            
            submit_button = st.form_submit_button("Calcular Risco")
            
            if submit_button:
                with st.spinner("Calculando risco cirúrgico..."):
                    # Calcular risco
                    risco, pontos = calcular_risco_cirurgico(st.session_state.respostas)
                    
                    # Determinar tempo de jejum
                    jejum = determinar_jejum(
                        st.session_state.respostas['tipo_cirurgia'], 
                        st.session_state.respostas['tipo_anestesia']
                    )
                    
                    # Gerar recomendações
                    recomendacoes = gerar_recomendacoes(st.session_state.respostas, risco, api_key)
                    
                    # Gerar HTML do relatório
                    relatorio_html = gerar_relatorio_pdf(
                        st.session_state.respostas,
                        risco,
                        pontos,
                        jejum,
                        recomendacoes
                    )
                    
                    # Armazenar resultado na sessão
                    st.session_state.resultado = {
                        'risco': risco,
                        'pontos': pontos,
                        'jejum': jejum,
                        'recomendacoes': recomendacoes
                    }
                    
                    st.session_state.resultado_calculado = True
                    st.session_state.relatorio_html = relatorio_html
        
        # Exibir resultado se calculado
        if st.session_state.resultado_calculado:
            st.write("---")
            
            # Exibir resultado do risco
            if st.session_state.resultado['risco'] == "Alto":
                st.markdown(f"### Risco Cirúrgico: <span class='risk-high'>ALTO</span> (Pontuação: {st.session_state.resultado['pontos']})", unsafe_allow_html=True)
                st.markdown("<div class='warning-box'>Este risco indica necessidade de avaliação especializada antes do procedimento.</div>", unsafe_allow_html=True)
            elif st.session_state.resultado['risco'] == "Médio":
                st.markdown(f"### Risco Cirúrgico: <span class='risk-medium'>MÉDIO</span> (Pontuação: {st.session_state.resultado['pontos']})", unsafe_allow_html=True)
                st.markdown("<div class='info-box'>Este risco indica que você deve seguir cuidadosamente todas as recomendações médicas.</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"### Risco Cirúrgico: <span class='risk-low'>BAIXO</span> (Pontuação: {st.session_state.resultado['pontos']})", unsafe_allow_html=True)
                st.markdown("<div class='success-box'>Este risco indica uma boa condição pré-operatória, mas ainda é importante seguir todas as recomendações.</div>", unsafe_allow_html=True)
            
            # Exibir orientações de jejum
            st.subheader("Orientações de Jejum")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Alimentos sólidos:** {st.session_state.resultado['jejum']['solidos']} horas antes da cirurgia")
            with col2:
                st.markdown(f"**Líquidos claros:** {st.session_state.resultado['jejum']['liquidos_claros']} horas antes da cirurgia")
            st.caption("Líquidos claros incluem água, chá sem leite, suco de fruta sem polpa.")
            
            # Exibir recomendações
            st.subheader("Recomendações Personalizadas")
            for rec in st.session_state.resultado['recomendacoes']:
                st.markdown(f"- {rec}")
            
            # Botão para download do relatório
            download_link = html_para_download(st.session_state.relatorio_html)
            st.download_button(
                label="📥 Baixar Relatório",
                data=st.session_state.relatorio_html,
                file_name="relatorio_pre_operatorio.html",
                mime="text/html"
            )
    
    with tab2:
        st.header("Informações Importantes")
        
        st.subheader("Classificação ASA")
        st.markdown("""
        A classificação ASA (American Society of Anesthesiologists) é um sistema usado para avaliar a condição física de um paciente antes da cirurgia:
        
        - **ASA I** - Paciente saudável
        - **ASA II** - Paciente com doença sistêmica leve
        - **ASA III** - Paciente com doença sistêmica grave
        - **ASA IV** - Paciente com doença sistêmica grave que representa risco de vida constante
        - **ASA V** - Paciente moribundo que não se espera que sobreviva sem a operação
        """)
        
        st.subheader("Orientações Gerais sobre Jejum")
        st.markdown("""
        O jejum pré-operatório é essencial para evitar complicações como aspiração pulmonar durante a anestesia:
        
        1. **Alimentos sólidos**: Geralmente 8 horas antes da cirurgia
        2. **Leite e produtos lácteos**: 6 horas antes da cirurgia
        3. **Líquidos claros** (água, chá sem leite, suco sem polpa): 2 horas antes para anestesia geral/regional
        
        > Nota: Estas são orientações gerais. Siga sempre as instruções específicas da sua equipe médica.
        """)
        
        st.subheader("Medicações")
        st.markdown("""
        **Medicações que geralmente devem ser suspensas:**
        - Anticoagulantes (conforme orientação médica específica)
        - Anti-inflamatórios não esteroidais (geralmente 7 dias antes)
        
        **Medicações que geralmente devem ser mantidas:**
        - Anti-hipertensivos (com pequeno gole de água)
        - Medicações cardíacas
        - Medicações para controle de convulsões
        
        > Importante: Nunca suspenda medicações sem orientação médica específica.
        """)
    
    with tab3:
        st.header("Dúvidas Frequentes")
        
        with st.expander("O que é avaliação pré-operatória?"):
            st.write("""
            A avaliação pré-operatória é um processo de avaliação da saúde geral do paciente antes de uma cirurgia. Ela ajuda a:
            
            - Identificar fatores de risco que podem complicar a cirurgia ou anestesia
            - Otimizar condições médicas existentes
            - Reduzir complicações pós-operatórias
            - Planejar o manejo perioperatório adequado
            """)
        
        with st.expander("Posso tomar água antes da cirurgia?"):
            st.write("""
            Em muitos casos, é permitido beber água e outros líquidos claros (sem polpa, sem leite) até 2 horas antes da cirurgia com anestesia geral ou regional. Para anestesia local, pode-se permitir até 1 hora antes.
            
            No entanto, é fundamental seguir as orientações específicas de sua equipe médica, pois existem exceções dependendo do tipo de cirurgia e da condição do paciente.
            """)
        
        with st.expander("Quais exames devo fazer antes da cirurgia?"):
            st.write("""
            Os exames pré-operatórios variam conforme o tipo de cirurgia e condição do paciente. Os mais comuns incluem:
            
            - **Exames de sangue**: Hemograma completo, coagulograma, função renal e hepática
            - **Eletrocardiograma (ECG)**: Especialmente para pacientes acima de 40 anos ou com fatores de risco cardíaco
            - **Raio-X de tórax**: Para avaliar condição pulmonar
            - **Outros exames específicos**: Dependendo de suas condições médicas ou tipo de cirurgia
            
            Seu médico irá solicitar os exames necessários com base no seu caso específico.
            """)
            
        with st.expander("Preciso suspender meus medicamentos antes da cirurgia?"):
            st.write("""
            A decisão de continuar ou suspender medicamentos antes da cirurgia é individual e deve ser tomada pelo seu médico. Em geral:
            
            - **Medicamentos para pressão alta, cardíacos e anti-convulsivantes**: Geralmente são mantidos até o dia da cirurgia
            - **Anticoagulantes e anti-inflamatórios**: Frequentemente precisam ser suspensos dias antes
            - **Antidiabéticos orais e insulina**: Podem precisar de ajustes no dia da cirurgia
            
            Nunca suspenda medicamentos por conta própria. Sempre consulte seu médico para orientações específicas.
            """)
            
        with st.expander("Como me preparar emocionalmente para a cirurgia?"):
            st.write("""
            Preparar-se emocionalmente para uma cirurgia é tão importante quanto a preparação física. Algumas dicas:
            
            - **Informe-se adequadamente**: Conhecimento reduz ansiedade
            - **Pratique técnicas de relaxamento**: Respiração profunda, meditação ou visualização
            - **Converse sobre seus medos**: Com seu médico, familiares ou amigos
            - **Mantenha uma atitude positiva**: Foque no resultado do tratamento e não no procedimento
            - **Descanse adequadamente**: Antes da cirurgia, tente dormir bem
            
            Se a ansiedade for intensa, mencione ao seu médico, pois existem medicações que podem ajudar.
            """)
            
        with st.expander("O que levar para o hospital no dia da cirurgia?"):
            st.write("""
            Itens importantes para levar ao hospital:
            
            - **Documentos**: Identidade, cartão do plano de saúde, termo de consentimento
            - **Exames pré-operatórios**: Todos os exames solicitados
            - **Lista de medicamentos**: Que você usa regularmente com doses
            - **Objetos pessoais básicos**: Escova de dentes, chinelos, roupas confortáveis
            - **Dispositivos médicos**: Se aplicável (inaladores, aparelhos auditivos)
            
            Evite levar objetos de valor, joias ou maquiagem.
            """)
            
        with st.expander("Quanto tempo antes devo chegar ao hospital?"):
            st.write("""
            Em geral, é recomendado chegar ao hospital:
            
            - **Cirurgias ambulatoriais**: 1-2 horas antes do horário agendado
            - **Cirurgias com internação**: 2-3 horas antes do horário agendado
            
            Este tempo é necessário para procedimentos administrativos, avaliação pré-anestésica final e preparação do paciente. Siga sempre as orientações específicas da sua equipe médica ou hospital.
            """)
            
    # Rodapé
    st.write("---")
    st.caption("Este aplicativo não substitui a avaliação médica profissional. Sempre consulte seu médico para orientações específicas sobre seu caso.")

if __name__ == "__main__":
    main()