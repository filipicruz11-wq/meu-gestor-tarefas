import calendar
import html
import os
import time
from datetime import datetime

import holidays
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide", page_icon="📲")

st.markdown(
    """
    <meta name="google" content="notranslate">
    <style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] { translate: no !important; }
    .caixa-texto-fix { margin-top:10px!important; font-family:sans-serif!important; font-size:14px!important; line-height:1.6!important; color:#1E1E1E!important; }
    .cal-table { width:100%; border-collapse:collapse; font-family:sans-serif; table-layout:fixed; background:#f8f9fa; border:2px solid #adb5bd; }
    .cal-header { background:#e9ecef; font-weight:bold; text-align:center; padding:8px; border:1px solid #adb5bd; font-size:14px; }
    .cal-day { height:85px; text-align:right; vertical-align:top; padding:5px; border:1px solid #adb5bd; font-size:14px; }
    .dia-util { background:#fff; }
    .dia-fds { background:#fff5f5; color:#e03131; }
    .dia-feriado { background:#fff9db; color:#f08c00; font-weight:bold; }
    .dia-vazio { background:#f1f3f5; border:1px solid #dee2e6; }
    hr { margin:4px 0!important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Banco de dados
DB_URL = os.environ.get("DATABASE_URL", "").strip()
if not DB_URL:
    st.error("A variável DATABASE_URL não foi configurada no Render.")
    st.stop()
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)

try:
    engine = create_engine(
        DB_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 30},
    )
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id SERIAL PRIMARY KEY,
                tipo TEXT,
                prazo TEXT,
                assunto TEXT,
                descricao TEXT
            )
        """))
except Exception as erro:
    st.error(f"Não foi possível conectar ao banco: {erro}")
    st.stop()

# Estado
padroes = {
    "logado": False,
    "editando_id": None,
    "campo_key": "init",
    "val_tipo": "",
    "val_assunto": "",
    "val_desc": "",
    "val_prazo": datetime.now().date(),
    "cal_mes": datetime.now().month,
    "cal_ano": datetime.now().year,
    "form_reset_key": 0,
}
for chave, valor in padroes.items():
    if chave not in st.session_state:
        st.session_state[chave] = valor


def acao_limpar_whatsapp():
    st.session_state.form_reset_key += 1


def limpar_tudo():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.val_prazo = datetime.now().date()
    st.session_state.campo_key = f"k_{time.time_ns()}"


def requisicao(metodo, url, *, json=None, data=None, files=None, timeout=(10, 30), tentativas=2):
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = requests.request(
                method=metodo,
                url=url,
                json=json,
                data=data,
                files=files,
                timeout=timeout,
                headers={"User-Agent": "Agenda-CEJUSC/1.0"},
            )
            return resposta, None
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as erro:
            ultimo_erro = erro
            if tentativa < tentativas:
                time.sleep(3)
        except requests.exceptions.RequestException as erro:
            return None, str(erro)
    return None, f"Falha após {tentativas} tentativas: {ultimo_erro}"


def testar_instancia(api_url, id_instance, api_token):
    url = f"{api_url}/waInstance{id_instance}/getStateInstance/{api_token}"
    resposta, erro = requisicao("GET", url, timeout=(10, 20), tentativas=1)
    if erro:
        return False, erro
    if resposta is None:
        return False, "Nenhuma resposta recebida."
    if not resposta.ok:
        return False, f"HTTP {resposta.status_code}: {resposta.text[:500]}"
    try:
        estado = resposta.json().get("stateInstance")
    except ValueError:
        return False, f"Resposta inválida: {resposta.text[:500]}"
    return bool(estado), estado or "Estado não informado."


