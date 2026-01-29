import os
import json
from datetime import date
import io

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit

# =============================
# CONFIGURAÇÕES
# =============================
st.set_page_config(page_title="Gerador de Acompanhamento", layout="wide")

TIPOS_CONTA = [
    "Banco",
    "Caixa",
    "Maquineta",
    "Cartão Pré-pago",
    "Cartão de Crédito",
]

# =============================
# UTIL
# =============================
def normalize_user(s: str) -> str:
    return (s or "").strip().lower()


def format_nome_acompanhador(username: str) -> str:
    return (username or "").replace("_", " ").strip().title()


def clean_text(s: str) -> str:
    return (s or "").replace("\t", " ").replace("\u00A0", " ").replace("\u200b", "").strip()


def load_setores_por_usuario() -> dict:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "setores_usuarios.json")

    if not os.path.exists(json_path):
        st.error(f"❌ Arquivo não encontrado: {json_path}")
        st.stop()

    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return {normalize_user(k): v for k, v in raw.items()}


def load_users_from_secrets() -> dict:
    if "users" not in st.secrets:
        st.error("❌ 'users' não encontrado no secrets.toml.")
        st.stop()

    raw = st.secrets["users"]
    return {normalize_user(k): v for k, v in raw.items()}


# =============================
# LOGIN
# =============================
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.title("Login")

    usuario_input = normalize_user(st.text_input("Usuário"))
    senha_input = st.text_input("Senha", type="password")

    usuarios = load_users_from_secrets()
    entrou = st.button("Entrar")

    if entrou:
        if usuario_input in usuarios and senha_input == usuarios[usuario_input].get("senha", ""):
            st.session_state["logado"] = True
            st.session_state["usuario"] = usuario_input
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos")

    st.stop()

# =============================
# SETORES POR USUÁRIO
# =============================
setores_por_usuario = load_setores_por_usuario()
usuario_atual = normalize_user(st.session_state.get("usuario", ""))

ACOMPANHADORA = format_nome_acompanhador(usuario_atual)
setores_disponiveis = setores_por_usuario.get(usuario_atual, [])

if not setores_disponiveis:
    st.warning("⚠️ Nenhum setor encontrado para este usuário (verifique o JSON e o username).")

# =============================
# GOOGLE SHEETS
# =============================
@st.cache_resource
def conectar_sheets():
    if "gcp_service_account" not in st.secrets:
        st.error("❌ 'gcp_service_account' não encontrado no secrets.toml.")
        st.stop()

    if "SPREADSHEET_URL" not in st.secrets:
        st.error("❌ 'SPREADSHEET_URL' não encontrado no secrets.toml.")
        st.stop()

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(creds)


def salvar_historico(linhas):
    if not linhas:
        return

    client = conectar_sheets()
    planilha = client.open_by_url(st.secrets["SPREADSHEET_URL"])

    # Nome da aba = nome do acompanhador logado
    nome_aba_user = ACOMPANHADORA  # ex: "Isabele Dandara"

    try:
        # tenta abrir a aba do acompanhador
        aba = planilha.worksheet(nome_aba_user)
    except gspread.exceptions.WorksheetNotFound:
        # se não existir, cria
        aba = planilha.add_worksheet(
            title=nome_aba_user,
            rows=2000,
            cols=30
        )

        # cria cabeçalho (só na primeira vez)
        cabecalho = [
            "Data",
            "Acompanhador(a)",
            "Setor",
            "Sistema Financeiro",
            "Responsável",
            "Período",
            "Tipo de conta",
            "Nome da conta",
            "Extrato bancário",
            "Conciliações pendentes",
            "Saldo atual",
            "Provisões",
            "Documentos",
            "Observações",
        ]
        aba.append_row(cabecalho)

    # salva os dados
    aba.append_rows(linhas)



