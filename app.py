import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import calendar
import holidays
import time
import re
import io
import zipfile
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Configuração da página
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# --- BLOQUEIO DE TRADUÇÃO AUTOMÁTICA ---
st.markdown("""
    <head>
        <meta name="google" content="notranslate">
    </head>
    """, unsafe_allow_html=True)

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

# --- FUNÇÕES PARA ABA "EXTRAIR DIAS" (RTF) ---
def rtf_unicode(texto):
    resultado = ""
    for char in texto:
        code = ord(char)
        if code > 127: resultado += f"\\u{code}?"
        else: resultado += char
    return resultado

def gerar_rtf_buffer(texto):
    mediadores_dias = defaultdict(list)
    mediadores_horarios = defaultdict(list)
    linhas = texto.split("\n")
    for linha in linhas:
        if not linha.strip(): continue
        colunas = linha.split("\t")
        if len(colunas) < 6: continue
        data_completa = colunas[0].strip()   
        horario = colunas[1].strip()        
        status_proc = colunas[2].upper() if len(colunas) > 2 else ""
        senha_proc = colunas[3].upper() if len(colunas) > 3 else ""
        mediador = colunas[-1].strip()
        if not mediador: continue
        esta_cancelado = "CANCEL" in status_proc or "CANCEL" in senha_proc
        match = re.match(r"(\d{2})/\d{2}/\d{4}", data_completa)
        if match:
            dia = match.group(1)
            info_horario = f"{data_completa} às {horario}"
            if esta_cancelado:
                mediadores_dias["AUDIÊNCIA CANCELADA"].append(dia)
                mediadores_horarios[mediador].append(f"{info_horario} - AUDIÊNCIA CANCELADA")
                mediadores_horarios["AUDIÊNCIA CANCELADA"].append(f"{info_horario} - AUDIÊNCIA CANCELADA")
            else:
                mediadores_dias[mediador].append(dia)
                mediadores_horarios[mediador].append(info_horario)

    mediadores_ordenados = sorted(mediadores_horarios.keys(), key=lambda n: (1 if "CANCEL" in n.upper() else 0, n.upper()))
    output = io.StringIO()
    output.write(r"{\rtf1\ansi\deff0{\fonttbl{\f0 Bookman Old Style;}}\fs24\f0 ")
    output.write(rtf_unicode(r"{\b\fs28 LISTA DE DIAS}\par\par "))
    for med in mediadores_ordenados:
        dias_lista = sorted(mediadores_dias[med], key=lambda x: int(x) if x.isdigit() else 0)
        dias_str = rtf_unicode(", ".join(dias_lista) + ".") if dias_lista else ""
        output.write(rtf_unicode(med + ": ") + r"\b " + dias_str + r"\b0\par ")
    output.write(r"\page ")
    output.write(rtf_unicode(r"{\b\fs28 DETALHAMENTO DE HORÁRIOS}\par\par "))
    for med in mediadores_ordenados:
        output.write(r"\b " + rtf_unicode(med + ":") + r"\b0\par ")
        for info in mediadores_horarios[med]:
            output.write(rtf_unicode("  - " + info) + r"\par ")
        output.write(r"\par ")
    output.write("}")
    return output.getvalue()

# --- FUNÇÕES PARA ABA "GERAR PDF" ---
def get_dia_semana(data_str):
    try:
        dias = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
        data = datetime.strptime(data_str, "%d/%m/%Y")
        return dias[data.weekday()]
    except: return ""

def gerar_pdf_bytes(mediador, registros):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=20, leftMargin=30, rightMargin=30)
    styles = getSampleStyleSheet()
    elementos = [Paragraph(mediador, styles['Title']), Spacer(1, 15)]
    headers = ["SEMANA", "DATA", "HORA", "PROCESSO", "SENHA", "VARA", "MEDIADOR"]
    t = Table([headers] + registros, colWidths=[85, 65, 45, 110, 75, 100, 220])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2cfc2")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#fff9c4")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    elementos.append(t)
    doc.build(elementos)
    return buffer.getvalue()