@st.dialog("Detalhes da Atividade", width="large")
def exibir_detalhes(assunto, descricao):
    st.markdown(f"### {html.escape(str(assunto or ''))}")
    if descricao:
        st.markdown(
            f'<div class="caixa-texto-fix" style="white-space:pre-wrap;overflow-wrap:anywhere">{html.escape(str(descricao))}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.write("Sem descrição disponível.")
    if st.button("Fechar", use_container_width=True, key="fechar_detalhes"):
        st.rerun()


@st.dialog("Confirmar Exclusão")
def confirmar_exclusao(id_item, assunto):
    st.warning(f"Deseja realmente excluir: **{str(assunto or '')}**?")
    st.write("Esta ação não pode ser desfeita.")
    c1, c2 = st.columns(2)
    if c1.button("✅ Sim, excluir", use_container_width=True, type="primary", key=f"confirmar_{id_item}"):
        try:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": int(id_item)})
            st.rerun()
        except Exception as erro:
            st.error(f"Não foi possível excluir: {erro}")
    if c2.button("❌ Cancelar", use_container_width=True, key=f"cancelar_{id_item}"):
        st.rerun()

# Login
USUARIO_APP = os.environ.get("USUARIO_APP", "admin").strip()
SENHA_APP = os.environ.get("SENHA_APP", "")
if not SENHA_APP:
    st.error("A variável SENHA_APP não foi configurada no Render.")
    st.stop()

if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.form("login_form"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True)
    if entrar:
        if usuario == USUARIO_APP and senha == SENHA_APP:
            st.session_state.logado = True
            st.rerun()
        st.error("Dados incorretos.")
    st.stop()

# Barra lateral
with st.sidebar:
    st.header("📝 Editar Item" if st.session_state.editando_id is not None else "📝 Novo Cadastro")
    tipos = ["", "TAREFA", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]
    try:
        indice_tipo = tipos.index(st.session_state.val_tipo)
    except ValueError:
        indice_tipo = 0
    tipo_sel = st.selectbox("Tipo", tipos, index=indice_tipo, key=f"sel_{st.session_state.campo_key}")
    if tipo_sel in ["", "TAREFA", "LEMBRETE", "COMPROMISSO"]:
        dt_venc = st.date_input("Vencimento", value=st.session_state.val_prazo, format="DD/MM/YYYY", key=f"dat_{st.session_state.campo_key}")
    else:
        dt_venc = datetime.now().date()
    ass_in = st.text_input("Assunto", value=st.session_state.val_assunto, key=f"ass_{st.session_state.campo_key}")
    des_in = st.text_area("Descrição", value=st.session_state.val_desc, height=250, key=f"des_{st.session_state.campo_key}")

    if st.button("✅ Salvar", use_container_width=True):
        if not tipo_sel or not ass_in.strip():
            st.error("Preencha Tipo e Assunto!")
        else:
            parametros = {"t": tipo_sel, "p": str(dt_venc), "a": ass_in.strip(), "de": des_in}
            try:
                with engine.begin() as conn:
                    if st.session_state.editando_id is not None:
                        parametros["i"] = int(st.session_state.editando_id)
                        conn.execute(text("UPDATE tarefas SET tipo=:t,prazo=:p,assunto=:a,descricao=:de WHERE id=:i"), parametros)
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo,prazo,assunto,descricao) VALUES (:t,:p,:a,:de)"), parametros)
                limpar_tudo()
                st.rerun()
            except Exception as erro:
                st.error(f"Não foi possível salvar: {erro}")

    if st.button("🧹 Limpar", use_container_width=True):
        limpar_tudo()
        st.rerun()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        limpar_tudo()
        st.rerun()

(t_dash, t_tar, t_com, t_lem, t_info, t_cont, t_aud, t_mod, t_cal, t_wpp) = st.tabs([
    "🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📝 LEMBRETES", "ℹ️ INFORMAÇÕES",
    "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO", "📲 WHATSAPP",
])

try:
    with engine.connect() as conn:
        df = pd.read_sql(text("SELECT id,tipo,prazo,assunto,descricao FROM tarefas"), conn)
except Exception as erro:
    st.error(f"Não foi possível carregar os registros: {erro}")
    df = pd.DataFrame(columns=["id", "tipo", "prazo", "assunto", "descricao"])