# =============================
# PDF (REPORTLAB) - 1 CONTA POR PÁGINA + RESPONSÁVEL 1X POR SETOR
# =============================
def draw_paragraph(c, texto, x, y, max_width, font_name="Helvetica", font_size=10, line_height=12):
    texto = clean_text(texto)
    linhas = simpleSplit(texto, font_name, font_size, max_width)
    for linha in linhas:
        c.drawString(x, y, linha)
        y -= line_height
    return y


def gerar_pdf(dados, data_acomp, periodo, sistema, acompanhadora_nome):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    AZUL = colors.HexColor("#0B2C4D")
    CINZA = colors.HexColor("#F2F2F2")
    PRETO = colors.black

    margem_x = 2 * cm
    pagina = 1

    # Larguras úteis
    w_setor = largura - 4 * cm
    w_pergunta = largura - 4.5 * cm
    w_resposta = largura - 5 * cm

    def cabecalho():
        c.setFillColor(AZUL)
        c.rect(0, altura - 3 * cm, largura, 3 * cm, fill=1, stroke=0)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(largura / 2, altura - 1.8 * cm, "Acompanhamento – Controladoria")

        c.setFont("Helvetica", 10)
        info = (
            f"Acompanhador(a): {acompanhadora_nome} | "
            f"Data do acompanhamento: {data_acomp} | "
            f"Período: {periodo} | "
            f"Sistema Financeiro: {sistema}"
        )
        max_w = largura - 2 * cm
        linhas_info = simpleSplit(info, "Helvetica", 10, max_w)[:2]

        # sobe um pouco
        y_info = altura - 2.35 * cm
        for ln in linhas_info:
            c.drawCentredString(largura / 2, y_info, ln)
            y_info -= 0.40 * cm

        c.setFillColor(PRETO)

    def rodape():
        nonlocal pagina
        c.setFont("Helvetica", 9)
        c.drawCentredString(largura / 2, 1.2 * cm, f"Página {pagina}")

    def nova_pagina():
        nonlocal pagina
        rodape()
        c.showPage()
        pagina += 1
        cabecalho()

    # primeira página
    cabecalho()

    # Y inicial abaixo do header
    def reset_y():
        return altura - 4 * cm

    y = reset_y()

    # Cada item em "dados" já representa UMA CONTA (porque vamos montar assim)
    for idx, conta_bloco in enumerate(dados):
        # cada conta começa em página nova, exceto a primeira
        if idx > 0:
            nova_pagina()
            y = reset_y()

        # Título do setor no topo da página
        setor_nome = conta_bloco.get("setor", "")
        c.setFont("Helvetica-Bold", 12)
        y = draw_paragraph(c, setor_nome, margem_x, y, w_setor,
                           font_name="Helvetica-Bold", font_size=12, line_height=14)
        y -= 0.3 * cm

        # Cards (pergunta/resposta)
        for item in conta_bloco.get("conteudo", []):
            pergunta = clean_text(item.get("pergunta", ""))
            resposta = clean_text(item.get("resposta", ""))

            linhas_pergunta = simpleSplit(pergunta, "Helvetica-Bold", 11, w_pergunta)
            linhas_resposta = simpleSplit(resposta, "Helvetica", 10, w_resposta)

            altura_pergunta_cm = len(linhas_pergunta) * (13 / 28.35)
            altura_resposta_cm = max(1, len(linhas_resposta)) * (12 / 28.35)

            padding_top = 0.5
            padding_mid = 0.15
            padding_bottom = 0.5

            altura_card_cm = padding_top + altura_pergunta_cm + padding_mid + altura_resposta_cm + padding_bottom
            altura_card = altura_card_cm * cm

            # se um card muito grande não couber, quebra página (ainda 1 conta por página continua,
            # só que a conta vai "espalhar" em mais de uma página)
            if y - altura_card < 2.5 * cm:
                nova_pagina()
                y = reset_y()

                # reimprime setor no topo da página seguinte (pra manter contexto)
                c.setFont("Helvetica-Bold", 12)
                y = draw_paragraph(c, setor_nome, margem_x, y, w_setor,
                                   font_name="Helvetica-Bold", font_size=12, line_height=14)
                y -= 0.3 * cm

            c.setFillColor(CINZA)
            c.roundRect(margem_x, y - altura_card, largura - 4 * cm, altura_card, 6, fill=1, stroke=1)
            c.setFillColor(PRETO)

            y -= padding_top * cm

            c.setFont("Helvetica-Bold", 11)
            y = draw_paragraph(c, pergunta, margem_x + 0.3 * cm, y, w_pergunta,
                               font_name="Helvetica-Bold", font_size=11, line_height=13)

            y -= padding_mid * cm

            c.setFont("Helvetica", 10)
            y = draw_paragraph(c, resposta, margem_x + 0.5 * cm, y, w_resposta,
                               font_name="Helvetica", font_size=10, line_height=12)

            y -= padding_bottom * cm

    rodape()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# =============================