# --- CAIXA DE DIÁLOGO: DETALHES ---
@st.dialog("Detalhes da Atividade", width="large")
def exibir_detalhes(assunto, descricao):
    st.markdown(f"### {assunto}")
    if descricao:
        desc_f = descricao.replace("\n", "<br>")
        st.markdown(f'<div class="caixa-texto-fix" style="white-space: pre-wrap; word-wrap: break-word;">{desc_f}</div>', unsafe_allow_html=True)
    else: st.write("Sem descrição disponível.")
    if st.button("Fechar", width="stretch"): st.rerun()

# --- ESTADOS E LOGIN ---
if "logged" in st.query_params and st.query_params["logged"] == "true": st.session_state.logado = True
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None
if 'campo_key' not in st.session_state: st.session_state.campo_key = "init"
if 'val_tipo' not in st.session_state: st.session_state.val_tipo = ""
if 'val_assunto' not in st.session_state: st.session_state.val_assunto = ""
if 'val_desc' not in st.session_state: st.session_state.val_desc = ""
if 'val_prazo' not in st.session_state: st.session_state.val_prazo = datetime.now().date()
if 'cal_mes' not in st.session_state: st.session_state.cal_mes = datetime.now().month
if 'cal_ano' not in st.session_state: st.session_state.cal_ano = datetime.now().year

def limpar_tudo():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.val_prazo = datetime.now().date()
    st.session_state.campo_key = f"k_{datetime.now().timestamp()}"

# --- ESTILIZAÇÃO CSS ---
st.markdown("""<style>
    .caixa-texto-fix { margin-top: 10px !important; font-family: sans-serif !important; font-size: 14px !important; line-height: 1.6 !important; color: #1E1E1E !important; }
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; background-color: #f8f9fa; border: 2px solid #adb5bd; }
    .cal-header { background-color: #e9ecef; font-weight: bold; text-align: center; padding: 8px; border: 1px solid #adb5bd; }
    .cal-day { height: 85px; text-align: right; vertical-align: top; padding: 5px; border: 1px solid #adb5bd; }
    .dia-util { background-color: #ffffff; }
    .dia-fds { background-color: #fff5f5; color: #e03131; }
    .dia-feriado { background-color: #fff9db; color: #f08c00; font-weight: bold; }
    .dia-vazio { background-color: #f1f3f5; }
    </style>""", unsafe_allow_html=True)