def obter_estilo(prazo):
    data = pd.to_datetime(prazo, errors="coerce")
    if pd.isna(data):
        return "blue", "🔵 SEM DATA"
    diferenca = (data.date() - datetime.now().date()).days
    if diferenca <= 0:
        return "red", "🔴 VENCIDO"
    if 1 <= diferenca <= 2:
        return "gold", "🟡 PRÓXIMO"
    return "blue", "🔵 FUTURO"

with t_dash:
    st.subheader("Visão Geral")
    colunas = st.columns(3)
    for indice, nome in enumerate(["TAREFA", "COMPROMISSO", "LEMBRETE"]):
        contagens = {"red": 0, "gold": 0, "blue": 0}
        for prazo in df[df["tipo"] == nome]["prazo"].dropna():
            cor, _ = obter_estilo(prazo)
            contagens[cor] += 1
        figura = go.Figure(go.Bar(
            x=[contagens["blue"], contagens["gold"], contagens["red"]],
            y=["3+ dias", "1 a 2 dias", "Vencido"],
            orientation="h", marker_color=["blue", "gold", "red"],
            text=[contagens["blue"], contagens["gold"], contagens["red"]], textposition="outside",
        ))
        figura.update_layout(title=f"{nome}S", height=230, margin=dict(l=10, r=50, t=40, b=10), xaxis=dict(visible=False))
        colunas[indice].plotly_chart(figura, use_container_width=True)


def carregar_edicao(registro, data_edicao):
    st.session_state.editando_id = int(registro["id"])
    st.session_state.val_tipo = registro["tipo"]
    st.session_state.val_assunto = str(registro["assunto"] or "")
    st.session_state.val_desc = str(registro["descricao"] or "")
    st.session_state.val_prazo = data_edicao
    st.session_state.campo_key = f"edit_{registro['id']}"
    st.rerun()


def listar(tipo, aba):
    with aba:
        dados = df[df["tipo"] == tipo].copy()
        dados["prazo_data"] = pd.to_datetime(dados["prazo"], errors="coerce")
        dados = dados.sort_values("prazo_data", na_position="last")
        if dados.empty:
            st.info("Nenhum registro cadastrado.")
        for _, registro in dados.iterrows():
            dt = registro["prazo_data"]
            data_exibicao = "Sem data" if pd.isna(dt) else dt.strftime("%d/%m/%Y")
            data_edicao = datetime.now().date() if pd.isna(dt) else dt.date()
            _, status = obter_estilo(registro["prazo"])
            c1, c2, _, c4, c5, c6 = st.columns([.15, .12, .02, .51, .10, .10])
            c1.write(status)
            c2.write(data_exibicao)
            if c4.button(f"**{registro['assunto']}**", key=f"b_{registro['id']}", use_container_width=True):
                exibir_detalhes(registro["assunto"], registro["descricao"])
            if c5.button("📝", key=f"e_{registro['id']}", use_container_width=True):
                carregar_edicao(registro, data_edicao)
            if c6.button("🗑️", key=f"d_{registro['id']}", use_container_width=True):
                confirmar_exclusao(int(registro["id"]), registro["assunto"])
            st.markdown("---")


def listar_simples(tipo, aba, icone):
    with aba:
        dados = df[df["tipo"] == tipo].copy().sort_values("assunto", na_position="last")
        if dados.empty:
            st.info("Nenhum registro cadastrado.")
        for _, registro in dados.iterrows():
            c1, c2, c3 = st.columns([.80, .10, .10])
            if c1.button(f"{icone} **{registro['assunto']}**", key=f"s_{registro['id']}", use_container_width=True):
                exibir_detalhes(registro["assunto"], registro["descricao"])
            if c2.button("📝", key=f"es_{registro['id']}", use_container_width=True):
                carregar_edicao(registro, datetime.now().date())
            if c3.button("🗑️", key=f"ds_{registro['id']}", use_container_width=True):
                confirmar_exclusao(int(registro["id"]), registro["assunto"])
            st.markdown("---")

