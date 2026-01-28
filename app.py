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

NOME_ABA = "Histórico"

# =============================
# UTIL
# =============================
def normalize_user(s: str) -> str:
    return (s or "").strip().lower()


def clean_text(s: str) -> str:
    # evita caracteres invisíveis que bagunçam quebra de linha
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

ACOMPANHADORA = usuario_atual.replace("_", " ").title()
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
    aba = planilha.worksheet(NOME_ABA)
    aba.append_rows(linhas)


# =============================
# PDF (REPORTLAB) - ESTILO ANTIGO
# =============================
def draw_wrapped(c, text, x, y, max_width, font_name="Helvetica", font_size=10, line_height=12):
    text = clean_text(text)
    linhas = simpleSplit(text, font_name, font_size, max_width)
    for linha in linhas:
        c.drawString(x, y, linha)
        y -= line_height
    return y


def estimate_lines(text, font_name, font_size, max_width):
    text = clean_text(text)
    return simpleSplit(text, font_name, font_size, max_width)


def gerar_pdf(dados_blocos, data_acomp, periodo, sistema):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    AZUL = colors.HexColor("#0B2C4D")
    PRETO = colors.black

    margem_x = 2 * cm
    margem_y = 2 * cm
    y = altura - margem_y
    pagina = 1

    def cabecalho():
        nonlocal y
        c.setFillColor(AZUL)
        c.rect(0, altura - 3 * cm, largura, 3 * cm, fill=1, stroke=0)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(largura / 2, altura - 1.8 * cm, "Acompanhamento - Controladoria")

        c.setFont("Helvetica", 11)
        c.drawCentredString(
            largura / 2,
            altura - 2.5 * cm,
            f"Data do acompanhamento: {data_acomp} | Período: {periodo} | Sistema Financeiro: {sistema}"
        )

        c.setFillColor(PRETO)
        y = altura - 4 * cm

    def rodape():
        c.setFont("Helvetica", 9)
        c.drawCentredString(largura / 2, 1.2 * cm, f"Página {pagina}")

    def nova_pagina():
        nonlocal y, pagina
        rodape()
        c.showPage()
        pagina += 1
        cabecalho()

    cabecalho()

    max_width = largura - 4 * cm

    for bloco in dados_blocos:
        titulo = bloco.get("titulo", "")
        linhas = bloco.get("conteudo", [])

        # Estima altura do bloco para decidir quebra de página
        # Título: fonte 11 bold, line_height ~ 14
        titulo_lines = estimate_lines(titulo, "Helvetica-Bold", 11, max_width)
        height_title = len(titulo_lines) * 14

        # Conteúdo: fonte 10, line_height ~ 12
        content_height = 0
        for ln in linhas:
            ln_lines = estimate_lines(ln, "Helvetica", 10, max_width)
            content_height += len(ln_lines) * 12

        # espaçamentos
        estimated = height_title + content_height + 18  # 18 = folga entre blocos

        if y - estimated < 2.5 * cm:
            nova_pagina()

        # Título
        c.setFont("Helvetica-Bold", 11)
        y = draw_wrapped(c, titulo, margem_x, y, max_width, font_name="Helvetica-Bold", font_size=11, line_height=14)

        # Conteúdo
        c.setFont("Helvetica", 10)
        for ln in linhas:
            y = draw_wrapped(c, ln, margem_x, y, max_width, font_name="Helvetica", font_size=10, line_height=12)

        y -= 10  # espaço entre blocos

        # Se estiver muito perto do rodapé, já pula
        if y < 2.5 * cm:
            nova_pagina()

    rodape()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# =============================