if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.form("login"):
        u, s = st.text_input("Usuário"), st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR"):
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.query_params["logged"] = "true"
                st.rerun()
            else: st.error("Dados incorretos.")
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📝 " + ("Editar" if st.session_state.editando_id else "Novo"))
        tipos = ["", "TAREFA", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]
        try: idx = tipos.index(st.session_state.val_tipo)
        except: idx = 0
        t_sel = st.selectbox("Tipo", tipos, index=idx, key=f"s_{st.session_state.campo_key}")
        dt_v = st.date_input("Vencimento", value=st.session_state.val_prazo, key=f"d_{st.session_state.campo_key}") if t_sel in ["TAREFA", "LEMBRETE", "COMPROMISSO", ""] else datetime.now().date()
        ass = st.text_input("Assunto", value=st.session_state.val_assunto, key=f"a_{st.session_state.campo_key}")
        des = st.text_area("Descrição", value=st.session_state.val_desc, height=250, key=f"tx_{st.session_state.campo_key}")
        if st.button("✅ Salvar"):
            if not t_sel or not ass: st.error("Preencha Tipo e Assunto!")
            else:
                with engine.connect() as conn:
                    p = {"t": t_sel, "p": str(dt_v), "a": ass, "de": des}
                    if st.session_state.editando_id:
                        p["i"] = st.session_state.editando_id
                        conn.execute(text("UPDATE tarefas SET tipo=:t, prazo=:p, assunto=:a, descricao=:de WHERE id=:i"), p)
                    else: conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"), p)
                    conn.commit()
                st.success("Salvo!"); limpar_tudo(); st.rerun()
        if st.button("🧹 Limpar"): limpar_tudo(); st.rerun()
        if st.button("🚪 Sair"): st.session_state.logado = False; st.query_params.clear(); st.rerun()

    # --- ABAS ---
    tabs = st.tabs(["🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📝 LEMBRETES", "ℹ️ INFORMAÇÕES", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO", "📄 EXTRAIR DIAS", "📕 GERAR PDF"])
    t_dash, t_tar, t_com, t_lem, t_info, t_cont, t_aud, t_mod, t_cal, t_ext, t_pdf = tabs

    try: df = pd.read_sql("SELECT * FROM tarefas", engine)
    except: df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

    def obter_estilo(p_str):
        try:
            dv = datetime.strptime(str(p_str), '%Y-%m-%d').date()
            hoje = datetime.now().date()
            dif = (dv - hoje).days
            if dif <= 0: return "red", "🔴 VENCIDO"
            elif 1 <= dif <= 2: return "gold", "🟡 PRÓXIMO"
            else: return "blue", "🔵 FUTURO"
        except: return "blue", "🔵 SEM DATA"

    # --- DASHBOARD ---
    with t_dash:
        st.subheader("Visão Geral")
        cols = st.columns(3)
        for i, nome in enumerate(["TAREFA", "COMPROMISSO", "LEMBRETE"]):
            dff = df[df['tipo'] == nome]
            cts = {"red": 0, "gold": 0, "blue": 0}
            for p in dff['prazo'].dropna():
                cor, _ = obter_estilo(p)
                cts[cor] += 1
            fig = go.Figure(go.Bar(x=[cts["blue"], cts["gold"], cts["red"]], y=["3+ dias", "2 dias", "Vencido"], orientation='h', marker_color=["blue", "gold", "red"]))
            fig.update_layout(title=f"{nome}S", height=230, margin=dict(l=10, r=50, t=40, b=10), xaxis=dict(visible=False))
            cols[i].plotly_chart(fig, use_container_width=True)

    # --- EXTRAIR DIAS ---
    with t_ext:
        st.subheader("Gerador de Lista de Dias (RTF)")
        p_in = st.text_area("Cole a pauta para RTF:", height=250)
        if st.button("🚀 Gerar RTF"):
            if p_in.strip():
                st.download_button("⬇️ Baixar DIAS.rtf", gerar_rtf_buffer(p_in), "DIAS.rtf", "application/rtf")
            else: st.error("Cole os dados primeiro.")

    # --- GERAR PDF ---
    with t_pdf:
        st.subheader("Gerador de PDFs por Mediador")
        p_pdf = st.text_area("Cole a pauta para PDF:", height=250)
        if st.button("📕 Gerar Todos os PDFs"):
            if not p_pdf.strip(): st.error("Cole os dados primeiro.")
            else:
                dados_med = defaultdict(list)
                linhas = p_pdf.strip().split("\n")
                for linha in linhas:
                    match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})\s+(\d{7}-\d{2}\.\d{4})\s+(.*)", linha.strip())
                    if match:
                        dt, hr, proc, resto = match.groups()
                        if "SEM DISPONIBILIDADE" in resto.upper(): m_ch = "SEM DISPONIBILIDADE"; miolo = resto.upper().split("SEM DISPONIBILIDADE")[0].strip()
                        elif "AUDIÊNCIA CANCELADA" in resto.upper(): m_ch = "AUDIÊNCIA CANCELADA"; miolo = resto.upper().split("AUDIÊNCIA CANCELADA")[0].strip()
                        elif "SIM" in resto: p_sim = resto.rsplit("SIM", 1); miolo, m_ch = p_sim[0].strip(), p_sim[1].strip()
                        else: p_res = resto.rsplit(maxsplit=1); miolo, m_ch = (p_res[0], p_res[1]) if len(p_res)>1 else ("", "OUTROS")
                        
                        p_mio = miolo.split(maxsplit=1)
                        sen, var = ("", miolo)
                        if p_mio and ("ª" not in p_mio[0] and "º" not in p_mio[0]): sen, var = p_mio[0], (p_mio[1] if len(p_mio)>1 else "")
                        dados_med[m_ch].append([get_dia_semana(dt), dt, hr, proc, sen, var, m_ch])
                
                if dados_med:
                    z_buf = io.BytesIO()
                    with zipfile.ZipFile(z_buf, "a", zipfile.ZIP_DEFLATED) as zf:
                        for m, rs in dados_med.items(): zf.writestr(f"{m.replace(' ','_')}.pdf", gerar_pdf_bytes(m, rs))
                    st.success(f"{len(dados_med)} mediadores identificados.")
                    st.download_button("📥 BAIXAR PDFs (.ZIP)", z_buf.getvalue(), "pautas_cejusc.zip", "application/zip")

    # --- LISTAGENS ---
    def listar(tipo, tab):
        with tab:
            dff = df[df['tipo'] == tipo].sort_values(by='prazo')
            for _, r in dff.iterrows():
                _, st_t = obter_estilo(r['prazo'])
                c1, c2, c3, c4, c5, c6 = st.columns([0.15, 0.12, 0.12, 0.46, 0.075, 0.075])
                c1.write(st_t); c2.write(datetime.strptime(r['prazo'], '%Y-%m-%d').strftime('%d/%m/%Y'))
                if c4.button(f"**{r['assunto']}**", key=f"b_{r['id']}", use_container_width=True): exibir_detalhes(r['assunto'], r['descricao'])
                if c5.button("📝", key=f"e_{r['id']}"):
                    st.session_state.editando_id, st.session_state.val_tipo, st.session_state.val_assunto, st.session_state.val_desc, st.session_state.val_prazo = r['id'], r['tipo'], r['assunto'], r['descricao'], datetime.strptime(r['prazo'], '%Y-%m-%d').date()
                    st.session_state.campo_key = f"ed_{r['id']}"; st.rerun()
                if c6.button("🗑️", key=f"d_{r['id']}"):
                    with engine.connect() as cn: cn.execute(text("DELETE FROM tarefas WHERE id=:i"),{"i":r['id']}); cn.commit()
                    st.rerun()
                st.markdown("---")

    def listar_s(tipo, tab, ic):
        with tab:
            dff = df[df['tipo'] == tipo].sort_values(by='assunto')
            for _, r in dff.iterrows():
                c1, c2, c3 = st.columns([0.85, 0.075, 0.075])
                if c1.button(f"{ic} **{r['assunto']}**", key=f"s_{r['id']}", use_container_width=True): exibir_detalhes(r['assunto'], r['descricao'])
                if c2.button("📝", key=f"es_{r['id']}"):
                    st.session_state.editando_id, st.session_state.val_tipo, st.session_state.val_assunto, st.session_state.val_desc = r['id'], r['tipo'], r['assunto'], r['descricao']
                    st.session_state.campo_key = f"ed_s_{r['id']}"; st.rerun()
                if c3.button("🗑️", key=f"ds_{r['id']}"):
                    with engine.connect() as cn: cn.execute(text("DELETE FROM tarefas WHERE id=:i"),{"i":r['id']}); cn.commit()
                    st.rerun()
                st.markdown("---")

    listar("TAREFA", t_tar); listar("COMPROMISSO", t_com); listar("LEMBRETE", t_lem)
    listar_s("INFORMAÇÃO", t_info, "📌"); listar_s("CONTATO", t_cont, "📞"); listar_s("AUDIÊNCIA", t_aud, "⚖️"); listar_s("MODELO", t_mod, "📄")

    # --- CALENDÁRIO ---
    with t_cal:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            n1, n2, n3 = st.columns([1,2,1])
            if n1.button("⬅️"):
                st.session_state.cal_mes -= 1
                if st.session_state.cal_mes < 1: st.session_state.cal_mes, st.session_state.cal_ano = 12, st.session_state.cal_ano-1
                st.rerun()
            n2.markdown(f"<h4 style='text-align:center'>{st.session_state.cal_mes}/{st.session_state.cal_ano}</h4>", unsafe_allow_html=True)
            if n3.button("➡️"):
                st.session_state.cal_mes += 1
                if st.session_state.cal_mes > 12: st.session_state.cal_mes, st.session_state.cal_ano = 1, st.session_state.cal_ano+1
                st.rerun()
        cal = calendar.monthcalendar(st.session_state.cal_ano, st.session_state.cal_mes)
        br_h = holidays.BR()
        h = '<table class="cal-table"><tr>'
        for sem in ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"]: h += f'<th class="cal-header">{sem}</th>'
        h += '</tr>'
        for sema in cal:
            h += '<tr>'
            for i, d in enumerate(sema):
                if d==0: h += '<td class="cal-day dia-vazio"></td>'
                else:
                    dt_at = datetime(st.session_state.cal_ano, st.session_state.cal_mes, d)
                    cl = "dia-fds" if i in [0,6] else "dia-util"
                    if br_h.get(dt_at): cl = "dia-feriado"
                    h += f'<td class="cal-day {cl}"><b>{d}</b></td>'
            h += '</tr>'
        st.markdown(h+'</table>', unsafe_allow_html=True)
