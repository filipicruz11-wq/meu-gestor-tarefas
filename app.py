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


# ============================================================
# 1. CONFIGURACAO DA PAGINA
# ============================================================
st.set_page_config(
    page_title="Minha Agenda CEJUSC",
    layout="wide",
    page_icon="📲",
)

# Evita a traducao automatica da pagina pelo Google.
st.markdown(
    """
    <meta name="google" content="notranslate">

    <style>
    html,
    body,
    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"] {
        translate: no !important;
    }

    .notranslate {
        translate: no !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 2. CONEXAO COM O BANCO
# ============================================================
DB_URL = os.environ.get("DATABASE_URL")

if not DB_URL:
    st.error(
        "A variável de ambiente DATABASE_URL não foi configurada no Render."
    )
    st.stop()

# Corrige URLs antigas fornecidas como postgres://.
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace(
        "postgres://",
        "postgresql+psycopg://",
        1,
    )

# Define explicitamente o Psycopg 3 como driver.
elif DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

try:
    engine = create_engine(
        DB_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
        connect_args={
            "connect_timeout": 30,
        },
    )
except Exception as erro:
    st.error(
        f"Não foi possível configurar a conexão com o banco: {erro}"
    )
    st.stop()


def inicializar_db():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS tarefas (
                    id SERIAL PRIMARY KEY,
                    tipo TEXT,
                    prazo TEXT,
                    assunto TEXT,
                    descricao TEXT
                )
                """
            )
        )


try:
    inicializar_db()
except Exception as erro:
    st.error(f"Não foi possível conectar ao banco de dados: {erro}")
    st.stop()


# ============================================================
# 3. ESTADOS DO SISTEMA
# ============================================================
if "logado" not in st.session_state:
    st.session_state.logado = False

if "editando_id" not in st.session_state:
    st.session_state.editando_id = None

if "campo_key" not in st.session_state:
    st.session_state.campo_key = "init"

if "val_tipo" not in st.session_state:
    st.session_state.val_tipo = ""

if "val_assunto" not in st.session_state:
    st.session_state.val_assunto = ""

if "val_desc" not in st.session_state:
    st.session_state.val_desc = ""

if "val_prazo" not in st.session_state:
    st.session_state.val_prazo = datetime.now().date()

if "cal_mes" not in st.session_state:
    st.session_state.cal_mes = datetime.now().month

if "cal_ano" not in st.session_state:
    st.session_state.cal_ano = datetime.now().year

if "form_reset_key" not in st.session_state:
    st.session_state.form_reset_key = 0


def acao_limpar_whatsapp():
    st.session_state.form_reset_key += 1


def limpar_tudo():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.val_prazo = datetime.now().date()
    st.session_state.campo_key = f"k_{time.time_ns()}"


# ============================================================
# 4. REQUISICOES HTTP COM NOVAS TENTATIVAS
# ============================================================
def fazer_requisicao_com_retry(
    url,
    *,
    json=None,
    data=None,
    files=None,
    timeout=(30, 120),
    tentativas=3,
):
    ultimo_erro = None

    for tentativa in range(1, tentativas + 1):
        try:
            resposta = requests.post(
                url,
                json=json,
                data=data,
                files=files,
                timeout=timeout,
            )

            return resposta, None

        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
        ) as erro:
            ultimo_erro = erro

            if tentativa < tentativas:
                espera = 5 * tentativa
                time.sleep(espera)

        except requests.exceptions.RequestException as erro:
            return None, str(erro)

    return (
        None,
        f"Falha após {tentativas} tentativas: {ultimo_erro}",
    )


