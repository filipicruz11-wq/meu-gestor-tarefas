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

# Imports específicos para o Gerador de PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAÇÃO DA PÁGINA ---
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

# --- FUNÇÕES DO GERADOR PDF (LÓGICA PARALELA) ---
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
    elementos = [Paragraph(f"<b>MEDIADOR(A): {mediador}</b>", styles['Title']), Spacer(1, 15)]
    
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

# --- FUNÇÕES DO GERADOR RTF (JÁ EXISTENTES) ---
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
        data_completa, horario = colunas[0].strip(), colunas[1].strip()
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
                texto_cancelado = f"{info_horario} - AUDIÊNCIA CANCELADA"
                mediadores_horarios[mediador].append(texto_cancelado)
                mediadores_horarios["AUDIÊNCIA CANCELADA"].append(texto_cancelado)
            else:
                mediadores_dias[mediador].append(dia)
                mediadores_horarios[mediador].append(info_horario)

    mediadores_ordenados = sorted(mediadores_horarios.keys(), key=lambda n: (1 if "CANCEL" in n.upper() else 2 if "DISP" in n.upper() else 0, n.upper()))
    output = io.StringIO()
    output.write(r"{\rtf1\ansi\deff0{\fonttbl{\f0 Bookman Old Style;}}\fs24\f0 ")
    output.write(rtf_unicode(r"{\b\fs28 LISTA DE DIAS}\par\par "))
    for med in mediadores_ordenados:
        dias_lista = sorted(mediadores_dias[med], key=lambda x: int(x) if x.isdigit() else 0)
        output.write(rtf_unicode(med + ": ") + (r"\b " + rtf_unicode(", ".join(dias_lista) + ".") + r"\b0\par " if dias_lista else r"\par "))
    output.write(r"\page " + rtf_unicode(r"{\b\fs28 DETALHAMENTO DE HORÁRIOS}\par\par "))
    for med in mediadores_ordenados:
        output.write(r"\b " + rtf_unicode(med + ":") + r"\b0\par ")
        for info in mediadores_horarios[med]: output.write(rtf_unicode("  - " + info) + r"\par ")
        output.write(r"\par ")
    output.write("}")
    return output.getvalue()

# --- INTERFACE E LOGIN (RESUMIDO PARA O EXEMPLO) ---
if 'logado' not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.form("login"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR"):
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.rerun()
else:
    # --- SIDEBAR E ESTADOS (Omitidos aqui por brevidade, mas devem permanecer iguais ao seu original) ---
    # ... (Seu código de Sidebar, limpar_tudo, CSS deve continuar aqui) ...

    # --- ABAS ---
    t_dash, t_tar, t_com, t_lem, t_info, t_cont, t_aud, t_mod, t_cal, t_ext, t_pdf = st.tabs([
        "🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📝 LEMBRETES", "ℹ️ INFORMAÇÕES", 
        "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO", "📄 EXTRAIR DIAS", "📑 GERAR PDF"
    ])

    try: df = pd.read_sql("SELECT * FROM tarefas", engine)
    except: df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

    # (Funções listar e ABA INÍCIO permanecem iguais)
    # ...

    # --- ABA EXTRAIR DIAS (RTF) ---
    with t_ext:
        st.subheader("Gerador de Lista de Dias (RTF)")
        pauta_rtf = st.text_area("Dados da Pauta (RTF)", height=200)
        if st.button("🚀 Gerar RTF"):
            if pauta_rtf:
                st.download_button("⬇️ Baixar DIAS.rtf", gerar_rtf_buffer(pauta_rtf), "DIAS.rtf", "application/rtf")

    # --- ABA NOVA: GERAR PDF (PARALELA) ---
    with t_pdf:
        st.subheader("📄 Gerador de PDFs Individuais (ZIP)")
        st.write("Esta ferramenta gera um PDF colorido para cada mediador em um arquivo ZIP.")
        texto_pauta_pdf = st.text_area("Cole a pauta aqui para PDF:", height=300, key="txt_pdf_area")

        if st.button("📥 GERAR E COMPACTAR PDFs"):
            if not texto_pauta_pdf.strip():
                st.warning("Cole os dados primeiro.")
            else:
                dados_por_mediador = defaultdict(list)
                linhas = texto_pauta_pdf.strip().split("\n")
                
                for linha in linhas:
                    linha = linha.strip()
                    if not linha: continue
                    # Regex para capturar o padrão da sua pauta
                    match_base = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})\s+(\d{7}-\d{2}\.\d{4})\s+(.*)", linha)
                    if match_base:
                        data_pt, hora_pt, processo, resto = match_base.groups()
                        if "SEM DISPONIBILIDADE" in resto.upper(): 
                            mediador_chave = "SEM DISPONIBILIDADE"; miolo = resto.upper().split("SEM DISPONIBILIDADE")[0].strip()
                        elif "AUDIÊNCIA CANCELADA" in resto.upper(): 
                            mediador_chave = "AUDIÊNCIA CANCELADA"; miolo = resto.upper().split("AUDIÊNCIA CANCELADA")[0].strip()
                        elif "SIM" in resto: 
                            partes_sim = resto.rsplit("SIM", 1); miolo = partes_sim[0].strip(); mediador_chave = partes_sim[1].strip()
                        else: 
                            partes = resto.rsplit(maxsplit=1); miolo = partes[0] if len(partes) > 1 else ""; mediador_chave = partes[1] if len(partes) > 1 else "OUTROS"
                        
                        partes_miolo = miolo.split(maxsplit=1)
                        senha = ""; vara = miolo
                        if partes_miolo:
                            primeira = partes_miolo[0]
                            if "ª" not in primeira and "º" not in primeira or primeira.upper() == "CANCELADA":
                                senha = primeira; vara = partes_miolo[1] if len(partes_miolo) > 1 else ""
                        
                        dados_por_mediador[mediador_chave].append([get_dia_semana(data_pt), data_pt, hora_pt, processo, senha, vara, mediador_chave])

                if dados_por_mediador:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        for med, regs in dados_por_mediador.items():
                            pdf_data = gerar_pdf_bytes(med, regs)
                            zip_file.writestr(f"{med.replace(' ', '_')}.pdf", pdf_data)
                    
                    st.success(f"{len(dados_por_mediador)} PDFs gerados!")
                    st.download_button(label="📥 BAIXAR ZIP", data=zip_buffer.getvalue(), file_name="pautas_cejusc.zip", mime="application/zip")
