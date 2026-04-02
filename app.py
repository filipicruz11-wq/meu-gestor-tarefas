import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

# Configuração da página
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# --- CONEXÃO COM BANCO DE DADOS POSTGRES ---
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"

engine = create_engine(DB_URL)

# Criar a tabela se ela não existir
def inicializar_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tarefas (
                    id SERIAL PRIMARY KEY,
                    tipo TEXT,
                    data TEXT,
                    assunto TEXT,
                    descricao TEXT
                )
            """))
            conn.commit()
    except Exception as e:
        st.error(f"Erro ao conectar ao banco: {e}")

inicializar_db()

# --- ESTILIZAÇÃO (CSS) para diferenciar campos brancos ---
st.markdown("""
    <style>
    .stTextInput input, .stTextArea textarea, .stDateInput input {
        background-color: #f1f3f5 !important;
        border: 2px solid #ced4da !important;
        color: #212529 !important;
        border-radius: 5px !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f8f9fa;
        border-radius: 5px 5px 0 0;
        padding: 10px 20px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ESTADOS DO SISTEMA ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None
if 'val_assunto' not in st.session_state: st.session_state.val_assunto = ""
if 'val_desc' not in st.session_state: st.session_state.val_desc = ""

# --- LÓGICA DE STATUS ---
def calcular_status(data_str):
    data_venc = datetime.strptime(data_str, '%Y-%m-%d').date()
    hoje = datetime.now().date()
    dif = (data_venc - hoje).days
    if dif <= 0: return "Vencido", "red"
    elif 1 <= dif <= 2: return "Próximos 2 dias", "gold"
    else: return "3 dias ou mais", "blue"

# --- TELA DE LOGIN ---
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
    # --- BARRA LATERAL (CADASTRO/EDIÇÃO) ---
    with st.sidebar:
        st.header("📝 " + ("Editar Item" if st.session_state.editando_id else "Novo Cadastro"))
        tipo = st.selectbox("Tipo", ["LEMBRETE", "COMPROMISSO"])
        data_venc = st.date_input("Vencimento", format="DD/MM/YYYY")
        assunto = st.text_input("Assunto", value=st.session_state.val_assunto)
        desc = st.text_area("Descrição (clique para expandir na lista)", value=st.session_state.val_desc)
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Salvar"):
            if assunto:
                with engine.connect() as conn:
                    if st.session_state.editando_id:
                        conn.execute(text("UPDATE tarefas SET tipo=:t, data=:d, assunto=:a, descricao=:de WHERE id=:i"),
                                   {"t": tipo, "d": str(data_venc), "a": assunto, "de": desc, "i": st.session_state.editando_id})
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo, data, assunto, descricao) VALUES (:t, :d, :a, :de)"),
                                   {"t": tipo, "d": str(data_venc), "a": assunto, "de": desc})
                    conn.commit()
                # Limpa tudo após salvar
                st.session_state.editando_id = None
                st.session_state.val_assunto = ""
                st.session_state.val_desc = ""
                st.success("Salvo com sucesso!")
                st.rerun()
            else: st.warning("O campo Assunto é obrigatório.")
        
        if c2.button("🧹 Limpar"):
            st.session_state.editando_id = None
            st.session_state.val_assunto = ""
            st.session_state.val_desc = ""
            st.rerun()

    # --- CORPO DO SITE ---
    tab_dashboard, tab_lem, tab_com = st.tabs(["🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS"])
    
    # Carregar dados do Banco
    try:
        df = pd.read_sql("SELECT * FROM tarefas", engine)
    except:
        df = pd.DataFrame(columns=['id', 'tipo', 'data', 'assunto', 'descricao'])

    # ABA INÍCIO (GRÁFICOS)
    with tab_dashboard:
        st.subheader("Visão Geral")
        col_l, col_c = st.columns(2)
        for i, nome in enumerate(["LEMBRETE", "COMPROMISSO"]):
            dff = df[df['tipo'] == nome]
            cts = {"red": 0, "gold": 0, "blue": 0}
            for d in dff['data']:
                _, cor = calcular_status(d)
                cts[cor] += 1
            
            fig = go.Figure(go.Bar(x=[cts["red"], cts["gold"], cts["blue"]],
                                   y=["Vencido", "Até 2 dias", "3+ dias"],
                                   orientation='h', marker_color=["red", "gold", "blue"]))
            fig.update_layout(title=f"{nome}S ({len(dff)})", height=300, margin=dict(l=20, r=20, t=50, b=20))
            if i == 0: col_l.plotly_chart(fig, use_container_width=True)
            else: col_c.plotly_chart(fig, use_container_width=True)

    # FUNÇÃO PARA LISTAR ITENS
    def listar_itens(tipo_nome, tab_obj):
        with tab_obj:
            dff = df[df['tipo'] == tipo_nome].copy()
            if dff.empty:
                st.info(f"Não há {tipo_nome.lower()}s cadastrados.")
            else:
                dff = dff.sort_values(by='data')
                for _, row in dff.iterrows():
                    dt = datetime.strptime(row['data'], '%Y-%m-%d')
                    traducao_dias = {"Monday":"SEGUNDA-FEIRA", "Tuesday":"TERÇA-FEIRA", "Wednesday":"QUARTA-FEIRA", 
                                    "Thursday":"QUINTA-FEIRA", "Friday":"SEXTA-FEIRA", "Saturday":"SÁBADO", "Sunday":"DOMINGO"}
                    dia_semana = traducao_dias[dt.strftime('%A')]
                    
                    # Layout da linha
                    col_info, col_btn_ed, col_btn_del = st.columns([0.7, 0.1, 0.1])
                    
                    with col_info:
                        label = f"**{dia_semana}** | {dt.strftime('%d/%m/%Y')} | **{row['assunto']}**"
                        with st.expander(label):
                            st.write(row['descricao'] if row['descricao'] else "Sem descrição.")
                    
                    if col_btn_ed.button("📝", key=f"edit_{row['id']}"):
                        st.session_state.editando_id = row['id']
                        st.session_state.val_assunto = row['assunto']
                        st.session_state.val_desc = row['descricao']
                        st.rerun()
                        
                    if col_btn_del.button("🗑️", key=f"del_{row['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": row['id']})
                            conn.commit()
                        st.rerun()

    listar_itens("LEMBRETE", tab_lem)
    listar_itens("COMPROMISSO", tab_com)
