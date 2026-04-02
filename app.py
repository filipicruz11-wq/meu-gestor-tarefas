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

# --- CAIXA DE DIÁLOGO (MODAL) ---
@st.dialog("Detalhes da Atividade")
def exibir_detalhes(assunto, descricao):
    st.markdown(f"### {assunto}")
    st.write(descricao if descricao else "Sem descrição disponível.")
    if st.button("Fechar", width="stretch"):
        st.rerun()

# --- ESTADOS DO SISTEMA ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None

if 'val_tipo' not in st.session_state: st.session_state.val_tipo = ""
if 'val_data' not in st.session_state: st.session_state.val_data = datetime.now().date()
if 'val_assunto' not in st.session_state: st.session_state.val_assunto = ""
if 'val_desc' not in st.session_state: st.session_state.val_desc = ""

if 'campo_key' not in st.session_state: st.session_state.campo_key = "init"

def limpar_tudo():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_data = datetime.now().date()
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.campo_key = f"limpar_{datetime.now().timestamp()}"

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .stTextInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #f1f3f5 !important;
        border: 2px solid #ced4da !important;
    }
    [data-testid="column"] {
        display: flex;
        align-items: center;
    }
    hr {
        margin-top: 5px !important;
        margin-bottom: 5px !important;
    }
    /* Estilo para alinhar o texto dos botões à esquerda sem a barra */
    .stButton button {
        text-align: left !important;
        padding-left: 0px !important;
    }
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
    with st.sidebar:
        st.header("📝 " + ("Editar Item" if st.session_state.editando_id else "Novo Cadastro"))
        
        lista_tipos = ["", "LEMBRETE", "COMPROMISSO"]
        idx_atual = lista_tipos.index(st.session_state.val_tipo) if st.session_state.val_tipo in lista_tipos else 0
        
        tipo = st.selectbox("Selecione o Tipo", lista_tipos, index=idx_atual, key=f"t_{st.session_state.campo_key}")
        data_venc = st.date_input("Vencimento", value=st.session_state.val_data, format="DD/MM/YYYY", key=f"d_{st.session_state.campo_key}")
        assunto = st.text_input("Assunto", value=st.session_state.val_assunto, key=f"a_{st.session_state.campo_key}")
        desc = st.text_area("Descrição", value=st.session_state.val_desc, key=f"de_{st.session_state.campo_key}")
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Salvar", width="stretch"):
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
                limpar_tudo()
                st.rerun()
        
        if c2.button("🧹 Limpar", width="stretch"):
            limpar_tudo()
            st.rerun()

    t_dash, t_lem, t_com = st.tabs(["🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS"])
    
    try:
        df = pd.read_sql("SELECT * FROM tarefas", engine)
    except:
        df = pd.DataFrame(columns=['id', 'tipo', 'data', 'assunto', 'descricao'])

    def obter_estilo(data_str):
        dv = datetime.strptime(data_str, '%Y-%m-%d').date()
        hoje = datetime.now().date()
        dif = (dv - hoje).days
        if dif <= 0: return "red", "🔴 VENCIDO"
        elif 1 <= dif <= 2: return "gold", "🟡 PRÓXIMO"
        else: return "blue", "🔵 FUTURO"

    with t_dash:
        st.subheader("Visão Geral")
        col_l, col_c = st.columns(2)
        ordem_categorias = ["3+ dias", "2 dias", "Vencido"]

        for i, nome in enumerate(["LEMBRETE", "COMPROMISSO"]):
            dff = df[df['tipo'] == nome]
            cts = {"red": 0, "gold": 0, "blue": 0}
            for d in dff['data']:
                cor, _ = obter_estilo(d)
                cts[cor] += 1
            
            fig = go.Figure(go.Bar(
                x=[cts["red"], cts["gold"], cts["blue"]],
                y=["Vencido", "2 dias", "3+ dias"],
                orientation='h',
                marker_color=["red", "gold", "blue"],
                text=[cts["red"], cts["gold"], cts["blue"]], 
                textposition='outside',
                cliponaxis=False 
            ))
            fig.update_layout(
                title=f"{nome}S: {len(dff)}", 
                height=250, 
                margin=dict(l=10, r=50, t=40, b=10),
                # OCULTAR EIXO X (Régua de números abaixo do gráfico)
                xaxis=dict(visible=False),
                yaxis=dict(categoryorder='array', categoryarray=ordem_categorias, showgrid=False)
            )
            if i == 0: col_l.plotly_chart(fig, width="stretch")
            else: col_c.plotly_chart(fig, width="stretch")

    def listar(tipo_nome, tab):
        with tab:
            dff = df[df['tipo'] == tipo_nome].sort_values(by='data')
            if dff.empty: st.info(f"Nenhum {tipo_nome.lower()} encontrado.")
            else:
                h1, h2, h3, h4, h5, h6 = st.columns([0.15, 0.12, 0.12, 0.46, 0.075, 0.075])
                h1.caption("STATUS")
                h2.caption("DIA")
                h3.caption("DATA")
                h4.caption("ASSUNTO")
                st.markdown("---")

                for _, row in dff.iterrows():
                    cor_hex, texto_status = obter_estilo(row['data'])
                    dt = datetime.strptime(row['data'], '%Y-%m-%d')
                    dias = {"Monday":"SEGUNDA", "Tuesday":"TERÇA", "Wednesday":"QUARTA", "Thursday":"QUINTA", "Friday":"SEXTA", "Saturday":"SÁBADO", "Sunday":"DOMINGO"}
                    dia_pt = dias[dt.strftime('%A')]
                    data_f = dt.strftime('%d/%m/%Y')
                    
                    c1, c2, c3, c4, c5, c6 = st.columns([0.15, 0.12, 0.12, 0.46, 0.075, 0.075])
                    
                    c1.write(texto_status)
                    c2.write(dia_pt) # Removida a barra |
                    c3.write(data_f) # Removida a barra |
                    
                    # Removida a barra | do botão de assunto
                    if c4.button(f"**{row['assunto']}**", key=f"btn_{row['id']}", width="stretch"):
                        exibir_detalhes(row['assunto'], row['descricao'])
                    
                    if c5.button("📝", key=f"ed_{tipo_nome}_{row['id']}"):
                        st.session_state.editando_id = row['id']
                        st.session_state.val_tipo = row['tipo']
                        st.session_state.val_data = datetime.strptime(row['data'], '%Y-%m-%d').date()
                        st.session_state.val_assunto = row['assunto']
                        st.session_state.val_desc = row['descricao']
                        st.session_state.campo_key = f"edit_{row['id']}_{datetime.now().timestamp()}"
                        st.rerun()
                        
                    if c6.button("🗑️", key=f"del_{tipo_nome}_{row['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": row['id']})
                            conn.commit()
                        st.rerun()
                    
                    st.markdown("---")

    listar("LEMBRETE", t_lem)
    listar("COMPROMISSO", t_com)
