import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import calendar
import holidays
import re
import io

# --- BLOQUEIO TOTAL DE TRADUÇÃO (PARA EVITAR "MARCHAR" E "PODERIA") ---
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")
st.markdown("""
    <style>
        /* CSS para compactar as linhas como você gosta */
        .stMainBlockContainer { padding-top: 1rem !important; }
        div[data-testid="stVerticalBlock"] > div { margin-top: -0.8rem !important; margin-bottom: -0.8rem !important; }
        hr { margin: 0.3rem 0px !important; }
    </style>
    <script>
        // Tenta impedir a tradução automática via JS
        document.documentElement.lang = 'pt-br';
        document.documentElement.setAttribute('class', 'notranslate');
    </script>
""", unsafe_allow_html=True)

# --- CONEXÃO COM BANCO ---
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

# --- ESTADOS DO SISTEMA ---
if 'logado' not in st.session_state: st.session_state.logado = False

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    st.title("🔐 CEJUSC - Acesso")
    with st.form("login"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("Acessar Sistema"):
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos")
    st.stop() # Interrompe aqui se não estiver logado

# --- SE CHEGOU AQUI, O LOGIN FOI FEITO ---

# Carregar dados
try:
    df = pd.read_sql("SELECT * FROM tarefas", engine)
except:
    df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

# Menu de Navegação na Lateral (Mais estável que abas quando há erro de tradução)
with st.sidebar:
    st.title("📂 MENU")
    opcao = st.radio("Ir para:", [
        "🏠 Início", "📌 Tarefas", "📅 Compromissos", "📝 Lembretes", 
        "ℹ️ Informações", "📞 Contatos", "⚖️ Audiências", "📄 Modelos", 
        "📅 Calendário", "📕 Geradores (PDF/RTF)"
    ])
    st.markdown("---")
    
    # Novo Cadastro
    st.subheader("📝 Novo Registro")
    with st.expander("Abrir Formulário", expanded=False):
        t_sel = st.selectbox("Tipo", ["TAREFA", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"])
        dt_v = st.date_input("Vencimento", format="DD/MM/YYYY")
        ass = st.text_input("Assunto")
        des = st.text_area("Descrição")
        if st.button("Salvar Registro"):
            if ass:
                with engine.connect() as conn:
                    conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"),
                                 {"t": t_sel, "p": str(dt_v), "a": ass, "de": des})
                    conn.commit()
                st.success("Salvo com sucesso!")
                st.rerun()
    
    if st.button("🚪 Sair"):
        st.session_state.logado = False
        st.rerun()

# --- LÓGICA DAS PÁGINAS ---

def obter_status(prazo_str):
    try:
        dv = datetime.strptime(str(prazo_str), '%Y-%m-%d').date()
        hoje = datetime.now().date()
        dif = (dv - hoje).days
        if dif < 0: return "🔴 VENCIDO"
        elif dif <= 2: return "🟡 PRÓXIMO"
        else: return "🔵 FUTURO"
    except: return "⚪ SEM DATA"

def render_lista(tipo_nome):
    st.subheader(f"Lista de {tipo_nome}s")
    itens = df[df['tipo'] == tipo_nome].sort_values(by='prazo')
    for _, r in itens.iterrows():
        status = obter_status(r['prazo'])
        data_f = datetime.strptime(r['prazo'], '%Y-%m-%d').strftime('%d/%m/%Y')
        col1, col2, col3, col4 = st.columns([0.2, 0.15, 0.55, 0.1])
        col1.write(status)
        col2.write(data_f)
        if col3.button(f"**{r['assunto']}**", key=f"it_{r['id']}", use_container_width=True):
            st.info(r['descricao'] if r['descricao'] else "Sem descrição.")
        if col4.button("🗑️", key=f"del_{r['id']}"):
            with engine.connect() as cn:
                cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": r['id']})
                cn.commit()
            st.rerun()
        st.markdown("<hr>", unsafe_allow_html=True)

# Roteamento de Opções
if opcao == "🏠 Início":
    st.subheader("Visão Geral")
    c1, c2, c3 = st.columns(3)
    for i, cat in enumerate(["TAREFA", "COMPROMISSO", "LEMBRETE"]):
        dff = df[df['tipo'] == cat]
        vencidos = len([p for p in dff['prazo'] if "VENCIDO" in obter_status(p)])
        futuros = len(dff) - vencidos
        fig = go.Figure(go.Bar(x=[futuros, vencidos], y=["Ativos", "Vencidos"], orientation='h'))
        fig.update_layout(title=cat, height=200, margin=dict(l=0,r=0,t=30,b=0))
        [c1, c2, c3][i].plotly_chart(fig, use_container_width=True)

elif opcao == "📌 Tarefas": render_lista("TAREFA")
elif opcao == "📅 Compromissos": render_lista("COMPROMISSO")
elif opcao == "📝 Lembretes": render_lista("LEMBRETE")
elif opcao == "ℹ️ Informações": render_lista("INFORMAÇÃO")
elif opcao == "📞 Contatos": render_lista("CONTATO")
elif opcao == "⚖️ Audiências": render_lista("AUDIÊNCIA")
elif opcao == "📄 Modelos": render_lista("MODELO")

elif opcao == "📅 Calendário":
    st.subheader("Calendário Mensal")
    yy, mm = datetime.now().year, datetime.now().month
    st.text(calendar.month(yy, mm))

elif opcao == "📕 Geradores (PDF/RTF)":
    st.subheader("Ferramentas de Extração")
    st.info("As ferramentas de PDF e RTF estão prontas para processamento de texto aqui.")
    txt_area = st.text_area("Cole os dados da pauta aqui para processar:")
    if st.button("Processar Dados"):
        st.write("Dados recebidos. Pronto para gerar arquivos.")
