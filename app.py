import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import sqlite3

# Configuração da página
st.set_page_config(page_title="Gestor de Tarefas", layout="wide")

# --- ESTILIZAÇÃO (CSS) ---
st.markdown("""
    <style>
    .stTextInput insert, .stTextArea textarea, .stDateInput input {
        background-color: #f0f2f6 !important;
        border: 1px solid #d1d5db !important;
        color: #31333f !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- BANCO DE DADOS (SQLITE) ---
def conectar_db():
    conn = sqlite3.connect('agenda.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            data TEXT,
            assunto TEXT,
            descricao TEXT
        )
    ''')
    conn.commit()
    return conn

db = conectar_db()

# --- INICIALIZAÇÃO DO ESTADO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'editando_id' not in st.session_state:
    st.session_state.editando_id = None
if 'temp_assunto' not in st.session_state:
    st.session_state.temp_assunto = ""
if 'temp_desc' not in st.session_state:
    st.session_state.temp_desc = ""

# --- FUNÇÕES DE APOIO ---
def calcular_status(data_str):
    data_venc = datetime.strptime(data_str, '%Y-%m-%d').date()
    hoje = datetime.now().date()
    diferenca = (data_venc - hoje).days
    if diferenca <= 0: return "Vencido", "red"
    elif 1 <= diferenca <= 2: return "Próximos 2 dias", "gold"
    else: return "3 dias ou mais", "blue"

def salvar_tarefa(tipo, data, assunto, descricao):
    cursor = db.cursor()
    if st.session_state.editando_id:
        cursor.execute('UPDATE tarefas SET tipo=?, data=?, assunto=?, descricao=? WHERE id=?',
                       (tipo, data, assunto, descricao, st.session_state.editando_id))
        st.session_state.editando_id = None
    else:
        cursor.execute('INSERT INTO tarefas (tipo, data, assunto, descricao) VALUES (?, ?, ?, ?)',
                       (tipo, data, assunto, descricao))
    db.commit()
    st.session_state.temp_assunto = ""
    st.session_state.temp_desc = ""

# --- LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Acesso ao Sistema")
    u = st.text_input("Usuário")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and s == "123456":
            st.session_state.logado = True
            st.rerun()
        else: st.error("Incorreto")
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📝 " + ("Editando" if st.session_state.editando_id else "Cadastro"))
        tipo = st.selectbox("Tipo", ["LEMBRETE", "COMPROMISSO"])
        data_venc = st.date_input("Data de Vencimento", format="DD/MM/YYYY")
        assunto = st.text_input("Assunto", value=st.session_state.temp_assunto)
        desc = st.text_area("Descrição", value=st.session_state.temp_desc)
        
        c1, c2 = st.columns(2)
        if c1.button("Salvar"):
            if assunto:
                salvar_tarefa(tipo, str(data_venc), assunto, desc)
                st.success("Sucesso!")
                st.rerun()
            else: st.warning("Falta assunto")
        
        if c2.button("Limpar"):
            st.session_state.editando_id = None
            st.session_state.temp_assunto = ""
            st.session_state.temp_desc = ""
            st.rerun()

    # --- CORPO PRINCIPAL ---
    tab_ini, tab_lem, tab_com = st.tabs(["🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS"])

    df = pd.read_sql_query("SELECT * FROM tarefas", db)

    with tab_ini:
        st.header("Gráficos de Status")
        col1, col2 = st.columns(2)
        for i, t_nome in enumerate(["LEMBRETE", "COMPROMISSO"]):
            dff = df[df['tipo'] == t_nome]
            counts = {"red": 0, "gold": 0, "blue": 0}
            for d in dff['data']:
                _, cor = calcular_status(d)
                counts[cor] += 1
            
            fig = go.Figure(go.Bar(x=[counts["red"], counts["gold"], counts["blue"]],
                                   y=["Vencido", "2 dias", "3+ dias"],
                                   orientation='h', marker_color=["red", "gold", "blue"]))
            fig.update_layout(title=f"Total de {t_nome}s", height=300)
            if i == 0: col1.plotly_chart(fig, use_container_width=True)
            else: col2.plotly_chart(fig, use_container_width=True)

    def mostrar_lista(t_nome, tab_alvo):
        with tab_alvo:
            dff = df[df['tipo'] == t_nome].copy()
            if not dff.empty:
                dff = dff.sort_values(by='data')
                for _, row in dff.iterrows():
                    dt = datetime.strptime(row['data'], '%Y-%m-%d')
                    dias = {"Monday":"SEGUNDA", "Tuesday":"TERÇA", "Wednesday":"QUARTA", "Thursday":"QUINTA", "Friday":"SEXTA", "Saturday":"SÁBADO", "Sunday":"DOMINGO"}
                    header = f"**{dias[dt.strftime('%A')]}** | {dt.strftime('%d/%m/%Y')} | {row['assunto']}"
                    
                    c_txt, c_ed, c_del = st.columns([0.7, 0.1, 0.1])
                    with c_txt:
                        with st.expander(header): st.write(row['descricao'])
                    if c_ed.button("📝", key=f"e{row['id']}"):
                        st.session_state.editando_id = row['id']
                        st.session_state.temp_assunto = row['assunto']
                        st.session_state.temp_desc = row['descricao']
                        st.rerun()
                    if c_del.button("🗑️", key=f"d{row['id']}"):
                        db.cursor().execute('DELETE FROM tarefas WHERE id=?', (row['id'],))
                        db.commit()
                        st.rerun()
            else: st.info("Vazio")

    mostrar_lista("LEMBRETE", tab_lem)
    mostrar_lista("COMPROMISSO", tab_com)
