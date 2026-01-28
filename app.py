import streamlit as st
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json

# =============================
# CONFIGURAÇÕES
# =============================
st.set_page_config(page_title="Gerador de Acompanhamento", layout="wide")

# =============================
# LOGIN DE USUÁRIOS
# =============================
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.title("Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    usuarios = st.secrets["users"]

    if st.button("Entrar"):
        if usuario in usuarios and senha == usuarios[usuario]["senha"]:
            st.session_state["logado"] = True
            st.session_state["usuario"] = usuario
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha incorretos")
    st.stop()

# =============================
# SETORES POR USUÁRIO
# =============================
with open("setores_usuarios.json", "r", encoding="utf-8") as f:
    setores_usuarios = json.load(f)

usuario_atual = st.session_state["usuario"]
SETORES_DISPONIVEIS = setores_usuarios.get(usuario_atual, [])

TIPOS_CONTA = [
    "Banco",
    "Caixa",
    "Maquineta",
    "Cartão Pré-pago",
    "Cartão de Crédito",
]

ACOMPANHADORA = usuario_atual  # Nome do usuário logado
NOME_ABA = "Histórico"

# =============================
# GOOGLE SHEETS
# =============================
def conectar_sheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(creds)

def salvar_historico(linhas):
    client = conectar_sheets()
    planilha = client.open_by_url(st.secrets["SPREADSHEET_URL"])
    aba = planilha.worksheet(NOME_ABA)
    for linha in linhas:
        aba.append_row(linha)

# =============================
# PDF UTF-8
# =============================
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, f"Acompanhamento – {ACOMPANHADORA}", ln=True, align="C")
        self.ln(5)

def gerar_pdf(dados):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    for bloco in dados:
        pdf.set_font("Arial", "B", 11)
        pdf.multi_cell(0, 8, bloco["titulo"])
        pdf.set_font("Arial", size=10)
        for linha in bloco["conteudo"]:
            if linha:  # só adiciona se não estiver vazio
                pdf.multi_cell(0, 6, linha)
        pdf.ln(3)
    return pdf.output(dest="S").encode("latin-1")

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
setores_selecionados = st.multiselect("Selecione o(s) setor(es)", SETORES_DISPONIVEIS, key="setores_selecionados")

# =============================
# CONTAS POR SETOR
# =============================
for setor in setores_selecionados:
    st.markdown("---")
    st.subheader(f"Setor: {setor}")
    responsavel = st.text_input(f"Responsável – {setor}", key=f"{setor}_responsavel")

    if f"contas_{setor}" not in st.session_state:
        st.session_state[f"contas_{setor}"] = []

    if st.button(f"Adicionar conta – {setor}", key=f"botao_add_{setor}"):
        st.session_state[f"contas_{setor}"].append({})

    for i in range(len(st.session_state[f"contas_{setor}"])):
        tipo_conta = st.selectbox("Tipo de conta", TIPOS_CONTA, key=f"{setor}_tipo_{i}")
        nome_conta = st.text_input("Nome da conta", key=f"{setor}_nome_{i}")

        # Se for Caixa, mostra saldo do caixa e não mostra extrato
        saldo_caixa = ""
        extrato = ""
        if tipo_conta == "Caixa":
            saldo_caixa = st.text_input("Saldo do caixa", key=f"{setor}_saldo_{i}")
        else:
            extrato = st.text_area("Extrato bancário", key=f"{setor}_extrato_{i}")

        conciliacoes = st.text_area("Conciliações pendentes", key=f"{setor}_conc_{i}")

        # Sim/Não/Parcialmente começam vazios
        provisoes = st.selectbox("Provisões", ["", "Sim", "Não"], key=f"{setor}_prov_{i}")
        documentos = st.selectbox("Documentos", ["", "Sim", "Não", "Parcialmente"], key=f"{setor}_doc_{i}")
        observacoes = st.text_area("Observações", key=f"{setor}_obs_{i}")

# =============================
# GERAR PDF
# =============================
modo_geracao = st.radio(
    "Modo de geração",
    ["Gerar PDF e salvar no histórico", "Gerar PDF sem salvar no histórico"],
    key="modo_geracao"
)

if st.button("Gerar PDF", key="botao_gerar_pdf"):
    todos_dados_pdf = []
    linhas_sheets = []

    for setor in setores_selecionados:
        responsavel = st.session_state.get(f"{setor}_responsavel", "")

        for i in range(len(st.session_state.get(f"contas_{setor}", []))):
            tipo_conta = st.session_state.get(f"{setor}_tipo_{i}", "")
            nome_conta = st.session_state.get(f"{setor}_nome_{i}", "")

            # Só adiciona saldo/extrato conforme tipo
            saldo_caixa = st.session_state.get(f"{setor}_saldo_{i}", "") if tipo_conta == "Caixa" else ""
            extrato = st.session_state.get(f"{setor}_extrato_{i}", "") if tipo_conta != "Caixa" else ""

            conciliacoes = st.session_state.get(f"{setor}_conc_{i}", "")
            provisoes = st.session_state.get(f"{setor}_prov_{i}", "")
            documentos = st.session_state.get(f"{setor}_doc_{i}", "")
            observacoes = st.session_state.get(f"{setor}_obs_{i}", "")

            # Monta linha da planilha
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

            # Monta PDF
            conteudo_pdf = []
            if responsavel: conteudo_pdf.append(f"Responsável: {responsavel}")
            if tipo_conta: conteudo_pdf.append(f"Tipo de conta: {tipo_conta}")
            if saldo_caixa: conteudo_pdf.append(f"Saldo do caixa: {saldo_caixa}")
            if extrato: conteudo_pdf.append(f"Extrato bancário: {extrato}")
            if conciliacoes: conteudo_pdf.append(f"Conciliações pendentes: {conciliacoes}")
            if provisoes: conteudo_pdf.append(f"Provisões: {provisoes}")
            if documentos: conteudo_pdf.append(f"Documentos: {documentos}")
            if observacoes: conteudo_pdf.append(f"Observações: {observacoes}")

            todos_dados_pdf.append({
                "titulo": f"{setor} – {nome_conta}",
                "conteudo": conteudo_pdf
            })

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
        mime="application/pdf"
    )

    st.success("PDF gerado com sucesso.")