# INTERFACE
# =============================
st.title("Acompanhamento – Controladoria")

col1, col2, col3, col4 = st.columns(4)
with col1:
    data_acomp = st.date_input("Data do acompanhamento", date.today(), format="DD/MM/YYYY", key="data_acomp")
    data_hora = data_acomp.strftime("%d/%m/%Y")
with col2:
    periodo_inicio = st.date_input("Período inicial", date.today(), format="DD/MM/YYYY", key="periodo_inicio")
with col3:
    periodo_fim = st.date_input("Período final", date.today(), format="DD/MM/YYYY", key="periodo_fim")
with col4:
    sistema_financeiro = st.selectbox("Sistema Financeiro", ["Conta Azul", "Omie"], key="sistema_financeiro")

periodo = f"{periodo_inicio.strftime('%d/%m/%Y')} a {periodo_fim.strftime('%d/%m/%Y')}"

setores_selecionados = st.multiselect(
    "Selecione o(s) setor(es)",
    setores_disponiveis,
    key="setores_selecionados",
)

# =============================
# CONTAS POR SETOR
# =============================
for setor in setores_selecionados:
    st.markdown("---")
    st.subheader(f"Setor: {setor}")
    st.text_input(f"Responsável – {setor}", key=f"{setor}_responsavel")

    if f"contas_{setor}" not in st.session_state:
        st.session_state[f"contas_{setor}"] = []

    # Renderiza as contas existentes
    for i in range(len(st.session_state[f"contas_{setor}"])):
        st.selectbox("Tipo de conta", TIPOS_CONTA, key=f"{setor}_tipo_{i}")
        st.text_input("Nome da conta", key=f"{setor}_nome_{i}")

        if st.session_state.get(f"{setor}_tipo_{i}") != "Caixa":
            st.text_area("Extrato bancário", key=f"{setor}_extrato_{i}")
        else:
            st.session_state.setdefault(f"{setor}_extrato_{i}", "")

        st.text_area("Conciliações pendentes", key=f"{setor}_conc_{i}")
        st.text_input("Saldo atual", key=f"{setor}_saldo_{i}")
        st.selectbox("Provisões", ["", "Sim", "Não"], key=f"{setor}_prov_{i}")
        st.selectbox("Documentos", ["", "Sim", "Não", "Parcialmente"], key=f"{setor}_doc_{i}")
        st.text_area("Observações", key=f"{setor}_obs_{i}")

        st.markdown("")

    # ✅ Botões no final do setor
    col_add, col_rem = st.columns([1, 1])
    with col_add:
        if st.button(f"➕ Adicionar conta – {setor}", key=f"botao_add_{setor}"):
            st.session_state[f"contas_{setor}"].append({})
            st.rerun()

    with col_rem:
        # só habilita se existir pelo menos 1 conta
        disabled = len(st.session_state[f"contas_{setor}"]) == 0
        if st.button(f"🗑️ Remover última conta – {setor}", key=f"botao_rem_{setor}", disabled=disabled):
            # remove a última conta
            idx = len(st.session_state[f"contas_{setor}"]) - 1
            st.session_state[f"contas_{setor}"].pop()

            # (Opcional, mas recomendado) limpa os campos do session_state dessa conta removida
            keys_to_delete = [
                f"{setor}_tipo_{idx}",
                f"{setor}_nome_{idx}",
                f"{setor}_extrato_{idx}",
                f"{setor}_conc_{idx}",
                f"{setor}_saldo_{idx}",
                f"{setor}_prov_{idx}",
                f"{setor}_doc_{idx}",
                f"{setor}_obs_{idx}",
            ]
            for k in keys_to_delete:
                if k in st.session_state:
                    del st.session_state[k]

            st.rerun()

