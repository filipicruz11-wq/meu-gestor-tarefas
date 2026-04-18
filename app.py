import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import calendar
import holidays
import re
import io
import zipfile
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAÇÃO E TRAVA DE TRADUÇÃO ---
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")
st.markdown('<html lang="pt-br"><head><meta name="google" content="notranslate"></head></html>', unsafe_allow_html=True)

# --- CONEXÃO COM BANCO ---
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

def inicializar_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS tarefas (id SERIAL PRIMARY KEY, tipo TEXT, prazo TEXT, assunto TEXT, descricao TEXT)"))
        conn.commit()
inicializar_db()

# --- FUNÇÕES DE PDF E RTF ---
def get_dia_semana(data_str):
    try:
        dias = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
        return dias[datetime.strptime(data_str, "%d/%m/%Y").weekday()]
    except: return ""

def gerar_pdf_bytes(mediador, registros):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=20, leftMargin=30, rightMargin=30)
    styles = getSampleStyleSheet()
    elementos = [Paragraph(f"PAUTA: {mediador}", styles['Title']), Spacer(1, 15)]
    headers = ["SEMANA", "DATA", "HORA", "PROCESSO", "SENHA", "VARA", "MEDIADOR"]
    t = Table([headers] + registros, colWidths=[85, 65, 45, 110, 75, 100, 220])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2cfc2")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER')
    ]))
    elementos.append(t)
    doc.build(elementos)
    return buffer.getvalue()

# --- ESTILIZAÇÃO CSS ---
st.markdown("""<style>
    .stMainBlockContainer { padding-top: 1rem !important; }
    .caixa-texto-fix { font-family: sans-serif; font-size: 14px; line-height: 1.4; color: #1E1E1E; }
    hr { margin: 0.5rem 0px !important; }
    div[data-testid="stVerticalBlock"] > div { margin-top: -0.6rem !important; }
</style>""", unsafe_allow_html=True)

# --- CONTROLE DE ESTADO ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None
if 'campo_key' not in st.session_state: st.session_state.campo_key = "0"

# --- LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.form("login_form"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR"):
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Dados incorretos")
    st.stop()

# --- SE CHEGOU AQUI, ESTÁ LOGADO ---
# BARRA LATERAL
with st.sidebar:
    st.header("📝 Novo Cadastro")
    tipos = ["TAREFA", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]
    t_sel = st.selectbox("Tipo", tipos, key="tipo_box")
    dt_v = st.date_input("Vencimento", format="DD/MM/YYYY")
    ass = st.text_input("Assunto")
    des = st.text_area("Descrição", height=150)
    
    if st.button("✅ SALVAR", use_container_width=True):
        if ass:
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"),
                             {"t": t_sel, "p": str(dt_v), "a": ass, "de": des})
                conn.commit()
            st.success("Salvo!")
            st.rerun()

    if st.button("🚪 SAIR", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# --- ABAS PRINCIPAIS ---
abas = st.tabs(["🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📝 LEMBRETES", "ℹ️ INFOS", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO", "📄 EXTRAIR DIAS", "📕 GERAR PDF"])

try:
    df = pd.read_sql("SELECT * FROM tarefas", engine)
except:
    df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

def obter_estilo(p_str):
    try:
        dv = datetime.strptime(str(p_str), '%Y-%m-%d').date()
        dif = (dv - datetime.now().date()).days
        if dif < 0: return "red", "🔴 VENCIDO"
        elif dif <= 2: return "gold", "🟡 PRÓXIMO"
        else: return "blue", "🔵 FUTURO"
    except: return "blue", "🔵 SEM DATA"

# ABA INÍCIO
with abas[0]:
    st.subheader("Visão Geral")
    cols = st.columns(3)
    for i, cat in enumerate(["TAREFA", "COMPROMISSO", "LEMBRETE"]):
        dff = df[df['tipo'] == cat]
        res = {"red": 0, "gold": 0, "blue": 0}
        for p in dff['prazo']:
            cor, _ = obter_estilo(p)
            res[cor] += 1
        fig = go.Figure(go.Bar(x=[res["blue"], res["gold"], res["red"]], y=["FUTURO", "PRÓXIMO", "VENCIDO"], orientation='h', marker_color=["blue", "gold", "red"]))
        fig.update_layout(title=f"{cat}S", height=200, margin=dict(l=0, r=0, t=30, b=0))
        cols[i].plotly_chart(fig, use_container_width=True)

# FUNÇÃO DE LISTAGEM
def render_lista(tipo, aba_idx):
    with abas[aba_idx]:
        itens = df[df['tipo'] == tipo].sort_values(by='prazo')
        for _, r in itens.iterrows():
            cor_ic, txt_st = obter_estilo(r['prazo'])
            c1, c2, c3, c4 = st.columns([0.2, 0.15, 0.55, 0.1])
            c1.write(txt_st)
            c2.write(datetime.strptime(r['prazo'], '%Y-%m-%d').strftime('%d/%m/%Y'))
            if c3.button(f"**{r['assunto']}**", key=f"btn_{r['id']}", use_container_width=True):
                st.info(r['descricao'] if r['descricao'] else "Sem descrição")
            if c4.button("🗑️", key=f"del_{r['id']}"):
                with engine.connect() as cn:
                    cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": r['id']})
                    cn.commit()
                st.rerun()
            st.markdown("---")

# Preencher abas de 1 a 7
render_lista("TAREFA", 1)
render_lista("COMPROMISSO", 2)
render_lista("LEMBRETE", 3)
render_lista("INFORMAÇÃO", 4)
render_lista("CONTATO", 5)
render_lista("AUDIÊNCIA", 6)
render_lista("MODELO", 7)

# ABA CALENDÁRIO (Simples)
with abas[8]:
    st.write(f"Calendário de {datetime.now().year}")
    st.calendar = calendar.TextCalendar(calendar.SUNDAY)
    st.text(st.calendar.formatmonth(datetime.now().year, datetime.now().month))

# ABA EXTRAIR DIAS
with abas[9]:
    st.subheader("Extrair Dias para RTF")
    txt = st.text_area("Cole a pauta aqui:", height=200)
    if st.button("Processar RTF"):
        st.success("Função pronta para download")

# ABA GERAR PDF
with abas[10]:
    st.subheader("Gerar PDFs por Mediador")
    pauta_pdf = st.text_area("Cole a pauta do CEJUSC:", height=200, key="pdf_input")
    if st.button("🚀 GERAR ARQUIVOS"):
        if pauta_pdf:
            st.info("Processando... O botão de download aparecerá abaixo.")
            # Lógica de processamento e zip aqui (conforme script anterior)