with t_cal:
    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        ant, titulo, prox = st.columns([1, 2, 1])
        if ant.button("⬅️ Ant.", use_container_width=True):
            st.session_state.cal_mes -= 1
            if st.session_state.cal_mes < 1:
                st.session_state.cal_mes = 12
                st.session_state.cal_ano -= 1
            st.rerun()
        meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        titulo.markdown(f"<h4 style='text-align:center'>{meses[st.session_state.cal_mes]} {st.session_state.cal_ano}</h4>", unsafe_allow_html=True)
        if prox.button("Próx. ➡️", use_container_width=True):
            st.session_state.cal_mes += 1
            if st.session_state.cal_mes > 12:
                st.session_state.cal_mes = 1
                st.session_state.cal_ano += 1
            st.rerun()

    calendar.setfirstweekday(calendar.SUNDAY)
    semanas = calendar.monthcalendar(st.session_state.cal_ano, st.session_state.cal_mes)
    feriados = holidays.BR(years=[st.session_state.cal_ano])
    calendario_html = '<table class="cal-table"><tr>'
    for nome in ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]:
        calendario_html += f'<th class="cal-header">{nome}</th>'
    calendario_html += "</tr>"
    for semana in semanas:
        calendario_html += "<tr>"
        for indice, dia in enumerate(semana):
            if dia == 0:
                calendario_html += '<td class="cal-day dia-vazio"></td>'
                continue
            data = datetime(st.session_state.cal_ano, st.session_state.cal_mes, dia).date()
            feriado = feriados.get(data)
            classe = "dia-feriado" if feriado else ("dia-fds" if indice in (0, 6) else "dia-util")
            texto_feriado = f'<div style="font-size:9px;color:#f08c00;line-height:1">{html.escape(str(feriado))}</div>' if feriado else ""
            calendario_html += f'<td class="cal-day {classe}"><b>{dia}</b>{texto_feriado}</td>'
        calendario_html += "</tr>"
    calendario_html += "</table>"
    st.markdown(calendario_html, unsafe_allow_html=True)

