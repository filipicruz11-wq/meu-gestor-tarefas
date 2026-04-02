import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

# Configuração da página
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# --- CONEXÃO COM BANCO ---
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

def inicializar_db():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id SERIAL PRIMARY KEY, tipo TEXT, data TEXT, assunto TEXT, descricao TEXT
            )
        """))
        conn.commit()

inicializar_db()

# --- ESTADOS DO SISTEMA ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None
if 'form_reset_key' not in st.session_state: st.session_state.form_reset_key = 0

# Variáveis que guardam o texto dos campos
if 'val_tipo' not in st.session_state: st.session_state.val_tipo = ""
if 'val_data' not in st.session_state: st.session_state.val_data = datetime.now().date()
if 'val_assunto' not in st.session_state: st.session_state.val_assunto = ""
if 'val_desc' not in st.session_state: st.session_state.val_desc = ""

def limpar_e_resetar():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_data = datetime.now().date()
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.form_reset_key += 1 # Muda a key para forçar o reset visual

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .stTextInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #f1f3f5 !important;
        border: 2px solid #ced4da !important;
    }
    /* Cores para os Expanders */
    .vencido { border-left: 10px solid red !important; }
    .proximo { border-left: 10px solid gold !important; }
    .futuro { border-left: 10px solid blue !important; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    u = st.text_input("Usuário")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and s == "123456":
            st.session_state.logado = True
            st.rerun()
        else: st.error("Dados incorretos.")
else:
    # --- BARRA LATERAL (CADASTRO) ---
    with st.sidebar:
        st.header("📝 " + ("Editar Item" if st.session_state.editando_id else "Novo Cadastro"))
        
        # Opções de Tipo com a escolha atual (importante para o editar)
        lista_tipos = ["", "LEMBRETE", "COMPROMISSO"]
        idx_tipo = lista_tipos.index(st.session_state.val_tipo) if st.session_state.val_tipo in lista_tipos else 0
        
        tipo = st.selectbox("Selecione o Tipo", lista_tipos, index=idx_tipo, key=f"t_{st.session_state.form_reset_key}")
        data_venc = st.date_input("Vencimento", value=st.session_state.val_data, format="DD/MM/YYYY", key=f"d_{st.session_state.form_reset_key}")
        assunto = st.text_input("Assunto", value=st.session_state.val_assunto, key=f"a_{st.session_state.form_reset_key}")
        desc = st.text_area("Descrição", value=st.session_state.val_desc, key=f"de_{st.session_state.form_reset_key}")
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Salvar", use_container_width=True):
            if not tipo or not assunto:
                st.error("Preencha Tipo e Assunto!")
            else:
                with engine.connect() as conn:
                    if st.session_state.editando_id:
                        conn.execute(text("UPDATE tarefas SET tipo=:t, data=:d, assunto=:a, descricao=:de WHERE id=:i"),
                                   {"t": tipo, "d": str(data_venc), "a": assunto, "de": desc, "i": st.session_state.editando_id})
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo, data, assunto, descricao) VALUES (:t, :d, :a, :de)"),
                                   {"t": tipo, "d": str(data_venc), "a": assunto, "de": desc})
                    conn.commit()
                st.success("Salvo!")
                limpar_e_resetar()
                st.rerun()
        
        if c2.button("🧹 Limpar", use_container_width=True):
            limpar_e_resetar()
            st.rerun()

    # --- ABAS ---
    t_dash, t_lem, t_com = st.tabs(["🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS"])
    
    df = pd.read_sql("SELECT * FROM tarefas", engine)

    # Função para definir cor e classe CSS
    def obter_estilo(data_str):
        dv = datetime.strptime(data_str, '%Y-%m-%d').date()
        hoje = datetime.now().date()
        dif = (dv - hoje).days
        if dif <= 0: return "red", "vencido"
        elif 1 <= dif <= 2: return "gold", "proximo"
        else: return "blue", "futuro"

    # Aba Dashboard
    with t_dash:
        st.subheader("Visão Geral")
        col_l, col_c = st.columns(2)
        for i, nome in enumerate(["LEMBRETE", "COMPROMISSO"]):
            dff = df[df['tipo'] == nome]
            cts = {"red": 0, "gold": 0, "blue": 0}
            for d in dff['data']:
                cor, _ = obter_estilo(d)
                cts[cor] += 1
            fig = go.Figure(go.Bar(x=[cts["red"], cts["gold"], cts["blue"]],
                                   y=["Vencido", "2 dias", "3+ dias"],
                                   orientation='h', marker_color=["red", "gold", "blue"]))
            fig.update_layout(title=f"{nome}S", height=250, margin=dict(l=10, r=10, t=40, b=10))
            if i == 0: col_l.plotly_chart(fig, use_container_width=True)
            else: col_c.plotly_chart(fig, use_container_width=True)

    # Listas com Cores
    def listar(tipo_nome, tab):
        with tab:
            dff = df[df['tipo'] == tipo_nome].sort_values(by='data')
            if dff.empty: st.info(f"Nenhum {tipo_nome.lower()} encontrado.")
            else:
                for _, row in dff.iterrows():
                    cor_hex, classe_css = obter_estilo(row['data'])
                    dt = datetime.strptime(row['data'], '%Y-%m-%d')
                    dias = {"Monday":"SEGUNDA", "Tuesday":"TERÇA", "Wednesday":"QUARTA", "Thursday":"QUINTA", "Friday":"SEXTA", "Saturday":"SÁBADO", "Sunday":"DOMINGO"}
                    
                    # Criando a linha com cor
                    col_info, col_ed, col_del = st.columns([0.8, 0.1, 0.1])
                    with col_info:
                        # O container ajuda a aplicar a borda colorida lateral
                        with st.container():
                            label = f"**{dias[dt.strftime('%A')]}** | {dt.strftime('%d/%m/%Y')} | {row['assunto']}"
                            # Expander colorido via Markdown (truque visual)
                            cor_emoji = "🔴" if cor_hex == "red" else "🟡" if cor_hex == "gold" else "🔵"
                            with st.expander(f"{cor_emoji} {label}"):
                                st.write(row['descricao'])
                    
                    if col_ed.button("📝", key=f"e_{row['id']}"):
                        # Carrega os dados para o estado
                        st.session_state.editando_id = row['id']
                        st.session_state.val_tipo = row['tipo']
                        st.session_state.val_data = datetime.strptime(row['data'], '%Y-%m-%d').date()
                        st.session_state.val_assunto = row['assunto']
                        st.session_state.val_desc = row['descricao']
                        st.rerun()
                        
                    if col_del.button("🗑️", key=f"d_{row['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": row['id']})
                            conn.commit()
                        st.rerun()

    listar("LEMBRETE", t_lem)
    listar("COMPROMISSO", t_com)