# =============================
# GERAR PDF
# =============================
modo_geracao = st.radio(
    "Modo de geração",
    ["Gerar PDF e salvar no histórico", "Gerar PDF sem salvar no histórico"],
    key="modo_geracao",
)

if st.button("Gerar PDF", key="botao_gerar_pdf"):
    linhas_sheets = []

    # ✅ Agora o PDF é uma lista "plana": cada item = UMA CONTA (uma página)
    dados_pdf = []

    for setor in setores_selecionados:
        responsavel = clean_text(st.session_state.get(f"{setor}_responsavel", ""))

        contas = st.session_state.get(f"contas_{setor}", [])
        for i in range(len(contas)):
            tipo_conta = clean_text(st.session_state.get(f"{setor}_tipo_{i}", ""))
            nome_conta = clean_text(st.session_state.get(f"{setor}_nome_{i}", ""))
            extrato = clean_text(st.session_state.get(f"{setor}_extrato_{i}", ""))
            conciliacoes = clean_text(st.session_state.get(f"{setor}_conc_{i}", ""))
            saldo_atual = clean_text(st.session_state.get(f"{setor}_saldo_{i}", ""))
            provisoes = clean_text(st.session_state.get(f"{setor}_prov_{i}", ""))
            documentos = clean_text(st.session_state.get(f"{setor}_doc_{i}", ""))
            observacoes = clean_text(st.session_state.get(f"{setor}_obs_{i}", ""))

            # Sheets (mantém)
            linhas_sheets.append([
                data_hora,
                ACOMPANHADORA,
                setor,
                sistema_financeiro,
                responsavel,
                periodo,
                tipo_conta,
                nome_conta,
                extrato,
                conciliacoes,
                saldo_atual,
                provisoes,
                documentos,
                observacoes,
            ])

            # PDF: responsável só na primeira conta do setor
            responsavel_pdf = responsavel if i == 0 else ""

            conteudo = [
                {"pergunta": "Responsável", "resposta": responsavel_pdf},
                {"pergunta": "Tipo de conta", "resposta": tipo_conta},
                {"pergunta": "Nome da conta", "resposta": nome_conta},
                {"pergunta": "Extrato bancário", "resposta": "" if tipo_conta == "Caixa" else extrato},
                {"pergunta": "Conciliações pendentes", "resposta": conciliacoes},
                {"pergunta": "Saldo atual", "resposta": saldo_atual},
                {"pergunta": "Provisões", "resposta": provisoes},
                {"pergunta": "Documentos", "resposta": documentos},
                {"pergunta": "Observações", "resposta": observacoes},
            ]

            # remove campos vazios do PDF
            conteudo = [x for x in conteudo if clean_text(x.get("resposta", ""))]

            if not conteudo:
                continue

            dados_pdf.append({
                "setor": setor,
                "conteudo": conteudo
            })

    if not dados_pdf:
        st.error("❌ Nenhum dado preenchido para gerar o PDF.")
        st.stop()

    if modo_geracao == "Gerar PDF e salvar no histórico":
        salvar_historico(linhas_sheets)

    pdf_bytes = gerar_pdf(dados_pdf, data_hora, periodo, sistema_financeiro, ACOMPANHADORA)

    st.download_button(
        "Baixar PDF",
        data=pdf_bytes,
        file_name="Acompanhamento.pdf",
        mime="application/pdf",
    )

    st.success("✅ PDF gerado com sucesso.")
