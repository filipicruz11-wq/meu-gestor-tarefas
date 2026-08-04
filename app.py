import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime, timedelta
import holidays
import psycopg2
from sqlalchemy import create_engine, text
import requests
import json
import time
import os
from google import genai
from google.genai import errors, types

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="CEJUSC - Gestão do Gabinete",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilização CSS Profissional
st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; }
    
    .header-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .header-title {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        color: #FFFFFF !important;
    }
    .header-subtitle {
        font-size: 0.95rem;
        color: #93C5FD;
        margin-top: 4px;
    }

    .stSelectbox label, .stTextArea label, .stAudioInput label, .stRadio label {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        color: #1E293B !important;
    }

    .stTextArea textarea {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        font-size: 0.95rem !important;
        color: #0F172A !important;
    }

    /* Estilo dos Botões */
    .stButton > button {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.5rem !important;
        width: 100% !important;
    }

    /* Caixa do Documento Gerado na IA */
    div[data-testid="stTextArea"] textarea[aria-label="Documento Gerado:"] {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-left: 6px solid #2563EB !important;
        border-radius: 8px !important;
        font-family: 'Georgia', 'Times New Roman', serif !important;
        font-size: 1.05rem !important;
        line-height: 1.7 !important;
        color: #0F172A !important;
    }

    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CONEXÃO COM O BANCO DE DADOS (POSTGRESQL)
# ==========================================
DB_URL = os.environ.get("DATABASE_URL")

if not DB_URL:
    try:
        DB_URL = st.secrets["DATABASE_URL"]
    except Exception:
        DB_URL = None

if not DB_URL:
    st.error("⚠️ Erro: Conexão com Banco de Dados não configurada. Defina DATABASE_URL nas variáveis do Render.")
    st.stop()

if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DB_URL)