# ============================================================
# 5. CAIXAS DE DIALOGO
# ============================================================
@st.dialog("Detalhes da Atividade", width="large")
def exibir_detalhes(assunto, descricao):
    assunto_seguro = html.escape(str(assunto or ""))

    st.markdown(f"### {assunto_seguro}")

    if descricao:
        descricao_segura = html.escape(str(descricao))

        st.markdown(
            f"""
            <div
                class="caixa-texto-fix"
                style="white-space: pre-wrap; overflow-wrap: anywhere;"
            >{descricao_segura}</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.write("Sem descrição disponível.")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button(
        "Fechar",
        use_container_width=True,
        key="fechar_detalhes",
    ):
        st.rerun()


@st.dialog("Confirmar Exclusão")
def confirmar_exclusao(id_item, assunto):
    assunto_exibicao = str(assunto or "")

    st.warning(
        f"Deseja realmente excluir o lançamento: "
        f"**{assunto_exibicao}**?"
    )

    st.markdown("Esta ação não pode ser desfeita.")

    col1, col2 = st.columns(2)

    if col1.button(
        "✅ Sim, excluir",
        use_container_width=True,
        type="primary",
        key=f"confirmar_exclusao_{id_item}",
    ):
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        DELETE FROM tarefas
                        WHERE id = :i
                        """
                    ),
                    {"i": int(id_item)},
                )

            st.success("Excluído!")
            time.sleep(0.5)
            st.rerun()

        except Exception as erro:
            st.error(
                f"Não foi possível excluir o lançamento: {erro}"
            )

    if col2.button(
        "❌ Não, cancelar",
        use_container_width=True,
        key=f"cancelar_exclusao_{id_item}",
    ):
        st.rerun()