# INTERFACE
# =============================
st.title("Acompanhamento - Controladoria")

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
    st.text_input(f"Responsável - {setor}", key=f"{setor}_responsavel")

    if f"contas_{setor}" not in st.session_state:
        st.session_state[f"contas_{setor}"] = []

    if st.button(f"Adicionar conta - {setor}", key=f"botao_add_{setor}"):
        st.session_state[f"contas_{setor}"].append({})

    for i in range(len(st.session_state[f"contas_{setor}"])):
        tipo_conta = st.selectbox("Tipo de conta", TIPOS_CONTA, key=f"{setor}_tipo_{i}")
        st.text_input("Nome da conta", key=f"{setor}_nome_{i}")

        if tipo_conta == "Caixa":
            st.text_input("Saldo do caixa", key=f"{setor}_saldo_{i}")
            st.text_area("Extrato bancário", value="", key=f"{setor}_extrato_{i}", disabled=True)
        else:
            st.text_area("Extrato bancário", key=f"{setor}_extrato_{i}")
            st.text_input("Saldo do caixa", value="", key=f"{setor}_saldo_{i}", disabled=True)

        st.text_area("Conciliações pendentes", key=f"{setor}_conc_{i}")
        st.selectbox("Provisões", ["", "Sim", "Não"], key=f"{setor}_prov_{i}")
        st.selectbox("Documentos", ["", "Sim", "Não", "Parcialmente"], key=f"{setor}_doc_{i}")
        st.text_area("Observações", key=f"{setor}_obs_{i}")

# =============================
# GERAR PDF
# =============================
modo_geracao = st.radio(
    "Modo de geração",
    ["Gerar PDF e salvar no histórico", "Gerar PDF sem salvar no histórico"],
    key="modo_geracao",
)

if st.button("Gerar PDF", key="botao_gerar_pdf"):
    todos_blocos_pdf = []
    linhas_sheets = []

    for setor in setores_selecionados:
        responsavel = clean_text(st.session_state.get(f"{setor}_responsavel", ""))

        contas = st.session_state.get(f"contas_{setor}", [])
        for i in range(len(contas)):
            tipo_conta = clean_text(st.session_state.get(f"{setor}_tipo_{i}", ""))
            nome_conta = clean_text(st.session_state.get(f"{setor}_nome_{i}", ""))
            extrato = clean_text(st.session_state.get(f"{setor}_extrato_{i}", ""))
            conciliacoes = clean_text(st.session_state.get(f"{setor}_conc_{i}", ""))
            saldo_caixa = clean_text(st.session_state.get(f"{setor}_saldo_{i}", ""))
            provisoes = clean_text(st.session_state.get(f"{setor}_prov_{i}", ""))
            documentos = clean_text(st.session_state.get(f"{setor}_doc_{i}", ""))
            observacoes = clean_text(st.session_state.get(f"{setor}_obs_{i}", ""))

            # Sheets
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
                saldo_caixa,
                provisoes,
                documentos,
                observacoes,
            ])

            # PDF (estilo antigo)
            conteudo_pdf = []
            if responsavel:
                conteudo_pdf.append(f"Responsável: {responsavel}")
            if tipo_conta:
                conteudo_pdf.append(f"Tipo de conta: {tipo_conta}")
            if nome_conta:
                conteudo_pdf.append(f"Nome da conta: {nome_conta}")
            if extrato and tipo_conta != "Caixa":
                conteudo_pdf.append(f"Extrato bancário: {extrato}")
            if conciliacoes:
                conteudo_pdf.append(f"Conciliações pendentes: {conciliacoes}")
            if saldo_caixa and tipo_conta == "Caixa":
                conteudo_pdf.append(f"Saldo do caixa: {saldo_caixa}")
            if provisoes:
                conteudo_pdf.append(f"Provisões: {provisoes}")
            if documentos:
                conteudo_pdf.append(f"Documentos: {documentos}")
            if observacoes:
                conteudo_pdf.append(f"Observações: {observacoes}")

            if conteudo_pdf:
                titulo = f"{setor} - {nome_conta}" if nome_conta else setor
                todos_blocos_pdf.append({"titulo": titulo, "conteudo": conteudo_pdf})

    if not todos_blocos_pdf:
        st.error("❌ Nenhum dado preenchido para gerar o PDF.")
        st.stop()

    if modo_geracao == "Gerar PDF e salvar no histórico":
        salvar_historico(linhas_sheets)

    pdf_bytes = gerar_pdf(todos_blocos_pdf, data_hora, periodo, sistema_financeiro)

    st.download_button(
        "Baixar PDF",
        data=pdf_bytes,
        file_name="Acompanhamento.pdf",
        mime="application/pdf",
    )

    st.success("✅ PDF gerado com sucesso.")