# WhatsApp
with t_wpp:
    st.subheader("📲 ENVIO POR WHATSAPP")
    st.markdown("---")

    # O apiUrl deve ser copiado do console da sua instância GREEN-API.
    # O padrão abaixo usa o host sem hífen, conforme o endpoint que você está testando.
    API_URL = os.environ.get("API_URL", "https://api.greenapi.com").strip().rstrip("/")
    MEDIA_URL = os.environ.get("MEDIA_URL", "https://media.green-api.com").strip().rstrip("/")
    ID_INSTANCE = os.environ.get("ID_INSTANCE", "").strip()
    API_TOKEN = os.environ.get("API_TOKEN", "").strip()
    DESTINO = os.environ.get("MEU_NUMERO", "").strip()

    st.caption(f"Servidor configurado: {API_URL}")

    st.button(
        "🗑️ LIMPAR TUDO (RESETAR TELA)",
        on_click=acao_limpar_whatsapp,
        use_container_width=True,
        key="btn_wpp_clear",
    )

    with st.form(key=f"form_envio_{st.session_state.form_reset_key}", clear_on_submit=True):
        m1 = st.text_area("Mensagem 1:", height=100)
        m2 = st.text_area("Mensagem 2:", height=100)
        m3 = st.text_area("Mensagem 3:", height=100)
        m4 = st.text_area("Mensagem 4:", height=100)
        arquivos = st.file_uploader("Arraste os arquivos aqui ou clique para selecionar", accept_multiple_files=True)
        submit = st.form_submit_button("🚀 ENVIAR AGORA", use_container_width=True)

    if submit:
        mensagens = [m.strip() for m in [m1, m2, m3, m4] if m and m.strip()]
        arquivos = arquivos or []
        if not mensagens and not arquivos:
            st.warning("Selecione ao menos um arquivo ou digite uma mensagem.")
        elif not all([API_URL, ID_INSTANCE, API_TOKEN, DESTINO]):
            st.error("Verifique API_URL, ID_INSTANCE, API_TOKEN e MEU_NUMERO no Render.")
        else:
            numero = "".join(c for c in DESTINO if c.isdigit())
            if not numero:
                st.error("MEU_NUMERO é inválido.")
                st.stop()

            chat_id = f"{numero}@c.us"
            url_texto = f"{API_URL}/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN}"
            url_arquivo = f"{MEDIA_URL}/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN}"

            with st.spinner("Verificando conexão com a GREEN-API..."):
                instancia_ok, estado = testar_instancia(API_URL, ID_INSTANCE, API_TOKEN)

            if not instancia_ok:
                st.error(f"Não foi possível acessar a instância: {estado}")
            elif estado != "authorized":
                st.error(f"A instância não está autorizada. Estado: {estado}")
            else:
                erros = []
                enviados = 0
                total = len(mensagens) + len(arquivos)
                progresso = st.progress(0)
                status = st.empty()
                atual = 0

                for indice, mensagem in enumerate(mensagens, start=1):
                    atual += 1
                    status.write(f"Enviando mensagem {indice} de {len(mensagens)}...")
                    resposta, erro = requisicao(
                        "POST", url_texto,
                        json={"chatId": chat_id, "message": mensagem},
                        timeout=(10, 30), tentativas=2,
                    )
                    if erro:
                        erros.append(f"Mensagem {indice}: {erro}")
                    elif resposta is None or not resposta.ok:
                        codigo = resposta.status_code if resposta is not None else "sem resposta"
                        detalhe = resposta.text[:500] if resposta is not None else ""
                        erros.append(f"Mensagem {indice}: HTTP {codigo}. {detalhe}")
                    else:
                        try:
                            id_mensagem = resposta.json().get("idMessage")
                        except ValueError:
                            id_mensagem = None
                        if id_mensagem:
                            enviados += 1
                        else:
                            erros.append(f"Mensagem {indice}: resposta sem idMessage: {resposta.text[:500]}")
                    progresso.progress(atual / total)
                    time.sleep(1)

                for arquivo in arquivos:
                    atual += 1
                    status.write(f"Enviando arquivo: {arquivo.name}")
                    resposta, erro = requisicao(
                        "POST", url_arquivo,
                        data={"chatId": chat_id, "caption": "", "fileName": arquivo.name},
                        files={"file": (arquivo.name, arquivo.getvalue(), arquivo.type or "application/octet-stream")},
                        timeout=(15, 120), tentativas=2,
                    )
                    if erro:
                        erros.append(f"Arquivo {arquivo.name}: {erro}")
                    elif resposta is None or not resposta.ok:
                        codigo = resposta.status_code if resposta is not None else "sem resposta"
                        detalhe = resposta.text[:500] if resposta is not None else ""
                        erros.append(f"Arquivo {arquivo.name}: HTTP {codigo}. {detalhe}")
                    else:
                        enviados += 1
                    progresso.progress(atual / total)
                    time.sleep(1)

                status.empty()
                if erros:
                    st.error(f"Foram enviados {enviados} de {total} itens.")
                    with st.expander("Ver detalhes", expanded=True):
                        for erro in erros:
                            st.write(f"• {erro}")
                else:
                    st.success(f"Todos os {total} itens foram enviados com sucesso.")
                    acao_limpar_whatsapp()
                    time.sleep(1)
                    st.rerun()

    st.markdown("---")
    st.caption("Uso restrito: CEJUSC - Araçatuba/SP")

listar("TAREFA", t_tar)
listar("COMPROMISSO", t_com)
listar("LEMBRETE", t_lem)
listar_simples("INFORMAÇÃO", t_info, "📌")
listar_simples("CONTATO", t_cont, "📞")
listar_simples("AUDIÊNCIA", t_aud, "⚖️")
listar_simples("MODELO", t_mod, "📄")