def inicializar_db():
    with engine.connect() as conn:
        # Criar tabelas se não existirem
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id SERIAL PRIMARY KEY,
                titulo TEXT NOT NULL,
                processo TEXT,
                prazo DATE NOT NULL,
                prioridade TEXT DEFAULT 'Média',
                status TEXT DEFAULT 'Pendente'
            );
            CREATE TABLE IF NOT EXISTS compromissos (
                id SERIAL PRIMARY KEY,
                titulo TEXT NOT NULL,
                data DATE NOT NULL,
                horario TIME NOT NULL,
                tipo TEXT DEFAULT 'Reunião'
            );
            CREATE TABLE IF NOT EXISTS lembretes (
                id SERIAL PRIMARY KEY,
                texto TEXT NOT NULL,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS audiencias (
                id SERIAL PRIMARY KEY,
                processo TEXT NOT NULL,
                partes TEXT NOT NULL,
                data DATE NOT NULL,
                horario TIME NOT NULL,
                modalidade TEXT DEFAULT 'Presencial',
                status TEXT DEFAULT 'Agendada'
            );
            CREATE TABLE IF NOT EXISTS contatos (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                cargo TEXT,
                orgao TEXT,
                telefone TEXT,
                email TEXT
            );
            CREATE TABLE IF NOT EXISTS modelos (
                id SERIAL PRIMARY KEY,
                titulo TEXT NOT NULL,
                categoria TEXT NOT NULL,
                conteudo TEXT NOT NULL
            );
        """))
        
        # Garante a existência de colunas em bancos/tabelas já existentes (Previne KeyError)
        conn.execute(text("ALTER TABLE tarefas ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Pendente';"))
        conn.execute(text("ALTER TABLE tarefas ADD COLUMN IF NOT EXISTS prioridade TEXT DEFAULT 'Média';"))
        conn.execute(text("ALTER TABLE tarefas ADD COLUMN IF NOT EXISTS processo TEXT;"))
        conn.execute(text("ALTER TABLE audiencias ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Agendada';"))
        
        conn.commit()

try:
    inicializar_db()
except Exception as e:
    st.error(f"Erro ao inicializar banco de dados: {e}")

# ==========================================
# CONFIGURAÇÃO E FUNÇÕES DA IA DO CEJUSC
# ==========================================
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except Exception:
        API_KEY = None

client = genai.Client(api_key=API_KEY) if API_KEY else None

ARQUIVO_BANCO_MODELOS = "BANCO DE DADOS OBJETOS.txt"
ARQUIVO_BANCO_TERMOS = "BANCO DE DADOS TERMOS.txt"

def carregar_arquivo_texto(nome_arquivo):
    diretorios = [os.getcwd(), os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()]
    for pasta in diretorios:
        caminho_direto = os.path.join(pasta, nome_arquivo)
        if os.path.exists(caminho_direto):
            try:
                with open(caminho_direto, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception as e:
                return f"[Erro ao ler {nome_arquivo}: {e}]"
    return f"[Aviso: O arquivo '{nome_arquivo}' não foi encontrado.]"

PROMPTS = {
    "1": """Você é um assistente especialista na redação de RELATOS DE CASOS para o CEJUSC.
    REGRAS DE SAÍDA E FORMATAÇÃO:
    - Retorne APENAS o texto final do relato. NÃO inclua saudações, explicações, metadados ou tópicos informando as correções feitas.
    - NÃO use símbolos de markdown como asteriscos (** ou *) para negrito. Devolva texto limpo pronto para colar em editores oficiais.
    - OBRIGATÓRIO: Mantenha ou utilize sempre as nomenclaturas Reclamante(s) e Reclamado(a)(s). NUNCA substitua por Requerente(s) ou Requerido(a)(s).
    - INSTRUÇÃO DE MODELO: Analise o Banco de Dados de Modelos Oficiais fornecido abaixo. Se o caso trazido pelo usuário se encaixar em algum deles, utilize a estrutura daquele modelo preenchendo-o com os dados concretos fornecidos. Caso nenhum modelo do arquivo se adeque perfeitamente, faça a estruturação, correção e adequação livre do relato de forma impecável.
    - Mantenha integralmente todos os nomes, datas, valores, endereços e matrículas.
    - Organize débitos/bens em listas alfabéticas (a, b, c).""",
    
    "2": """Você é um assistente especializado na redação de CERTIDÕES PROCESSUAIS para o CEJUSC. Retorne APENAS o texto formal sem asteriscos. Finalize rigorosamente com a expressão: 'CERTIFICO e dou fé.'""",
    "3": """Você é um assistente especializado na redação de MINUTAS DE SENTENÇA E HOMOLOGAÇÕES para o CEJUSC. Retorne APENAS o texto final da minuta sem asteriscos. Utilize a estrutura formal (Relatório, Fundamentação e Dispositivo). Para homologação de acordo, utilize o Art. 487, III, 'b' do CPC.""",
    "4": """Você é um assistente especializado na redação de DESPACHOS E DECISÕES INTERLOCUTÓRIAS para o CEJUSC. Retorne APENAS a minuta final sem asteriscos.""",
    "5": """Você é um assistente especializado em REDAÇÃO DE E-MAILS INSTITUCIONAIS para o CEJUSC. Retorne APENAS o e-mail pronto para envio sem asteriscos.""",
    "6": """Você é um assistente especializado em NOTIFICAÇÕES VIA WHATSAPP para o CEJUSC. Retorne APENAS a mensagem. UTILIZE A SINTAXE DO WHATSAPP (*texto em negrito*, _texto em itálico_).""",
    "7": """Você é um assistente especialista de consulta e esclarecimento de DÚVIDAS GERAIS.""",
    "8": """Você é um assistente especializado na redação e estruturação de TERMOS DE AUDIÊNCIA para o CEJUSC. Retorne APENAS o texto formal do termo sem asteriscos.""",
    "9": """Você é um revisor de textos. Corrija a gramática e clareza preservando o estilo original.""",
    "10": """Você é um assistente objetivo para consulta rápida de documentos no atendimento do CEJUSC."""
}

def transcrever_audio(audio_bytes, mime_type):
    if not client: 
        raise Exception("A chave GEMINI_API_KEY não foi configurada no sistema.")
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    prompt = "Transcreva com máxima fidelidade o áudio a seguir para texto. Retorne APENAS a transcrição exata das palavras faladas, sem explicações ou comentários."
    
    modelos = ["gemini-flash-latest", "gemini-2.0-flash-lite", "gemini-flash-lite-latest"]
    for modelo in modelos:
        try:
            response = client.models.generate_content(model=modelo, contents=[prompt, audio_part])
            return response.text.strip()
        except errors.APIError:
            time.sleep(2)
    raise Exception("Não foi possível transcrever o áudio no momento.")

def processar_com_gemini(texto_bruto, opcao_menu):
    if not client:
        raise Exception("A chave GEMINI_API_KEY não foi configurada no sistema.")
    prompt_sistema = PROMPTS.get(opcao_menu, PROMPTS["1"])
    
    if opcao_menu == "1":
        conteudo_banco = carregar_arquivo_texto(ARQUIVO_BANCO_MODELOS)
        prompt_completo = f"{prompt_sistema}\n\nBANCO DE DADOS DE MODELOS (ARQUIVO EXTERNO):\n{conteudo_banco}\n\nPEDIDO OU RELATO DO CASO FORNECIDO PELO USUÁRIO:\n{texto_bruto}"
    elif opcao_menu == "8":
        conteudo_termos = carregar_arquivo_texto(ARQUIVO_BANCO_TERMOS)
        prompt_completo = f"{prompt_sistema}\n\nBANCO DE DADOS DE TERMOS (ARQUIVO EXTERNO):\n{conteudo_termos}\n\nDADOS DA AUDIÊNCIA OU CASO FORNECIDO PELO USUÁRIO:\n{texto_bruto}"
    elif opcao_menu in ["7", "10"]:
        prompt_completo = f"{prompt_sistema}\n\nCASO OU DÚVIDA INFORMADA:\n{texto_bruto}"
    else:
        prompt_completo = f"{prompt_sistema}\n\nTEXTO BRUTO A SER PROCESSADO:\n{texto_bruto}"

    modelos = ["gemini-flash-latest", "gemini-2.0-flash-lite", "gemini-flash-lite-latest"]
    for modelo in modelos:
        try:
            response = client.models.generate_content(model=modelo, contents=prompt_completo)
            return response.text
        except errors.APIError:
            time.sleep(2)
    raise Exception("Servidores indisponíveis no momento. Tente novamente.")

# ==========================================
# FUNÇÕES DE CONSULTA DO BANCO DE DADOS
# ==========================================
def carregar_dados(tabela):
    with engine.connect() as conn:
        return pd.read_sql(f"SELECT * FROM {tabela}", conn)

def executar_query(sql, params=None):
    with engine.connect() as conn:
        conn.execute(text(sql), params or {})
        conn.commit()

# ==========================================
# CABEÇALHO DO DASHBOARD
# ==========================================
st.markdown("""
    <div class="header-container">
        <div class="header-title">⚖️ CEJUSC - Gestão do Gabinete</div>
        <div class="header-subtitle">Sistema Integrado de Controle de Prazos, Audiências e Automação Jurídica</div>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# ABAS DE NAVEGAÇÃO (11 ABAS)
# ==========================================
t_dash, t_tar, t_com, t_lem, t_info, t_cont, t_aud, t_mod, t_cal, t_wpp, t_ia = st.tabs([
    "🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📝 LEMBRETES", "ℹ️ INFORMAÇÕES", 
    "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO", "📲 WHATSAPP", "🤖 IA CEJUSC"
])

# ------------------------------------------
# 1. TAB DASHBOARD / INÍCIO
# ------------------------------------------
with t_dash:
    st.subheader("📊 Painel Geral de Atividades")
    
    df_tar = carregar_dados("tarefas")
    df_aud = carregar_dados("audiencias")
    df_lem = carregar_dados("lembretes")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pendentes = len(df_tar[df_tar['status'] == 'Pendente']) if not df_tar.empty and 'status' in df_tar.columns else 0
        st.metric("Tarefas Pendentes", pendentes)
    with col2:
        hoje = date.today()
        atrasadas = len(df_tar[(pd.to_datetime(df_tar['prazo']).dt.date < hoje) & (df_tar['status'] == 'Pendente')]) if not df_tar.empty and 'status' in df_tar.columns else 0
        st.metric("Tarefas Atrasadas", atrasadas, delta_color="inverse")
    with col3:
        aud_agendadas = len(df_aud[df_aud['status'] == 'Agendada']) if not df_aud.empty and 'status' in df_aud.columns else 0
        st.metric("Audiências Agendadas", aud_agendadas)
    with col4:
        lembretes_cnt = len(df_lem) if not df_lem.empty else 0
        st.metric("Lembretes Ativos", lembretes_cnt)

    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### 📌 Próximos Prazos")
        if not df_tar.empty and 'status' in df_tar.columns:
            df_tar['prazo'] = pd.to_datetime(df_tar['prazo']).dt.date
            proximos = df_tar[df_tar['status'] == 'Pendente'].sort_values('prazo').head(5)
            st.dataframe(proximos[['titulo', 'processo', 'prazo', 'prioridade']], use_container_width=True)
        else:
            st.info("Nenhuma tarefa cadastrada.")

    with c2:
        st.markdown("### ⚖️ Próximas Audiências")
        if not df_aud.empty and 'status' in df_aud.columns:
            df_aud['data'] = pd.to_datetime(df_aud['data']).dt.date
            proximas_aud = df_aud[df_aud['status'] == 'Agendada'].sort_values('data').head(5)
            st.dataframe(proximas_aud[['processo', 'partes', 'data', 'horario', 'modalidade']], use_container_width=True)
        else:
            st.info("Nenhuma audiência agendada.")

# ------------------------------------------
# 2. TAB TAREFAS
# ------------------------------------------
with t_tar:
    st.subheader("📌 Gerenciamento de Tarefas")
    
    with st.expander("➕ Nova Tarefa", expanded=False):
        with st.form("form_tarefa"):
            titulo = st.text_input("Título da Tarefa*")
            processo = st.text_input("Número do Processo")
            prazo = st.date_input("Prazo*", value=date.today() + timedelta(days=5))
            prioridade = st.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
            if st.form_submit_button("Salvar Tarefa"):
                if titulo:
                    executar_query(
                        "INSERT INTO tarefas (titulo, processo, prazo, prioridade, status) VALUES (:t, :p, :pr, :prio, 'Pendente')",
                        {"t": titulo, "p": processo, "pr": prazo, "prio": prioridade}
                    )
                    st.success("Tarefa salva com sucesso!")
                    st.rerun()
                else:
                    st.error("Informe o título da tarefa.")

    df_tar = carregar_dados("tarefas")
    if not df_tar.empty:
        st.dataframe(df_tar, use_container_width=True)
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            id_concluir = st.number_input("ID da Tarefa para Concluir", min_value=1, step=1)
            if st.button("Marcar como Concluída"):
                executar_query("UPDATE tarefas SET status='Concluída' WHERE id=:id", {"id": id_concluir})
                st.success("Status atualizado!")
                st.rerun()
        with col_m2:
            id_deletar = st.number_input("ID da Tarefa para Excluir", min_value=1, step=1)
            if st.button("Excluir Tarefa"):
                executar_query("DELETE FROM tarefas WHERE id=:id", {"id": id_deletar})
                st.success("Tarefa excluída!")
                st.rerun()

# ------------------------------------------
# 3. TAB COMPROMISSOS
# ------------------------------------------
with t_com:
    st.subheader("📅 Compromissos do Gabinete")
    
    with st.form("form_compromisso"):
        titulo_comp = st.text_input("Compromisso")
        data_comp = st.date_input("Data", value=date.today())
        horario_comp = st.time_input("Horário", value=datetime.now().time())
        tipo_comp = st.selectbox("Tipo", ["Reunião", "Sessão", "Atendimento", "Outro"])
        if st.form_submit_button("Agendar Compromisso"):
            if titulo_comp:
                executar_query(
                    "INSERT INTO compromissos (titulo, data, horario, tipo) VALUES (:t, :d, :h, :tp)",
                    {"t": titulo_comp, "d": data_comp, "h": horario_comp, "tp": tipo_comp}
                )
                st.success("Compromisso agendado!")
                st.rerun()

    df_com = carregar_dados("compromissos")
    st.dataframe(df_com, use_container_width=True)

# ------------------------------------------
# 4. TAB LEMBRETES
# ------------------------------------------
with t_lem:
    st.subheader("📝 Lembretes Rápidos")
    
    with st.form("form_lembrete"):
        texto_lembrete = st.text_area("Novo Lembrete")
        if st.form_submit_button("Adicionar Lembrete"):
            if texto_lembrete:
                executar_query("INSERT INTO lembretes (texto) VALUES (:t)", {"t": texto_lembrete})
                st.success("Lembrete salvo!")
                st.rerun()

    df_lem = carregar_dados("lembretes")
    for _, row in df_lem.iterrows():
        st.warning(f"📌 [{row['data_criacao']}] {row['texto']}")

# ------------------------------------------
# 5. TAB INFORMAÇÕES
# ------------------------------------------
with t_info:
    st.subheader("ℹ️ Informações Úteis do CEJUSC")
    st.markdown("""
    * **Horário de Atendimento:** 08:00 às 17:00
    * **Balcão Virtual:** Link oficial de atendimento
    * **Orientações Gerais:**
      - Atendimentos pré-processuais exigem documento com foto e comprovante de residência.
      - Termos de acordo devem ser enviados diretamente para homologação via sistema.
    """)

# ------------------------------------------
# 6. TAB CONTATOS
# ------------------------------------------
with t_cont:
    st.subheader("📞 Agenda de Contatos Institucionais")
    
    with st.expander("➕ Adicionar Contato"):
        with st.form("form_contato"):
            nome = st.text_input("Nome")
            cargo = st.text_input("Cargo")
            orgao = st.text_input("Órgão/Setor")
            telefone = st.text_input("Telefone")
            email = st.text_input("E-mail")
            if st.form_submit_button("Salvar Contato"):
                executar_query(
                    "INSERT INTO contatos (nome, cargo, orgao, telefone, email) VALUES (:n, :c, :o, :t, :e)",
                    {"n": nome, "c": cargo, "o": orgao, "t": telefone, "e": email}
                )
                st.success("Contato cadastrado!")
                st.rerun()

    df_cont = carregar_dados("contatos")
    st.dataframe(df_cont, use_container_width=True)

# ------------------------------------------
# 7. TAB AUDIÊNCIAS
# ------------------------------------------
with t_aud:
    st.subheader("⚖️ Pauta de Audiências")
    
    with st.expander("➕ Agendar Audiência"):
        with st.form("form_aud"):
            proc = st.text_input("Processo/Reclamação")
            partes = st.text_input("Partes (Reclamante x Reclamado)")
            data_aud = st.date_input("Data da Audiência")
            hora_aud = st.time_input("Horário")
            modalidade = st.selectbox("Modalidade", ["Presencial", "Virtual (Teams)", "Híbrida"])
            if st.form_submit_button("Agendar Audiência"):
                executar_query(
                    "INSERT INTO audiencias (processo, partes, data, horario, modalidade) VALUES (:p, :pa, :d, :h, :m)",
                    {"p": proc, "pa": partes, "d": data_aud, "h": hora_aud, "m": modalidade}
                )
                st.success("Audiência agendada!")
                st.rerun()

    df_aud = carregar_dados("audiencias")
    st.dataframe(df_aud, use_container_width=True)

# ------------------------------------------
# 8. TAB MODELOS
# ------------------------------------------
with t_mod:
    st.subheader("📄 Banco de Modelos de Documentos")
    
    with st.expander("➕ Adicionar Modelo"):
        with st.form("form_modelo"):
            tit_mod = st.text_input("Título do Modelo")
            cat_mod = st.selectbox("Categoria", ["Termo", "Certidão", "Despacho", "Sentença", "Outro"])
            conteudo_mod = st.text_area("Conteúdo do Modelo", height=200)
            if st.form_submit_button("Salvar Modelo"):
                executar_query(
                    "INSERT INTO modelos (titulo, categoria, conteudo) VALUES (:t, :c, :cnt)",
                    {"t": tit_mod, "c": cat_mod, "cnt": conteudo_mod}
                )
                st.success("Modelo cadastrado!")
                st.rerun()

    df_mod = carregar_dados("modelos")
    st.dataframe(df_mod, use_container_width=True)

# ------------------------------------------
# 9. TAB CALENDÁRIO & PRAZOS
# ------------------------------------------
with t_cal:
    st.subheader("📅 Calculadora de Prazos Processuais")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        data_inicio = st.date_input("Data de Início/Intimação", value=date.today())
        dias_prazo = st.number_input("Quantidade de Dias", min_value=1, value=15)
        contar_uteis = st.checkbox("Contar apenas dias úteis (CPC)", value=True)
        uf_feriados = st.text_input("UF para Feriados (Ex: MA, SP, RJ)", value="MA")

    with col_c2:
        if st.button("Calcular Prazo Final"):
            data_atual = data_inicio
            dias_contados = 0
            feriados_br = holidays.BR(prov=uf_feriados if uf_feriados else None)
            
            while dias_contados < dias_prazo:
                data_atual += timedelta(days=1)
                if contar_uteis:
                    if data_atual.weekday() < 5 and data_atual not in feriados_br:
                        dias_contados += 1
                else:
                    dias_contados += 1

            st.success(f"🎯 **Prazo Final:** {data_atual.strftime('%d/%m/%Y')}")

# ------------------------------------------
# 10. TAB WHATSAPP
# ------------------------------------------
with t_wpp:
    st.subheader("📲 Notificações via WhatsApp")
    
    numero_wpp = st.text_input("Número com DDD (Ex: 5598912345678)")
    mensagem_wpp = st.text_area("Mensagem")
    
    if st.button("Gerar Link do WhatsApp"):
        if numero_wpp and mensagem_wpp:
            import urllib.parse
            texto_enc = urllib.parse.quote(mensagem_wpp)
            link = f"https://wa.me/{numero_wpp}?text={texto_enc}"
            st.markdown(f"👉 [Clique aqui para abrir no WhatsApp]({link})")

# ------------------------------------------
# 11. TAB IA DO CEJUSC (NOVA INTEGRAÇÃO)
# ------------------------------------------
with t_ia:
    if not API_KEY:
        st.error("⚠️ A chave GEMINI_API_KEY não foi configurada no servidor. Cadastre-a nas variáveis de ambiente do Render.")
    else:
        st.subheader("🤖 IA DO CEJUSC - Automação Jurídica Pré-Processual")
        st.markdown("---")
        
        col_esq, col_dir = st.columns([1, 1], gap="large")

        with col_esq:
            st.subheader("📝 Dados de Entrada")
            
            opcao_escolhida = st.selectbox(
                "Selecione o tipo de documento a ser gerado:",
                (
                    "1 - Relato de Caso", "2 - Certidão Processual", "3 - Sentença / Homologação de Acordo",
                    "4 - Despacho / Decisão", "5 - E-mail Institucional", "6 - Mensagem para WhatsApp",
                    "7 - Dúvidas Gerais", "8 - Termo de Audiência", "9 - Correção de Redação", "10 - Orientações de Documentos"
                ),
                key="ia_opcao_sel"
            )
            opcao_ia = opcao_escolhida.split(" - ")[0]

            if "ia_texto_entrada" not in st.session_state:
                st.session_state.ia_texto_entrada = ""

            audio_ia = st.audio_input("🎙️ Gravar relato falado (Opcional):", key="ia_audio_input")
            
            if audio_ia is not None:
                if st.button("📝 Converter Áudio em Texto", key="btn_transcrever_ia"):
                    with st.spinner("Transcrevendo áudio para o campo de texto..."):
                        try:
                            transcricao = transcrever_audio(audio_ia.read(), audio_ia.type)
                            if st.session_state.ia_texto_entrada.strip():
                                st.session_state.ia_texto_entrada += f"\n{transcricao}"
                            else:
                                st.session_state.ia_texto_entrada = transcricao
                            st.success("Áudio transcrito com sucesso! Verifique o texto abaixo.")
                        except Exception as e:
                            st.error(f"Erro na transcrição: {e}")

            st.session_state.ia_texto_entrada = st.text_area(
                "Insira ou edite as informações do atendimento/rascunho abaixo:",
                value=st.session_state.ia_texto_entrada,
                height=260,
                placeholder="Digite o relato aqui ou grave um áudio acima para transcrever...",
                key="ia_text_area_input"
            )

            btn_processar_ia = st.button("✨ Gerar Documento Jurídico", type="primary", key="btn_processar_ia")

        with col_dir:
            st.subheader("📄 Documento Gerado")
            
            if "ia_resultado_texto" not in st.session_state:
                st.session_state.ia_resultado_texto = ""

            if btn_processar_ia:
                if not st.session_state.ia_texto_entrada.strip():
                    st.warning("⚠️ Insira ou transcreva um texto nos Dados de Entrada antes de gerar.")
                else:
                    with st.spinner("Estruturando o documento jurídico com base nas normas do CEJUSC..."):
                        try:
                            st.session_state.ia_resultado_texto = processar_com_gemini(st.session_state.ia_texto_entrada, opcao_ia)
                        except Exception as e:
                            st.error(f"Erro ao processar: {e}")

            st.text_area(
                "Documento Gerado:",
                value=st.session_state.ia_resultado_texto,
                height=400,
                placeholder="O documento pronto para cópia aparecerá aqui...",
                key="ia_text_area_output"
            )
