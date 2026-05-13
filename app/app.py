import re
import streamlit as st
import os
import sys
import cv2
import pytesseract
import pandas as pd
import tempfile

# Add the parent directory of 'app' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.paths import resolve_poppler_bin, resolve_tesseract_cmd
from src.pdf_converter import convert_pdfs_to_images
from src.preprocess import preprocess_image
from src.ocr_engine import run_ocr, get_full_text, ocr_stats
from src.extractor import extract_fields
from src.visualize import draw_boxes

poppler_bin_path = resolve_poppler_bin()
tesseract_cmd = resolve_tesseract_cmd()
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

# --- UI helpers -----------------------------------------------------------------

FIELD_ROWS = [
    ("invoice_number", "Nº da fatura"),
    ("order_number", "Nº da encomenda"),
    ("date", "Data"),
    ("payment_details", "Condições de pagamento"),
    ("invoice_total", "Total"),
]

DISPLAY_COLUMNS = {
    "source_file": "Ficheiro",
    "invoice_number": "Nº fatura",
    "order_number": "Nº encomenda",
    "date": "Data",
    "payment_details": "Pagamento",
    "invoice_total": "Total (€)",
    "ocr_mean_confidence": "OCR conf. (%)",
    "ocr_word_count": "Palavras OCR",
    "completeness_pct": "Completude",
    "prazo_dias": "Prazo (dias)",
}


def _fmt_cell(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, str) and not value.strip():
        return "—"
    return str(value)


