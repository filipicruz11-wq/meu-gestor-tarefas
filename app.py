import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import time
import calendar
import holidays

# Configuração da página
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# --- CONEXÃO COM BANCO ---
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

def inicializar_db():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id SERIAL PRIMARY KEY, tipo TEXT, prazo TEXT, assunto TEXT, descricao TEXT
            )
        """))
        conn.commit()

inicializar_db()

# --- CAIXA DE DIÁLOGO (MODAL) ---
@st.dialog("Detalhes da Atividade", width="large")
def exibir_detalhes(assunto, descricao):
    st.markdown(f"### {assunto}")
    if descricao:
        descricao_limpa = descricao.replace("<span>", "").replace("</span>", "")
        descricao_formatada = descricao_limpa.replace("\n", "<br>")
        st.markdown(f'<div class="caixa-texto-fix">{descricao_formatada}</div>', unsafe_allow_html=True)
    else:
        st.write("Sem descrição disponível.")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Fechar", width="stretch"):
        st.rerun()

# --- ESTADOS DO SISTEMA ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None
if 'val_tipo' not in st.session_state: st.session_state.val_tipo = ""
if 'val_prazo' not in st.session_state: st.session_state.val_prazo = datetime.now().date()
if 'val_assunto' not in st.session_state: st.session_state.val_assunto = ""
if 'val_desc' not in st.session_state: st.session_state.val_desc = ""
if 'campo_key' not in st.session_state: st.session_state.campo_key = "init"

# Controle de navegação do calendário
if 'cal_mes' not in st.session_state: st.session_state.cal_mes = datetime.now().month
if 'cal_ano' not in st.session_state: st.session_state.cal_ano = datetime.now().year

def limpar_tudo():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_prazo = datetime.now().date()
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.campo_key = f"limpar_{datetime.now().timestamp()}"

# --- ESTILIZAÇÃO CSS ---
st.markdown(f"""
    <style>
    .caixa-texto-fix {{
        margin-top: 20px !important;
        font-family: sans-serif !important;
        font-size: 14px !important;
        line-height: 1.7 !important;
        color: #1E1E1E !important;
    }}
    .cal-table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; }}
    .cal-header {{ background-color: #f1f3f5; font-weight: bold; text-align: center; padding: 10px; border: 1px solid #dee2e6; }}
    .cal-day {{ height: 100px; width: 14%; text-align: right; vertical-align: top; padding: 10px; border: 1px solid #dee2e6; font-size: 18px; }}
    .dia-util {{ background-color: white; }}
    .dia-fds {{ background-color: #fff5f5; color: #e03131; }} /* Vermelho claro para FDS */
    .dia-feriado {{ background-color: #fff9db; color: #f08c00; font-weight: bold; }} /* Amarelo para Feriados */
    .dia-vazio {{ background-color: #f8f9fa; }}
    </style>
    """, unsafe_allow_html=True)

# --- TELA DE LOGIN (COM SUPORTE A ENTER) ---
if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.form("login_form"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        submit = st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True)
        if submit:
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Dados incorretos.")
else:
    # --- INTERFACE PRINCIPAL ---
    with st.sidebar:
        st.header("📝 " + ("Editar Item" if st.session_state.editando_id else "Novo Cadastro"))
        lista_tipos = ["", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]
        idx_atual = lista_tipos.index(st.session_state.val_tipo) if st.session_state.val_tipo in lista_tipos else 0
        tipo_selecionado = st.selectbox("Selecione o Tipo", lista_tipos, index=idx_atual, key=f"t_{st.session_state.campo_key}")
        
        tipos_sem_prazo = ["INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]
        if tipo_selecionado not in tipos_sem_prazo:
            data_venc = st.date_input("Vencimento", value=st.session_state.val_prazo, format="DD/MM/YYYY", key=f"d_{st.session_state.campo_key}")
        else:
            data_venc = datetime.now().date()
            
        assunto_input = st.text_input("Assunto", value=st.session_state.val_assunto, key=f"a_{st.session_state.campo_key}")
        desc_input = st.text_area("Descrição", value=st.session_state.val_desc, key=f"de_{st.session_state.campo_key}", height=250)
        
        if st.button("✅ Salvar", use_container_width=True):
            if not tipo_selecionado or not assunto_input:
                st.error("Preencha Tipo e Assunto!")
            else:
                with engine.connect() as conn:
                    params = {"t": tipo_selecionado, "p": str(data_venc), "a": str(assunto_input), "de": str(desc_input)}
                    if st.session_state.editando_id:
                        params["i"] = st.session_state.editando_id
                        conn.execute(text("UPDATE tarefas SET tipo=:t, prazo=:p, assunto=:a, descricao=:de WHERE id=:i"), params)
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"), params)
                    conn.commit()
                st.success("Salvo!")
                limpar_tudo()
                st.rerun()
        
        if st.button("🧹 Limpar", use_container_width=True):
            limpar_tudo()
            st.rerun()

    # ABAS
    t_dash, t_lem, t_com, t_info, t_cont, t_aud, t_mod, t_cal = st.tabs([
        "🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS", "ℹ️ INFORMAÇÕES", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO"
    ])

    try:
        df = pd.read_sql("SELECT * FROM tarefas", engine)
    except:
        df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

    # --- FUNÇÕES DE LISTAGEM (Omitidas aqui para brevidade, mantêm-se as mesmas do seu código anterior) ---
    # [Manter funções listar() e listar_simplificado() aqui]

    # --- ABA CALENDÁRIO (NOVA) ---
    with t_cal:
        col_m1, col_m2, col_m3 = st.columns([1, 2, 1])
        with col_m2:
            c1, c2, c3 = st.columns([1, 3, 1])
            if c1.button("⬅️ Anterior"):
                st.session_state.cal_mes -= 1
                if st.session_state.cal_mes < 1:
                    st.session_state.cal_mes = 12
                    st.session_state.cal_ano -= 1
                st.rerun()
            
            meses_pt = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            c2.markdown(f"<h2 style='text-align: center;'>{meses_pt[st.session_state.cal_mes]} {st.session_state.cal_ano}</h2>", unsafe_allow_html=True)
            
            if c3.button("Próximo ➡️"):
                st.session_state.cal_mes += 1
                if st.session_state.cal_mes > 12:
                    st.session_state.cal_mes = 1
                    st.session_state.cal_ano += 1
                st.rerun()

        # Gerar o calendário
        cal = calendar.monthcalendar(st.session_state.cal_ano, st.session_state.cal_mes)
        br_holidays = holidays.BR()
        
        html_cal = '<table class="cal-table"><tr>'
        for sem in ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]:
            html_cal += f'<th class="cal-header">{sem}</th>'
        html_cal += '</tr>'

        for semana in cal:
            html_cal += '<tr>'
            for i, dia in enumerate(semana):
                if dia == 0:
                    html_cal += '<td class="cal-day dia-vazio"></td>'
                else:
                    data_atual = datetime(st.session_state.cal_ano, st.session_state.cal_mes, dia)
                    classe = "dia-util"
                    nome_feriado = br_holidays.get(data_atual)
                    
                    if i >= 5: classe = "dia-fds" # Sábado ou Domingo
                    if nome_feriado: classe = "dia-feriado"
                    
                    conteudo = f"<div>{dia}</div>"
                    if nome_feriado:
                        conteudo += f'<div style="font-size: 10px; color: #f08c00; text-align:center; margin-top:10px;">{nome_feriado}</div>'
                    
                    html_cal += f'<td class="cal-day {classe}">{conteudo}</td>'
            html_cal += '</tr>'
        html_cal += '</table>'
        st.markdown(html_cal, unsafe_allow_html=True)

    # Executar listagens das outras abas
    # [Chamar listar(...) para as outras abas conforme o código anterior]
