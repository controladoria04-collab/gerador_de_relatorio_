import os
import json
from datetime import date

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF

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


def normalize_user(s: str) -> str:
    """Normaliza username pra evitar erro de maiúscula/minúscula, espaços etc."""
    return (s or "").strip().lower()


def safe_pdf_text(s: str) -> str:
    """
    FPDF clássico (latin-1) pode quebrar com caracteres Unicode (ex: travessão “–”).
    Aqui a gente força para latin-1 com replace.
    """
    return (s or "").encode("latin-1", "replace").decode("latin-1")


def load_setores_por_usuario() -> dict:
    """Carrega e normaliza o JSON de setores."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "setores_usuarios.json")

    if not os.path.exists(json_path):
        st.error(f"❌ Arquivo não encontrado: {json_path}")
        st.stop()

    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # normaliza as chaves do JSON
    return {normalize_user(k): v for k, v in raw.items()}


def load_users_from_secrets() -> dict:
    """Carrega e normaliza os usuários do secrets.toml."""
    if "users" not in st.secrets:
        st.error("❌ 'users' não encontrado no secrets.toml.")
        st.stop()

    raw = st.secrets["users"]  # ex.: Pedrina_Freita = { senha = "123" }
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
# CARREGAR SETORES POR USUÁRIO
# =============================
setores_por_usuario = load_setores_por_usuario()
usuario_atual = normalize_user(st.session_state.get("usuario", ""))

# Se quiser mostrar o nome bonitinho no PDF/título
ACOMPANHADORA = usuario_atual.replace("_", " ").title()

setores_disponiveis = setores_por_usuario.get(usuario_atual, [])
if not setores_disponiveis:
    st.warning("⚠️ Nenhum setor encontrado para este usuário (verifique o JSON e o username).")

# =============================
# GOOGLE SHEETS
# =============================
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
    for linha in linhas:
        aba.append_row(linha)


# =============================
# PDF
# =============================
class PDF(FPDF):
    def header(self):
        # Header azul
        self.set_fill_color(0, 51, 102)
        self.rect(0, 0, 210, 15, "F")
        self.set_font("Arial", "B", 14)
        self.set_text_color(255, 255, 255)
        # Evitar travessão Unicode “–” -> usar "-"
        title = f"Acompanhamento - Controladoria ({ACOMPANHADORA})"
        self.cell(0, 10, safe_pdf_text(title), ln=True, align="C")
        self.ln(5)


def gerar_pdf(dados):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(0, 0, 0)

    for bloco in dados:
        pdf.set_font("Arial", "B", 11)
        pdf.multi_cell(0, 8, safe_pdf_text(bloco["titulo"]))
        pdf.set_font("Arial", size=10)
        for linha in bloco["conteudo"]:
            pdf.multi_cell(0, 6, safe_pdf_text(linha))
        pdf.ln(3)

    # Retorna bytes
    return pdf.output(dest="S").encode("latin-1", "replace")


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
    responsavel = st.text_input(f"Responsável - {setor}", key=f"{setor}_responsavel")

    if f"contas_{setor}" not in st.session_state:
        st.session_state[f"contas_{setor}"] = []

    if st.button(f"Adicionar conta - {setor}", key=f"botao_add_{setor}"):
        st.session_state[f"contas_{setor}"].append({})

    for i in range(len(st.session_state[f"contas_{setor}"])):
        tipo_conta = st.selectbox("Tipo de conta", TIPOS_CONTA, key=f"{setor}_tipo_{i}")
        nome_conta = st.text_input("Nome da conta", key=f"{setor}_nome_{i}")

        extrato = "" if tipo_conta == "Caixa" else st.text_area("Extrato bancário", key=f"{setor}_extrato_{i}")
        saldo_caixa = st.text_input("Saldo do caixa", key=f"{setor}_saldo_{i}") if tipo_conta == "Caixa" else ""

        conciliacoes = st.text_area("Conciliações pendentes", key=f"{setor}_conc_{i}")
        provisoes = st.selectbox("Provisões", ["", "Sim", "Não"], key=f"{setor}_prov_{i}")
        documentos = st.selectbox("Documentos", ["", "Sim", "Não", "Parcialmente"], key=f"{setor}_doc_{i}")
        observacoes = st.text_area("Observações", key=f"{setor}_obs_{i}")

# =============================
# GERAR PDF
# =============================
modo_geracao = st.radio(
    "Modo de geração",
    ["Gerar PDF e salvar no histórico", "Gerar PDF sem salvar no histórico"],
    key="modo_geracao",
)

if st.button("Gerar PDF", key="botao_gerar_pdf"):
    todos_dados_pdf = []
    linhas_sheets = []

    for setor in setores_selecionados:
        responsavel = st.session_state.get(f"{setor}_responsavel", "")

        contas = st.session_state.get(f"contas_{setor}", [])
        for i in range(len(contas)):
            tipo_conta = st.session_state.get(f"{setor}_tipo_{i}", "")
            nome_conta = st.session_state.get(f"{setor}_nome_{i}", "")
            extrato = st.session_state.get(f"{setor}_extrato_{i}", "")
            conciliacoes = st.session_state.get(f"{setor}_conc_{i}", "")
            saldo_caixa = st.session_state.get(f"{setor}_saldo_{i}", "")
            provisoes = st.session_state.get(f"{setor}_prov_{i}", "")
            documentos = st.session_state.get(f"{setor}_doc_{i}", "")
            observacoes = st.session_state.get(f"{setor}_obs_{i}", "")

            # Linha para Sheets
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

            # Conteúdo para PDF (só campos preenchidos)
            conteudo_pdf = []
            if responsavel:
                conteudo_pdf.append(f"Responsável: {responsavel}")
            if tipo_conta:
                conteudo_pdf.append(f"Tipo de conta: {tipo_conta}")
            if nome_conta:
                conteudo_pdf.append(f"Nome da conta: {nome_conta}")
            if extrato:
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
                todos_dados_pdf.append({"titulo": titulo, "conteudo": conteudo_pdf})

    if not todos_dados_pdf:
        st.error("❌ Nenhum dado preenchido para gerar o PDF.")
        st.stop()

    if modo_geracao == "Gerar PDF e salvar no histórico":
        salvar_historico(linhas_sheets)

    pdf_bytes = gerar_pdf(todos_dados_pdf)

    st.download_button(
        "Baixar PDF",
        data=pdf_bytes,
        file_name="Acompanhamento.pdf",
        mime="application/pdf",
    )

    st.success("PDF gerado com sucesso.")
