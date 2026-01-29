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


def format_nome_acompanhador(username: str) -> str:
    # Isabele_Dandara -> Isabele Dandara
    return (username or "").replace("_", " ").strip().title()


def clean_text(s: str) -> str:
    # remove tabs e caracteres invisíveis que atrapalham quebra de linha
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
    aba = planilha.worksheet(NOME_ABA)
    aba.append_rows(linhas)


# =============================
# PDF (REPORTLAB) - LAYOUT CARDS (IGUAL IMAGEM)
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
    y = altura - 2 * cm
    pagina = 1

    def cabecalho():
        nonlocal y
        c.setFillColor(AZUL)
        c.rect(0, altura - 3 * cm, largura, 3 * cm, fill=1, stroke=0)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(largura / 2, altura - 1.8 * cm, "Acompanhamento – Controladoria")

        c.setFont("Helvetica", 11)
        c.drawCentredString(
            largura / 2,
            altura - 2.5 * cm,
            f"Acompanhador(a): {acompanhadora_nome} | Data do acompanhamento: {data_acomp} | Período: {periodo} | Sistema Financeiro: {sistema}"
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
    c.setFont("Helvetica", 10)

    for bloco in dados:
        # Se estiver muito perto do fim antes de escrever o nome do setor
        if y < 3.5 * cm:
            nova_pagina()

        # Nome do setor
        c.setFont("Helvetica-Bold", 12)
        y = draw_paragraph(
            c,
            bloco.get("setor", ""),
            margem_x,
            y,
            largura - 4 * cm,
            font_name="Helvetica-Bold",
            font_size=12,
            line_height=14
        )
        y -= 0.3 * cm

        # Cards pergunta/resposta (layout igual imagem)
        for item in bloco.get("conteudo", []):
            pergunta = clean_text(item.get("pergunta", ""))
            resposta = clean_text(item.get("resposta", ""))

            # Calcula linhas reais para o card ter altura correta (sem estourar)
            linhas_pergunta = simpleSplit(pergunta, "Helvetica-Bold", 11, largura - 4.5 * cm)
            linhas_resposta = simpleSplit(resposta, "Helvetica", 10, largura - 5 * cm)

            # Alturas aproximadas em cm (usando line heights do draw)
            altura_pergunta_cm = len(linhas_pergunta) * (13 / 28.35)  # 13pt -> cm
            altura_resposta_cm = max(1, len(linhas_resposta)) * (12 / 28.35)  # garante espaço mesmo se vazio

            padding_top = 0.5
            padding_mid = 0.15
            padding_bottom = 0.5

            altura_card_cm = padding_top + altura_pergunta_cm + padding_mid + altura_resposta_cm + padding_bottom
            altura_card = altura_card_cm * cm

            # Quebra página se o card não couber
            if y - altura_card < 2.5 * cm:
                nova_pagina()

            # Card
            c.setFillColor(CINZA)
            c.roundRect(margem_x, y - altura_card, largura - 4 * cm, altura_card, 6, fill=1, stroke=1)
            c.setFillColor(PRETO)

            # Conteúdo do card
            y -= padding_top * cm

            # Pergunta
            c.setFont("Helvetica-Bold", 11)
            y = draw_paragraph(
                c,
                pergunta,
                margem_x + 0.3 * cm,
                y,
                largura - 4.5 * cm,
                font_name="Helvetica-Bold",
                font_size=11,
                line_height=13
            )

            y -= padding_mid * cm

            # Resposta
            c.setFont("Helvetica", 10)
            y = draw_paragraph(
                c,
                resposta,
                margem_x + 0.5 * cm,
                y,
                largura - 5 * cm,
                font_name="Helvetica",
                font_size=10,
                line_height=12
            )

            y -= padding_bottom * cm

        y -= 0.8 * cm

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

    if st.button(f"Adicionar conta – {setor}", key=f"botao_add_{setor}"):
        st.session_state[f"contas_{setor}"].append({})

    for i in range(len(st.session_state[f"contas_{setor}"])):
        tipo_conta = st.selectbox("Tipo de conta", TIPOS_CONTA, key=f"{setor}_tipo_{i}")
        st.text_input("Nome da conta", key=f"{setor}_nome_{i}")

        # Extrato só para não-caixa (mantém sua regra)
        if tipo_conta != "Caixa":
            st.text_area("Extrato bancário", key=f"{setor}_extrato_{i}")
        else:
            # cria a key mesmo assim (pra não faltar no PDF/Sheets)
            st.session_state.setdefault(f"{setor}_extrato_{i}", "")

        st.text_area("Conciliações pendentes", key=f"{setor}_conc_{i}")

        # ✅ Ajuste pedido: antes era "Saldo do caixa" e desativado nos bancos.
        # Agora é "Saldo atual" e SEMPRE editável.
        st.text_input("Saldo atual", key=f"{setor}_saldo_{i}")

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
    dados_pdf = []
    linhas_sheets = []

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

            # Sheets (mantém as colunas; só estamos usando "saldo_atual" no lugar do antigo saldo_caixa)
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

            # PDF no layout de cards (igual imagem)
            bloco = {
                "setor": setor,
                "conteudo": [
                    {"pergunta": "Responsável", "resposta": responsavel},
                    {"pergunta": "Tipo de conta", "resposta": tipo_conta},
                    {"pergunta": "Nome da conta", "resposta": nome_conta},
                    {"pergunta": "Extrato bancário", "resposta": "" if tipo_conta == "Caixa" else extrato},
                    {"pergunta": "Conciliações pendentes", "resposta": conciliacoes},
                    {"pergunta": "Saldo atual", "resposta": saldo_atual},
                    {"pergunta": "Provisões", "resposta": provisoes},
                    {"pergunta": "Documentos", "resposta": documentos},
                    {"pergunta": "Observações", "resposta": observacoes},
                ]
            }

            dados_pdf.append(bloco)

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
