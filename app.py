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

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# --- TRAVA ANTI-TRADUÇÃO (ESTRUTURAL) ---
st.markdown("""
    <style>
        /* Compactação de linhas solicitada */
        .stMainBlockContainer { padding-top: 1.5rem !important; }
        div[data-testid="stVerticalBlock"] > div { margin-top: -0.8rem !important; margin-bottom: -0.8rem !important; }
        hr { margin: 0.4rem 0px !important; }
        /* Impede que o tradutor quebre o layout */
        .notranslate { translate: no !important; }
    </style>
    <script>
        document.documentElement.className += ' notranslate';
    </script>
""", unsafe_allow_html=True)

# --- CONEXÃO COM BANCO ---
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

def inicializar_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS tarefas (id SERIAL PRIMARY KEY, tipo TEXT, prazo TEXT, assunto TEXT, descricao TEXT)"))
        conn.commit()
inicializar_db()

# --- ESTADOS DO SISTEMA ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None

# --- FUNÇÕES DE APOIO ---
def obter_estilo(p_str):
    try:
        dv = datetime.strptime(str(p_str), '%Y-%m-%d').date()
        hoje = datetime.now().date()
        dif = (dv - hoje).days
        if dif < 0: return "red", "🔴 VENCIDO"
        elif dif <= 2: return "gold", "🟡 PRÓXIMO"
        else: return "blue", "🔵 FUTURO"
    except: return "blue", "⚪ SEM DATA"

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
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    elementos.append(t)
    doc.build(elementos)
    return buffer.getvalue()

# --- LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.form("login"):
        u, s = st.text_input("Usuário"), st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR"):
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Incorreto")
    st.stop()

# --- INTERFACE PRINCIPAL ---
with st.sidebar:
    st.header("📝 Novo Registro")
    tipos = ["TAREFA", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]
    t_sel = st.selectbox("Tipo", tipos)
    dt_v = st.date_input("Vencimento", format="DD/MM/YYYY") # DATA NO PADRÃO PT-BR
    ass = st.text_input("Assunto")
    des = st.text_area("Descrição")
    if st.button("✅ Salvar", use_container_width=True):
        if ass:
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"),
                             {"t": t_sel, "p": str(dt_v), "a": ass, "de": des})
                conn.commit()
            st.rerun()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# ABAS VOLTARAM (FORA DE QUALQUER BLOCO QUE POSSA OCULTAR)
abas = st.tabs(["🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📝 LEMBRETES", "ℹ️ INFOS", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDAR", "📄 EXTRAIR", "📕 PDF"])

try: df = pd.read_sql("SELECT * FROM tarefas", engine)
except: df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

# ABA INÍCIO (GRÁFICOS CORRIGIDOS)
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
        fig.update_layout(height=180, margin=dict(l=0, r=0, t=20, b=0))
        cols[i].plotly_chart(fig, use_container_width=True)

# LISTAGENS COMPACTAS
def render_aba(tipo, idx):
    with abas[idx]:
        itens = df[df['tipo'] == tipo].sort_values(by='prazo')
        for _, r in itens.iterrows():
            _, txt_st = obter_estilo(r['prazo'])
            data_br = datetime.strptime(r['prazo'], '%Y-%m-%d').strftime('%d/%m/%Y')
            c1, c2, c3, c4 = st.columns([0.15, 0.12, 0.63, 0.1])
            c1.write(txt_st)
            c2.write(data_br)
            if c3.button(f"**{r['assunto']}**", key=f"it_{r['id']}", use_container_width=True):
                st.info(r['descricao'] if r['descricao'] else "Sem descrição")
            if c4.button("🗑️", key=f"del_{r['id']}"):
                with engine.connect() as cn:
                    cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": r['id']})
                    cn.commit()
                st.rerun()
            st.markdown("<hr>", unsafe_allow_html=True)

render_aba("TAREFA", 1); render_aba("COMPROMISSO", 2); render_aba("LEMBRETE", 3)
render_aba("INFORMAÇÃO", 4); render_aba("CONTATO", 5); render_aba("AUDIÊNCIA", 6); render_aba("MODELO", 7)

# CALENDÁRIO
with abas[8]:
    st.write(calendar.month(datetime.now().year, datetime.now().month))

# PDF/EXTRAIR
with abas[10]:
    st.subheader("Gerar PDFs")
    pauta = st.text_area("Cole a pauta aqui:")
    if st.button("Gerar Arquivos"):
        st.write("Processando...")
