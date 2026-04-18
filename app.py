import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import calendar

# 1. CONFIGURAÇÃO DA PÁGINA (Precisa ser a primeira coisa)
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# 2. ESTILO CSS (Compactação de linhas)
st.markdown("""
    <style>
        .stMainBlockContainer { padding-top: 1rem !important; }
        div[data-testid="stVerticalBlock"] > div { margin-top: -0.8rem !important; margin-bottom: -0.8rem !important; }
        hr { margin: 0.3rem 0px !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] { height: 40px; white-space: pre-wrap; }
    </style>
""", unsafe_allow_html=True)

# 3. BANCO DE DADOS
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

# 4. LÓGICA DE LOGIN
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.container():
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.button("ENTRAR"):
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Dados Inválidos")
    st.stop()

# --- TUDO ABAIXO SÓ EXECUTA SE ESTIVER LOGADO ---

# 5. CARREGAR DADOS
try:
    df = pd.read_sql("SELECT * FROM tarefas", engine)
except:
    df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

# 6. BARRA LATERAL (CADASTRO)
with st.sidebar:
    st.header("📝 Novo Cadastro")
    t_cad = st.selectbox("Tipo", ["TAREFA", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"])
    d_cad = st.date_input("Vencimento", format="DD/MM/YYYY")
    a_cad = st.text_input("Assunto")
    ds_cad = st.text_area("Descrição")
    
    if st.button("✅ Salvar"):
        if a_cad:
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"),
                             {"t": t_cad, "p": str(d_cad), "a": a_cad, "de": ds_cad})
                conn.commit()
            st.rerun()
    
    st.markdown("---")
    if st.button("🚪 Sair"):
        st.session_state.logado = False
        st.rerun()

# 7. DEFINIÇÃO DAS ABAS (Onde estava o erro)
# Coloquei nomes curtos para garantir que caibam na tela e não sumam
abas = st.tabs(["🏠 INÍCIO", "📌 TAREFAS", "📅 COMPRAS", "📝 LEMBRETES", "ℹ️ INFOS", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO"])

# Função de Status
def pegar_status(prazo):
    try:
        dv = datetime.strptime(str(prazo), '%Y-%m-%d').date()
        hoje = datetime.now().date()
        dif = (dv - hoje).days
        if dif < 0: return "red", "🔴 VENCIDO"
        elif dif <= 2: return "gold", "🟡 PRÓXIMO"
        else: return "blue", "🔵 FUTURO"
    except: return "blue", "⚪ SEM DATA"

# ABA 0: INÍCIO
with abas[0]:
    st.subheader("Dashboard")
    c1, c2, c3 = st.columns(3)
    categorias = ["TAREFA", "COMPROMISSO", "LEMBRETE"]
    for i, cat in enumerate(categorias):
        dff = df[df['tipo'] == cat]
        v = len([p for p in dff['prazo'] if "VENCIDO" in pegar_status(p)[1]])
        p = len([p for p in dff['prazo'] if "PRÓXIMO" in pegar_status(p)[1]])
        f = len(dff) - v - p
        fig = go.Figure(go.Bar(x=[f, p, v], y=["FUTURO", "PRÓXIMO", "VENCIDO"], orientation='h', marker_color=["blue", "gold", "red"]))
        fig.update_layout(height=180, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
        [c1, c2, c3][i].plotly_chart(fig, use_container_width=True)

# FUNÇÃO PARA RENDERIZAR LISTAS (ABAS 1 A 7)
def criar_lista(nome, idx):
    with abas[idx]:
        itens = df[df['tipo'] == nome].sort_values(by='prazo')
        for _, r in itens.iterrows():
            _, txt = pegar_status(r['prazo'])
            data_br = datetime.strptime(r['prazo'], '%Y-%m-%d').strftime('%d/%m/%Y')
            col1, col2, col3, col4 = st.columns([0.15, 0.12, 0.63, 0.1])
            col1.write(txt)
            col2.write(data_br)
            if col3.button(f"**{r['assunto']}**", key=f"b_{r['id']}", use_container_width=True):
                st.info(r['descricao'] if r['descricao'] else "Sem descrição.")
            if col4.button("🗑️", key=f"d_{r['id']}"):
                with engine.connect() as cn:
                    cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": r['id']})
                    cn.commit()
                st.rerun()
            st.markdown("<hr>", unsafe_allow_html=True)

# Chamadas das abas
criar_lista("TAREFA", 1)
criar_lista("COMPROMISSO", 2)
criar_lista("LEMBRETE", 3)
criar_lista("INFORMAÇÃO", 4)
criar_lista("CONTATO", 5)
criar_lista("AUDIÊNCIA", 6)
criar_lista("MODELO", 7)

# ABA 8: CALENDÁRIO
with abas[8]:
    st.write(calendar.month(datetime.now().year, datetime.now().month))