def _fmt_money(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    # European style: thousands . decimal ,
    s = f"{v:,.2f}"
    if "." in s and "," in s:
        pass
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def _payment_days_hint(payment: str | None) -> int | None:
    if not payment:
        return None
    m = re.search(r"(\d+)\s*days?", str(payment), re.IGNORECASE)
    return int(m.group(1)) if m else None


def _completeness(record: dict) -> int:
    keys = ("invoice_number", "order_number", "date", "payment_details", "invoice_total")
    filled = sum(1 for k in keys if record.get(k) not in (None, "", []))
    return int(round(100 * filled / len(keys)))


def _detail_table(record: dict) -> pd.DataFrame:
    rows = []
    for key, label in FIELD_ROWS:
        raw = record.get(key)
        if key == "invoice_total":
            val = _fmt_money(raw)
        else:
            val = _fmt_cell(raw)
        rows.append({"Campo": label, "Valor": val})
    return pd.DataFrame(rows)


def _enrich_record(record: dict, source_file: str, stats: dict) -> dict:
    out = {**record, **stats, "source_file": source_file}
    out["prazo_dias"] = _payment_days_hint(record.get("payment_details"))
    out["completeness_pct"] = _completeness(record)
    return out


def _render_insights(df: pd.DataFrame) -> None:
    st.markdown("### Resumo e insights")
    totals = pd.to_numeric(df["invoice_total"], errors="coerce")
    conf = pd.to_numeric(df["ocr_mean_confidence"], errors="coerce")
    words = pd.to_numeric(df["ocr_word_count"], errors="coerce")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Páginas processadas", len(df))
    sum_t = totals.sum()
    m2.metric("Volume faturado (soma)", f"€ {sum_t:,.0f}".replace(",", ".") if pd.notna(sum_t) else "—")
    avg_t = totals.mean()
    m3.metric("Ticket médio", f"€ {avg_t:,.0f}".replace(",", ".") if pd.notna(avg_t) else "—")
    avg_c = conf.mean()
    m4.metric("Confiança média do OCR", f"{avg_c:.1f} %" if pd.notna(avg_c) else "—")

    d1, d2, d3 = st.columns(3)
    dates = pd.to_datetime(df["date"], errors="coerce")
    if dates.notna().any():
        d1.metric("Data mais antiga", dates.min().strftime("%Y-%m-%d"))
        d2.metric("Data mais recente", dates.max().strftime("%Y-%m-%d"))
    else:
        d1.metric("Data mais antiga", "—")
        d2.metric("Data mais recente", "—")
    avg_words = words.mean()
    d3.metric("Palavras lidas (média)", f"{avg_words:.0f}" if pd.notna(avg_words) else "—")

    if "completeness_pct" in df.columns:
        st.caption(
            f"Completude média dos campos extraídos: **{df['completeness_pct'].mean():.0f}%** "
            "(campos: fatura, encomenda, data, pagamento, total)."
        )

    pay = df["payment_details"].dropna().astype(str).unique()
    if len(pay):
        st.caption("**Condições de pagamento detetadas:** " + " · ".join(f"`{p}`" for p in pay[:5]))
    if "prazo_dias" in df.columns and df["prazo_dias"].notna().any():
        mx = int(df["prazo_dias"].max())
        st.caption(f"Prazo máximo inferido a partir do texto: **{mx} dias**.")


# --- Page ------------------------------------------------------------------------

st.set_page_config(page_title="Invoice OCR", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    "<style>div.block-container{padding-top:1.2rem;} h1{margin-bottom:0.25rem;}</style>",
    unsafe_allow_html=True,
)
st.title("Invoice OCR")
st.caption("Extração de campos, métricas de OCR e exportação CSV — leitura apenas (sem edição manual).")

if not poppler_bin_path:
    st.warning(
        "**Poppler** não encontrado. Na raiz do projeto corre: "
        "`python scripts/download_poppler.py` (descarrega e extrai para `poppler-windows/`). "
        "Ou define **POPPLER_BIN** com o caminho da pasta `bin` que contém `pdfinfo.exe`, "
        "ou adiciona essa pasta ao PATH."
    )

uploaded_files = st.file_uploader("Carregar PDFs de faturas", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if not poppler_bin_path:
        st.error(
            "Sem Poppler. Corre na raiz do projeto: `python scripts/download_poppler.py` "
            "ou configura **POPPLER_BIN**."
        )
        st.stop()

    all_results: list[dict] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for uploaded_file in uploaded_files:
            pdf_path = os.path.join(tmpdir, uploaded_file.name)
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.read())

        image_paths = convert_pdfs_to_images(
            pdf_dir=tmpdir, image_dir=tmpdir, dpi=300, poppler_path=poppler_bin_path
        )
        st.success(f"{len(image_paths)} página(s) a partir de {len(uploaded_files)} PDF(s).")

        for image_path in image_paths:
            base = os.path.basename(image_path)
            st.divider()
            st.subheader(base)

            image = cv2.imread(image_path)
            if image is None:
                st.error("Não foi possível carregar a imagem.")
                continue

            preprocessed = preprocess_image(image)
            ocr_result = run_ocr(preprocessed)
            full_text = get_full_text(ocr_result)
            stats = ocr_stats(ocr_result)
            extracted = extract_fields(full_text)
            row = _enrich_record(extracted, base, stats)

            c_metrics = st.columns(4)
            c_metrics[0].metric("Confiança OCR", f"{stats['ocr_mean_confidence']} %" if stats["ocr_mean_confidence"] else "—")
            c_metrics[1].metric("Palavras detetadas", stats["ocr_word_count"])
            c_metrics[2].metric("Completude", f"{row['completeness_pct']} %")
            prazo = row.get("prazo_dias")
            c_metrics[3].metric("Prazo (texto)", f"{prazo} dias" if prazo else "—")

            st.markdown("##### Dados extraídos")
            st.dataframe(
                _detail_table(row),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Campo": st.column_config.TextColumn("Campo", width="medium"),
                    "Valor": st.column_config.TextColumn("Valor", width="large"),
                },
            )

            all_results.append(row)

            boxed_img = draw_boxes(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), ocr_result)
            with st.expander("Pré-visualização OCR (caixas)", expanded=False):
                st.image(boxed_img, width="stretch")

        if all_results:
            df = pd.DataFrame(all_results)
            st.divider()
            _render_insights(df)

            st.markdown("### Tabela consolidada")
            display_df = df.rename(columns={k: v for k, v in DISPLAY_COLUMNS.items() if k in df.columns})
            st.dataframe(
                display_df,
                hide_index=True,
                use_container_width=True,
            )

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Descarregar CSV (dados técnicos)",
                data=csv,
                file_name="all_invoices_data.csv",
                mime="text/csv",
            )
