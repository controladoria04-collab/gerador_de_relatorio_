import streamlit as st
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import os

# =============================
# CONFIGURAÇÕES GERAIS
# =============================
st.set_page_config(page_title="Gerador de Acompanhamento", layout="wide")

ACOMPANHADORA = "Isabele Dandara"
NOME_ABA = "Histórico"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTE_REGULAR = os.path.join(BASE_DIR, "DejaVuSans.ttf")
FONTE_BOLD = os.path.join(BASE_DIR, "DejaVuSans-Bold.ttf")

# =============================
# VALIDAÇÃO DE FONTE
# =============================
if not os.path.exists(FONTE_REGULAR) or not os.path.exists(FONTE_BOLD):
    st.error("❌ Fontes DejaVuSans não encontradas na pasta do projeto.")
    st.stop()

SETORES_DISPONIVEIS = [
    "Ass. Comunitária",
    "Previdência Brasil",
    "Sinodalidade",
    "Ass. Missionária",
    "Construção Igreja",
    "Discipulado Eusébio",
    "Discipulado Pacajus",
    "Discipulado Quixadá",
    "Fundo dos Necessitados",
    "Fundo Eclesial",
    "Instituto Parresia",
    "Lit. Sacramental",
    "Oficina Dis. Eusébio",
    "Oficina Dis. Pacajus",
    "Oficina Dis. Quixadá",
    "Promoção Humana",
    "Seminaristas",
    "Lançai as Redes",
]

TIPOS_CONTA = [
    "Banco",
    "Caixa",
    "Maquineta",
    "Cartão Pré-pago",
    "Cartão de Crédito",
]

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
# PDF
# =============================
class PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("DejaVu", "", FONTE_REGULAR, uni=True)
        self.add_font("DejaVu", "B", FONTE_BOLD, uni=True)

    def header(self):
        self.set_font("DejaVu", "B", 14)
        self.cell(0, 10, getattr(self, "title", ""), ln=True, align="C")
        self.ln(5)

def gerar_pdf(dados):
    pdf = PDF()
    pdf.title = "Acompanhamento – Controladoria"
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_page()
    pdf.set_font("DejaVu", size=10)

    for bloco in dados:
        pdf.set_font("DejaVu", "B", 11)
        pdf.cell(0, 8, bloco["titulo"], ln=True)

        pdf.set_font("DejaVu", size=10)
        for linha in bloco["conteudo"]:
            pdf.multi_cell(0, 6, linha)
        pdf.ln(3)

    return pdf.output(dest="S")

# =============================
# INTERFACE
# =============================
st.title("Acompanhamento – Controladoria")

st.subheader("Dados gerais")

col1, col2, col3, col4 = st.columns(4)

with col1:
    data_acomp = st.date_input(
        "Data do acompanhamento",
        date.today(),
        format="DD/MM/YYYY",
        key="data_acomp"
    )
    data_hora = data_acomp.strftime("%d/%m/%Y")

with col2:
    periodo_inicio = st.date_input(
        "Período inicial",
        date.today(),
        format="DD/MM/YYYY",
        key="periodo_inicio"
    )

with col3:
    periodo_fim = st.date_input(
        "Período final",
        date.today(),
        format="DD/MM/YYYY",
        key="periodo_fim"
    )

with col4:
    sistema_financeiro = st.selectbox(
        "Sistema Financeiro",
        ["Conta Azul", "Omie"],
        key="sistema_financeiro"
    )

periodo = f"{periodo_inicio.strftime('%d/%m/%Y')} a {periodo_fim.strftime('%d/%m/%Y')}"

setores_selecionados = st.multiselect(
    "Selecione o(s) setor(es)",
    SETORES_DISPONIVEIS,
    key="setores_selecionados"
)

# =============================
# SETORES E CONTAS
# =============================
for setor in setores_selecionados:
    st.markdown("---")
    st.subheader(f"Setor: {setor}")

    responsavel = st.text_input(
        f"Responsável – {setor}",
        key=f"{setor}_responsavel"
    )

    if f"contas_{setor}" not in st.session_state:
        st.session_state[f"contas_{setor}"] = []

    if st.button(f"Adicionar conta – {setor}", key=f"botao_add_{setor}"):
        st.session_state[f"contas_{setor}"].append({})

    for i in range(len(st.session_state[f"contas_{setor}"])):
        tipo_conta = st.selectbox(
            "Tipo de conta",
            TIPOS_CONTA,
            key=f"{setor}_tipo_{i}"
        )
        nome_conta = st.text_input(
            "Nome da conta",
            key=f"{setor}_nome_{i}"
        )
        extrato = st.text_area(
            "Extrato bancário",
            key=f"{setor}_extrato_{i}"
        )
        conciliacoes = st.text_area(
            "Conciliações pendentes",
            key=f"{setor}_conc_{i}"
        )

        saldo_caixa = ""
        if tipo_conta == "Caixa":
            saldo_caixa = st.text_input(
                "Saldo do caixa",
                key=f"{setor}_saldo_{i}"
            )

        provisoes = st.selectbox(
            "Provisões",
            ["Sim", "Não"],
            key=f"{setor}_prov_{i}"
        )
        documentos = st.selectbox(
            "Documentos",
            ["Sim", "Não", "Parcialmente"],
            key=f"{setor}_doc_{i}"
        )
        observacoes = st.text_area(
            "Observações",
            key=f"{setor}_obs_{i}"
        )

# =============================
# AÇÕES
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
            extrato = st.session_state.get(f"{setor}_extrato_{i}", "")
            conciliacoes = st.session_state.get(f"{setor}_conc_{i}", "")
            saldo_caixa = st.session_state.get(f"{setor}_saldo_{i}", "")
            provisoes = st.session_state.get(f"{setor}_prov_{i}", "")
            documentos = st.session_state.get(f"{setor}_doc_{i}", "")
            observacoes = st.session_state.get(f"{setor}_obs_{i}", "")

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

            todos_dados_pdf.append({
                "titulo": f"{setor} – {nome_conta}",
                "conteudo": [
                    f"Responsável: {responsavel}",
                    f"Tipo de conta: {tipo_conta}",
                    f"Extrato bancário: {extrato}",
                    f"Conciliações pendentes: {conciliacoes}",
                    f"Saldo do caixa: {saldo_caixa}",
                    f"Provisões: {provisoes}",
                    f"Documentos: {documentos}",
                    f"Observações: {observacoes}",
                ]
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
