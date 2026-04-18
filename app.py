import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import calendar

# 1. Configuração inicial (Sempre no topo)
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# 2. CSS para garantir o espaçamento compacto que você gosta
st.markdown("""
    <style>
        .stMainBlockContainer { padding-top: 1rem !important; }
        div[data-testid="stVerticalBlock"] > div { margin-top: -0.8rem !important; margin-bottom: -0.8rem !important; }
        hr { margin: 0.3rem 0px !important; }
    </style>
""", unsafe_allow_html=True)

# 3. Conexão com o Banco de Dados
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

# 4. Controle de Login (Simples e Direto)
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🔐 Acesso")
    u = st.text_input("Usuário")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and s == "123456":
            st.session_state.logado = True
            st.rerun()
    st.stop()

# --- A PARTIR DAQUI TUDO SÓ APARECE SE ESTIVER LOGADO ---

# 5. Barra Lateral de Cadastro
with st.sidebar:
    st.header("📝 Novo Registro")
    tipo_cad = st.selectbox("Tipo", ["TAREFA", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"])
    data_cad = st.date_input("Vencimento", format="DD/MM/YYYY")
    assunto_cad = st.text_input("Assunto")
    desc_cad = st.text_area("Descrição")
    
    if st.button("✅ Salvar"):
        if assunto_cad:
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"),
                             {"t": tipo_cad, "p": str(data_cad), "a": assunto_cad, "de": desc_cad})
                conn.commit()
            st.rerun()
    
    if st.button("🚪 Sair"):
        st.session_state.logado = False
        st.rerun()

# 6. Definição das Abas (Exatamente como você tinha antes)
abas = st.tabs(["🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📝 LEMBRETES", "ℹ️ INFOS", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO"])

# 7. Carregar os dados
try:
    df = pd.read_sql("SELECT * FROM tarefas", engine)
except:
    df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

# 8. Função de Cores para o Início
def cor_status(prazo):
    try:
        dv = datetime.strptime(str(prazo), '%Y-%m-%d').date()
        dif = (dv - datetime.now().date()).days
        if dif < 0: return "red", "🔴 VENCIDO"
        elif dif <= 2: return "gold", "🟡 PRÓXIMO"
        else: return "blue", "🔵 FUTURO"
    except: return "blue", "⚪ SEM DATA"

# --- CONTEÚDO DAS ABAS ---

# Aba Início
with abas[0]:
    st.subheader("Visão Geral")
    c1, c2, c3 = st.columns(3)
    for i, cat in enumerate(["TAREFA", "COMPROMISSO", "LEMBRETE"]):
        dff = df[df['tipo'] == cat]
        v = len([p for p in dff['prazo'] if "VENCIDO" in cor_status(p)[1]])
        p = len([p for p in dff['prazo'] if "PRÓXIMO" in cor_status(p)[1]])
        f = len(dff) - v - p
        fig = go.Figure(go.Bar(x=[f, p, v], y=["FUTURO", "PRÓXIMO", "VENCIDO"], orientation='h', marker_color=["blue", "gold", "red"]))
        fig.update_layout(height=180, margin=dict(l=0, r=0, t=20, b=0))
        [c1, c2, c3][i].plotly_chart(fig, use_container_width=True)

# Função para as listas (Aba 1 a 7)
def mostrar_lista(nome_tipo, aba_id):
    with abas[aba_id]:
        filtrado = df[df['tipo'] == nome_tipo].sort_values(by='prazo')
        for _, r in filtrado.iterrows():
            _, txt = cor_status(r['prazo'])
            dt_br = datetime.strptime(r['prazo'], '%Y-%m-%d').strftime('%d/%m/%Y')
            col1, col2, col3, col4 = st.columns([0.15, 0.12, 0.63, 0.1])
            col1.write(txt)
            col2.write(dt_br)
            if col3.button(f"**{r['assunto']}**", key=f"btn_{r['id']}", use_container_width=True):
                st.info(r['descricao'] if r['descricao'] else "Sem descrição")
            if col4.button("🗑️", key=f"ex_{r['id']}"):
                with engine.connect() as cn:
                    cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": r['id']})
                    cn.commit()
                st.rerun()
            st.markdown("<hr>", unsafe_allow_html=True)

mostrar_lista("TAREFA", 1)
mostrar_lista("COMPROMISSO", 2)
mostrar_lista("LEMBRETE", 3)
mostrar_lista("INFORMAÇÃO", 4)
mostrar_lista("CONTATO", 5)
mostrar_lista("AUDIÊNCIA", 6)
mostrar_lista("MODELO", 7)

# Aba Calendário
with abas[8]:
    st.text(calendar.month(datetime.now().year, datetime.now().month))