# ============================================================
# 6. ESTILIZACAO
# ============================================================
st.markdown(
    """
    <style>
    .caixa-texto-fix {
        margin-top: 10px !important;
        font-family: sans-serif !important;
        font-size: 14px !important;
        line-height: 1.6 !important;
        color: #1E1E1E !important;
    }

    .cal-table {
        width: 100%;
        border-collapse: collapse;
        font-family: sans-serif;
        table-layout: fixed;
        background-color: #f8f9fa;
        border: 2px solid #adb5bd;
    }

    .cal-header {
        background-color: #e9ecef;
        font-weight: bold;
        text-align: center;
        padding: 8px;
        border: 1px solid #adb5bd;
        font-size: 14px;
    }

    .cal-day {
        height: 85px;
        text-align: right;
        vertical-align: top;
        padding: 5px;
        border: 1px solid #adb5bd;
        font-size: 14px;
    }

    .dia-util {
        background-color: #ffffff;
    }

    .dia-fds {
        background-color: #fff5f5;
        color: #e03131;
    }

    .dia-feriado {
        background-color: #fff9db;
        color: #f08c00;
        font-weight: bold;
    }

    .dia-vazio {
        background-color: #f1f3f5;
        border: 1px solid #dee2e6;
    }

    hr {
        margin: 4px 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 7. LOGIN
# ============================================================
USUARIO_APP = os.environ.get("USUARIO_APP", "admin")
SENHA_APP = os.environ.get("SENHA_APP")

if not SENHA_APP:
    st.error(
        "A variável de ambiente SENHA_APP não foi configurada no Render."
    )
    st.stop()


if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")

    with st.form("login_form"):
        usuario_digitado = st.text_input("Usuário")

        senha_digitada = st.text_input(
            "Senha",
            type="password",
        )

        entrar = st.form_submit_button(
            "ENTRAR NO SISTEMA",
            use_container_width=True,
        )

        if entrar:
            usuario_correto = usuario_digitado == USUARIO_APP
            senha_correta = senha_digitada == SENHA_APP

            if usuario_correto and senha_correta:
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Dados incorretos.")

else:
    # ========================================================
    # 8. BARRA LATERAL DE CADASTRO E EDICAO
    # ========================================================
    with st.sidebar:
        titulo_sidebar = (
            "Editar Item"
            if st.session_state.editando_id is not None
            else "Novo Cadastro"
        )

        st.header(f"📝 {titulo_sidebar}")

        lista_tipos = [
            "",
            "TAREFA",
            "LEMBRETE",
            "COMPROMISSO",
            "INFORMAÇÃO",
            "CONTATO",
            "AUDIÊNCIA",
            "MODELO",
        ]

        try:
            idx_tipo = lista_tipos.index(
                st.session_state.val_tipo
            )
        except ValueError:
            idx_tipo = 0

        tipo_sel = st.selectbox(
            "Tipo",
            lista_tipos,
            index=idx_tipo,
            key=f"sel_{st.session_state.campo_key}",
        )

        tipos_com_vencimento = [
            "",
            "TAREFA",
            "LEMBRETE",
            "COMPROMISSO",
        ]

        if tipo_sel in tipos_com_vencimento:
            dt_venc = st.date_input(
                "Vencimento",
                value=st.session_state.val_prazo,
                format="DD/MM/YYYY",
                key=f"dat_{st.session_state.campo_key}",
                help="Selecione a data",
            )
        else:
            dt_venc = datetime.now().date()

        ass_in = st.text_input(
            "Assunto",
            value=st.session_state.val_assunto,
            key=f"ass_{st.session_state.campo_key}",
        )

        des_in = st.text_area(
            "Descrição",
            value=st.session_state.val_desc,
            height=250,
            key=f"des_{st.session_state.campo_key}",
        )

        if st.button(
            "✅ Salvar",
            use_container_width=True,
        ):
            assunto_limpo = ass_in.strip()

            if not tipo_sel or not assunto_limpo:
                st.error("Preencha Tipo e Assunto!")

            else:
                parametros = {
                    "t": tipo_sel,
                    "p": str(dt_venc),
                    "a": assunto_limpo,
                    "de": des_in,
                }

                try:
                    with engine.begin() as conn:
                        if (
                            st.session_state.editando_id
                            is not None
                        ):
                            parametros["i"] = int(
                                st.session_state.editando_id
                            )

                            conn.execute(
                                text(
                                    """
                                    UPDATE tarefas
                                    SET
                                        tipo = :t,
                                        prazo = :p,
                                        assunto = :a,
                                        descricao = :de
                                    WHERE id = :i
                                    """
                                ),
                                parametros,
                            )

                        else:
                            conn.execute(
                                text(
                                    """
                                    INSERT INTO tarefas (
                                        tipo,
                                        prazo,
                                        assunto,
                                        descricao
                                    )
                                    VALUES (
                                        :t,
                                        :p,
                                        :a,
                                        :de
                                    )
                                    """
                                ),
                                parametros,
                            )

                    st.success("Salvo!")
                    limpar_tudo()
                    st.rerun()

                except Exception as erro:
                    st.error(
                        f"Não foi possível salvar: {erro}"
                    )

        if st.button(
            "🧹 Limpar",
            use_container_width=True,
        ):
            limpar_tudo()
            st.rerun()

        if st.button(
            "🚪 Sair",
            use_container_width=True,
        ):
            st.session_state.logado = False
            limpar_tudo()
            st.rerun()

    # ========================================================
    # 9. ABAS
    # ========================================================
    (
        t_dash,
        t_tar,
        t_com,
        t_lem,
        t_info,
        t_cont,
        t_aud,
        t_mod,
        t_cal,
        t_wpp,
    ) = st.tabs(
        [
            "🏠 INÍCIO",
            "📌 TAREFAS",
            "📅 COMPROMISSOS",
            "📝 LEMBRETES",
            "ℹ️ INFORMAÇÕES",
            "📞 CONTATOS",
            "⚖️ AUDIÊNCIAS",
            "📄 MODELOS",
            "📅 CALENDÁRIO",
            "📲 WHATSAPP",
        ]
    )

    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                text(
                    """
                    SELECT
                        id,
                        tipo,
                        prazo,
                        assunto,
                        descricao
                    FROM tarefas
                    """
                ),
                conn,
            )

    except Exception as erro:
        st.error(
            f"Não foi possível carregar os registros: {erro}"
        )

        df = pd.DataFrame(
            columns=[
                "id",
                "tipo",
                "prazo",
                "assunto",
                "descricao",
            ]
        )

    def obter_estilo(p_str):
        data_convertida = pd.to_datetime(
            p_str,
            errors="coerce",
        )

        if pd.isna(data_convertida):
            return "blue", "🔵 SEM DATA"

        data_vencimento = data_convertida.date()
        hoje = datetime.now().date()
        diferenca = (data_vencimento - hoje).days

        if diferenca <= 0:
            return "red", "🔴 VENCIDO"

        if 1 <= diferenca <= 2:
            return "gold", "🟡 PRÓXIMO"

        return "blue", "🔵 FUTURO"

    # ========================================================
    # 10. PAINEL INICIAL
    # ========================================================
    with t_dash:
        st.subheader("Visão Geral")

        c_t, c_c, c_l = st.columns(3)
        colunas_grid = [c_t, c_c, c_l]

        for indice, nome in enumerate(
            [
                "TAREFA",
                "COMPROMISSO",
                "LEMBRETE",
            ]
        ):
            dff = df[df["tipo"] == nome]

            contagens = {
                "red": 0,
                "gold": 0,
                "blue": 0,
            }

            for prazo in dff["prazo"].dropna():
                cor, _ = obter_estilo(prazo)
                contagens[cor] += 1

            figura = go.Figure(
                go.Bar(
                    x=[
                        contagens["blue"],
                        contagens["gold"],
                        contagens["red"],
                    ],
                    y=[
                        "3+ dias",
                        "1 a 2 dias",
                        "Vencido",
                    ],
                    orientation="h",
                    marker_color=[
                        "blue",
                        "gold",
                        "red",
                    ],
                    text=[
                        contagens["blue"],
                        contagens["gold"],
                        contagens["red"],
                    ],
                    textposition="outside",
                )
            )

            figura.update_layout(
                title=f"{nome}S",
                height=230,
                margin=dict(
                    l=10,
                    r=50,
                    t=40,
                    b=10,
                ),
                xaxis=dict(
                    visible=False,
                ),
            )

            colunas_grid[indice].plotly_chart(
                figura,
                use_container_width=True,
            )

    # ========================================================
    # 11. FUNCOES DE LISTAGEM
    # ========================================================
    def listar(tipo, tab):
        with tab:
            dff = df[df["tipo"] == tipo].copy()

            dff["prazo_data"] = pd.to_datetime(
                dff["prazo"],
                errors="coerce",
            )

            dff = dff.sort_values(
                by="prazo_data",
                na_position="last",
            )

            if dff.empty:
                st.info("Nenhum registro cadastrado.")
                return

            for _, registro in dff.iterrows():
                dt = registro["prazo_data"]

                if pd.isna(dt):
                    data_exibicao = "Sem data"
                    data_edicao = datetime.now().date()
                else:
                    data_exibicao = dt.strftime(
                        "%d/%m/%Y"
                    )
                    data_edicao = dt.date()

                _, texto_status = obter_estilo(
                    registro["prazo"]
                )

                c1, c2, c3, c4, c5, c6 = st.columns(
                    [
                        0.15,
                        0.12,
                        0.02,
                        0.51,
                        0.10,
                        0.10,
                    ]
                )

                c1.write(texto_status)
                c2.write(data_exibicao)

                if c4.button(
                    f"**{registro['assunto']}**",
                    key=f"b_{registro['id']}",
                    use_container_width=True,
                ):
                    exibir_detalhes(
                        registro["assunto"],
                        registro["descricao"],
                    )

                if c5.button(
                    "📝",
                    key=f"e_{registro['id']}",
                    use_container_width=True,
                ):
                    st.session_state.editando_id = int(
                        registro["id"]
                    )

                    st.session_state.val_tipo = registro[
                        "tipo"
                    ]

                    st.session_state.val_assunto = str(
                        registro["assunto"] or ""
                    )

                    st.session_state.val_desc = str(
                        registro["descricao"] or ""
                    )

                    st.session_state.val_prazo = data_edicao

                    st.session_state.campo_key = (
                        f"edit_{registro['id']}"
                    )

                    st.rerun()

                if c6.button(
                    "🗑️",
                    key=f"d_{registro['id']}",
                    use_container_width=True,
                ):
                    confirmar_exclusao(
                        int(registro["id"]),
                        registro["assunto"],
                    )

                st.markdown("---")

    def listar_simples(tipo, tab, icone):
        with tab:
            dff = df[df["tipo"] == tipo].copy()

            dff = dff.sort_values(
                by="assunto",
                na_position="last",
            )

            if dff.empty:
                st.info("Nenhum registro cadastrado.")
                return

            for _, registro in dff.iterrows():
                c1, c2, c3 = st.columns(
                    [
                        0.80,
                        0.10,
                        0.10,
                    ]
                )

                if c1.button(
                    f"{icone} **{registro['assunto']}**",
                    key=f"s_{registro['id']}",
                    use_container_width=True,
                ):
                    exibir_detalhes(
                        registro["assunto"],
                        registro["descricao"],
                    )

                if c2.button(
                    "📝",
                    key=f"es_{registro['id']}",
                    use_container_width=True,
                ):
                    st.session_state.editando_id = int(
                        registro["id"]
                    )

                    st.session_state.val_tipo = registro[
                        "tipo"
                    ]

                    st.session_state.val_assunto = str(
                        registro["assunto"] or ""
                    )

                    st.session_state.val_desc = str(
                        registro["descricao"] or ""
                    )

                    st.session_state.val_prazo = (
                        datetime.now().date()
                    )

                    st.session_state.campo_key = (
                        f"edit_s_{registro['id']}"
                    )

                    st.rerun()

                if c3.button(
                    "🗑️",
                    key=f"ds_{registro['id']}",
                    use_container_width=True,
                ):
                    confirmar_exclusao(
                        int(registro["id"]),
                        registro["assunto"],
                    )

                st.markdown("---")

    # ========================================================
    # 12. CALENDARIO
    # ========================================================
    with t_cal:
        c_nav1, c_nav2, c_nav3 = st.columns(
            [
                1,
                2,
                1,
            ]
        )

        with c_nav2:
            n1, n2, n3 = st.columns(
                [
                    1,
                    2,
                    1,
                ]
            )

            if n1.button(
                "⬅️ Ant.",
                use_container_width=True,
            ):
                st.session_state.cal_mes -= 1

                if st.session_state.cal_mes < 1:
                    st.session_state.cal_mes = 12
                    st.session_state.cal_ano -= 1

                st.rerun()

            meses = [
                "",
                "Janeiro",
                "Fevereiro",
                "Março",
                "Abril",
                "Maio",
                "Junho",
                "Julho",
                "Agosto",
                "Setembro",
                "Outubro",
                "Novembro",
                "Dezembro",
            ]

            n2.markdown(
                (
                    "<h4 style='text-align:center'>"
                    f"{meses[st.session_state.cal_mes]} "
                    f"{st.session_state.cal_ano}"
                    "</h4>"
                ),
                unsafe_allow_html=True,
            )

            if n3.button(
                "Próx. ➡️",
                use_container_width=True,
            ):
                st.session_state.cal_mes += 1

                if st.session_state.cal_mes > 12:
                    st.session_state.cal_mes = 1
                    st.session_state.cal_ano += 1

                st.rerun()

        calendar.setfirstweekday(calendar.SUNDAY)

        calendario_mes = calendar.monthcalendar(
            st.session_state.cal_ano,
            st.session_state.cal_mes,
        )

        feriados_br = holidays.BR(
            years=[
                st.session_state.cal_ano,
            ]
        )

        html_calendario = (
            '<table class="cal-table"><tr>'
        )

        for nome_semana in [
            "Dom",
            "Seg",
            "Ter",
            "Qua",
            "Qui",
            "Sex",
            "Sáb",
        ]:
            html_calendario += (
                f'<th class="cal-header">'
                f"{nome_semana}"
                f"</th>"
            )

        html_calendario += "</tr>"

        for semana in calendario_mes:
            html_calendario += "<tr>"

            for indice_dia, dia in enumerate(semana):
                if dia == 0:
                    html_calendario += (
                        '<td class="cal-day dia-vazio">'
                        "</td>"
                    )
                    continue

                data_atual = datetime(
                    st.session_state.cal_ano,
                    st.session_state.cal_mes,
                    dia,
                ).date()

                classe = (
                    "dia-fds"
                    if indice_dia in (0, 6)
                    else "dia-util"
                )

                feriado = feriados_br.get(data_atual)

                if feriado:
                    classe = "dia-feriado"

                nome_feriado = (
                    html.escape(str(feriado))
                    if feriado
                    else ""
                )

                texto_feriado = (
                    '<div style="'
                    "font-size:9px;"
                    "color:#f08c00;"
                    "line-height:1"
                    '">'
                    f"{nome_feriado}"
                    "</div>"
                    if feriado
                    else ""
                )

                html_calendario += (
                    f'<td class="cal-day {classe}">'
                    f"<b>{dia}</b>"
                    f"{texto_feriado}"
                    "</td>"
                )

            html_calendario += "</tr>"

        html_calendario += "</table>"

        st.markdown(
            html_calendario,
            unsafe_allow_html=True,
        )

    # ========================================================
    # 13. WHATSAPP
    # ========================================================
    with t_wpp:
        st.subheader("📲 ENVIO POR WHATSAPP")
        st.markdown("---")

        ID_INSTANCE = os.environ.get("ID_INSTANCE")
        API_TOKEN = os.environ.get("API_TOKEN")
        DESTINO = os.environ.get("MEU_NUMERO")

        st.button(
            "🗑️ LIMPAR TUDO (RESETAR TELA)",
            on_click=acao_limpar_whatsapp,
            use_container_width=True,
            key="btn_wpp_clear",
        )

        with st.form(
            key=(
                f"form_envio_"
                f"{st.session_state.form_reset_key}"
            ),
            clear_on_submit=True,
        ):
            m1 = st.text_area(
                "Mensagem 1:",
                height=100,
            )

            m2 = st.text_area(
                "Mensagem 2:",
                height=100,
            )

            m3 = st.text_area(
                "Mensagem 3:",
                height=100,
            )

            m4 = st.text_area(
                "Mensagem 4:",
                height=100,
            )

            arquivos = st.file_uploader(
                (
                    "Arraste e solte os arquivos aqui "
                    "ou clique para selecionar"
                ),
                accept_multiple_files=True,
            )

            submit = st.form_submit_button(
                "🚀 ENVIAR AGORA",
                use_container_width=True,
            )

        if submit:
            mensagens_para_enviar = [
                mensagem.strip()
                for mensagem in [
                    m1,
                    m2,
                    m3,
                    m4,
                ]
                if mensagem and mensagem.strip()
            ]

            arquivos_para_enviar = arquivos or []

            if (
                not arquivos_para_enviar
                and not mensagens_para_enviar
            ):
                st.warning(
                    "⚠️ Selecione ao menos um arquivo "
                    "ou digite uma mensagem."
                )

            elif not all(
                [
                    ID_INSTANCE,
                    API_TOKEN,
                    DESTINO,
                ]
            ):
                st.error(
                    "❌ Verifique as variáveis ID_INSTANCE, "
                    "API_TOKEN e MEU_NUMERO no Render."
                )

            else:
                destino_limpo = "".join(
                    caractere
                    for caractere in str(DESTINO)
                    if caractere.isdigit()
                )

                if not destino_limpo:
                    st.error(
                        "❌ O número configurado em "
                        "MEU_NUMERO é inválido."
                    )
                    st.stop()

                chat_id = f"{destino_limpo}@c.us"

                url_texto = (
                    "https://api.green-api.com/"
                    f"waInstance{ID_INSTANCE}/"
                    f"sendMessage/{API_TOKEN}"
                )

                url_arquivo = (
                    "https://media.green-api.com/"
                    f"waInstance{ID_INSTANCE}/"
                    f"sendFileByUpload/{API_TOKEN}"
                )

                erros_envio = []
                enviados = 0

                total_itens = (
                    len(mensagens_para_enviar)
                    + len(arquivos_para_enviar)
                )

                barra_progresso = st.progress(0)
                texto_progresso = st.empty()
                item_atual = 0

                with st.spinner(
                    "Enviando sequência..."
                ):
                    for indice, mensagem in enumerate(
                        mensagens_para_enviar,
                        start=1,
                    ):
                        item_atual += 1

                        texto_progresso.write(
                            f"Enviando mensagem {indice} de "
                            f"{len(mensagens_para_enviar)}..."
                        )

                        resposta, erro_rede = (
                            fazer_requisicao_com_retry(
                                url_texto,
                                json={
                                    "chatId": chat_id,
                                    "message": mensagem,
                                },
                                timeout=(60, 120),
                                tentativas=3,
                            )
                        )

                        if erro_rede:
                            erros_envio.append(
                                f"Mensagem {indice}: "
                                f"{erro_rede}"
                            )

                        elif resposta is None:
                            erros_envio.append(
                                f"Mensagem {indice}: "
                                "nenhuma resposta recebida."
                            )

                        elif not resposta.ok:
                            detalhe = resposta.text[:500]

                            erros_envio.append(
                                f"Mensagem {indice}: HTTP "
                                f"{resposta.status_code}. "
                                f"{detalhe}"
                            )

                        else:
                            enviados += 1

                        barra_progresso.progress(
                            item_atual / total_itens
                        )

                        time.sleep(1)

                    for arquivo in arquivos_para_enviar:
                        item_atual += 1

                        texto_progresso.write(
                            f"Enviando arquivo: "
                            f"{arquivo.name}"
                        )

                        tipo_mime = (
                            arquivo.type
                            or "application/octet-stream"
                        )

                        conteudo_arquivo = (
                            arquivo.getvalue()
                        )

                        resposta, erro_rede = (
                            fazer_requisicao_com_retry(
                                url_arquivo,
                                data={
                                    "chatId": chat_id,
                                    "caption": "",
                                    "fileName": arquivo.name,
                                },
                                files={
                                    "file": (
                                        arquivo.name,
                                        conteudo_arquivo,
                                        tipo_mime,
                                    )
                                },
                                timeout=(60, 300),
                                tentativas=3,
                            )
                        )

                        if erro_rede:
                            erros_envio.append(
                                f"Arquivo {arquivo.name}: "
                                f"{erro_rede}"
                            )

                        elif resposta is None:
                            erros_envio.append(
                                f"Arquivo {arquivo.name}: "
                                "nenhuma resposta recebida."
                            )

                        elif not resposta.ok:
                            detalhe = resposta.text[:500]

                            erros_envio.append(
                                f"Arquivo {arquivo.name}: "
                                f"HTTP "
                                f"{resposta.status_code}. "
                                f"{detalhe}"
                            )

                        else:
                            enviados += 1

                        barra_progresso.progress(
                            item_atual / total_itens
                        )

                        time.sleep(1)

                texto_progresso.empty()

                if erros_envio:
                    st.warning(
                        f"⚠️ Foram enviados {enviados} "
                        f"de {total_itens} itens."
                    )

                    with st.expander(
                        (
                            "Ver detalhes dos itens "
                            "que falharam"
                        ),
                        expanded=True,
                    ):
                        for erro in erros_envio:
                            st.write(f"• {erro}")

                else:
                    st.success(
                        f"✅ Todos os {total_itens} "
                        "itens foram enviados."
                    )

                    acao_limpar_whatsapp()
                    time.sleep(1)
                    st.rerun()

        st.markdown("---")
        st.caption(
            "Uso restrito: CEJUSC - Araçatuba/SP"
        )

    # ========================================================
    # 14. EXECUCAO DAS LISTAGENS
    # ========================================================
    listar(
        "TAREFA",
        t_tar,
    )

    listar(
        "COMPROMISSO",
        t_com,
    )

    listar(
        "LEMBRETE",
        t_lem,
    )

    listar_simples(
        "INFORMAÇÃO",
        t_info,
        "📌",
    )

    listar_simples(
        "CONTATO",
        t_cont,
        "📞",
    )

    listar_simples(
        "AUDIÊNCIA",
        t_aud,
        "⚖️",
    )

    listar_simples(
        "MODELO",
        t_mod,
        "📄",
    )
