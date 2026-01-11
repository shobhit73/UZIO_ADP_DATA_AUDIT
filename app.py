import io
import re
from datetime import datetime, date

import numpy as np
import pandas as pd
import streamlit as st


# =========================================================
# UZIO vs ADP Comparison (ADP = Source of Truth) - Streamlit
#
# OUTPUT TABS:
#   - Summary
#   - Field_Summary_By_Status
#   - Mapping_ADP_Col_Missing
#   - Comparison_Detail_AllFields
#   - Mismatches_Only
#
# Rules included:
# 1) ZIPCODE compares first 5 digits (21239 vs 21239-4214 => OK)
# 2) Gender normalization: ADP Man/Male -> male, Woman/Female -> female
# 3) Employment Status: ADP retired/terminated => UZIO terminated OK; UZIO active => mismatch
# 4) Termination Reason: UZIO "Other" + ADP reason in allowed list => OK
# 5) PayType exceptions:
#    - HOURLY: missing Annual Salary in UZIO => OK
#    - SALARIED: missing Hourly Pay Rate in UZIO => OK
# =========================================================

UZIO_SHEET_DEFAULT = "Uzio Data"
ADP_SHEET_DEFAULT = "ADP Data"
MAP_SHEET_DEFAULT = "Mapping Sheet"

OUTPUT_FILENAME = "UZIO_vs_ADP_Comparison_Report_ADP_SourceOfTruth.xlsx"

# ---------- Helpers ----------
def norm_colname(c: str) -> str:
    if c is None:
        return ""
    c = str(c).replace("\n", " ").replace("\r", " ")
    c = c.replace("\u00A0", " ")
    c = re.sub(r"\s+", " ", c).strip()
    c = c.replace("*", "")
    c = c.strip('"').strip("'")
    return c

def norm_blank(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    if isinstance(x, str) and x.strip().lower() in {"", "nan", "none", "null"}:
        return ""
    return x

def try_parse_date(x):
    x = norm_blank(x)
    if x == "":
        return ""
    if isinstance(x, (datetime, date, np.datetime64, pd.Timestamp)):
        return pd.to_datetime(x).date().isoformat()
    if isinstance(x, str):
        s = x.strip()
        try:
            return pd.to_datetime(s, errors="raise").date().isoformat()
        except Exception:
            return s
    return str(x)

def digits_only(x):
    x = norm_blank(x)
    if x == "":
        return ""
    return re.sub(r"\D", "", str(x))

def norm_zip_first5(x):
    x = norm_blank(x)
    if x == "":
        return ""
    if isinstance(x, (int, np.integer)):
        s = str(int(x))
    elif isinstance(x, (float, np.floating)) and float(x).is_integer():
        s = str(int(x))
    else:
        s = re.sub(r"[^\d]", "", str(x).strip())
    if s == "":
        return ""
    if 0 < len(s) < 5:
        s = s.zfill(5)
    return s[:5]

NUMERIC_KEYWORDS = {"salary", "rate", "hours", "amount"}
DATE_KEYWORDS = {"date", "dob", "birth"}
SSN_KEYWORDS = {"ssn", "tax id"}
ZIP_KEYWORDS = {"zip", "zipcode", "postal"}
GENDER_KEYWORDS = {"gender"}

def norm_gender(x):
    x = norm_blank(x)
    if x == "":
        return ""
    s = str(x).replace("\u00A0", " ")
    s = re.sub(r"\s+", " ", s).strip().casefold()
    if "female" in s or "woman" in s:
        return "female"
    if "male" in s or "man" in s:
        return "male"
    return s

def norm_value(x, field_name: str):
    f = norm_colname(field_name).lower()
    x = norm_blank(x)
    if x == "":
        return ""

    if any(k in f for k in GENDER_KEYWORDS):
        return norm_gender(x)

    if any(k in f for k in SSN_KEYWORDS):
        return digits_only(x)

    if any(k in f for k in ZIP_KEYWORDS):
        return norm_zip_first5(x)

    if any(k in f for k in DATE_KEYWORDS):
        return try_parse_date(x)

    if any(k in f for k in NUMERIC_KEYWORDS):
        if isinstance(x, (int, float, np.integer, np.floating)):
            return float(x)
        if isinstance(x, str):
            s = x.strip().replace(",", "").replace("$", "")
            try:
                return float(s)
            except Exception:
                return re.sub(r"\s+", " ", x.strip()).casefold()

    if isinstance(x, str):
        return re.sub(r"\s+", " ", x.strip()).casefold()
    return str(x).casefold()

def norm_emp_key_series(s: pd.Series) -> pd.Series:
    s2 = s.astype(object).where(~s.isna(), "")
    def _fix(v):
        v = str(v).strip()
        v = v.replace("\u00A0", " ")
        if re.fullmatch(r"\d+\.0+", v):
            v = v.split(".")[0]
        return v
    return s2.map(_fix)

# ---------- Rule helpers ----------
def is_termination_reason_field(field_name: str) -> bool:
    return "termination reason" in norm_colname(field_name).casefold()

def is_employment_status_field(field_name: str) -> bool:
    return "employment status" in norm_colname(field_name).casefold()

def status_contains_any(s: str, needles) -> bool:
    s = ("" if s is None else str(s)).casefold()
    return any(n in s for n in needles)

def uzio_is_active(uz_norm: str) -> bool:
    s = ("" if uz_norm is None else str(uz_norm)).casefold()
    return s == "active" or s.startswith("active")

def uzio_is_terminated(uz_norm: str) -> bool:
    s = ("" if uz_norm is None else str(uz_norm)).casefold()
    return s == "terminated" or s.startswith("terminated")

ALLOWED_TERM_REASONS = {
    "quit without notice",
    "no reason given",
    "misconduct",
    "abandoned job",
    "advancement (better job with higher pay)",
    "no-show (never started employment)",
    "performance",
    "personal",
    "scheduling conflicts (schedules don't work)",
    "attendance",
}

def normalize_reason_text(x) -> str:
    s = norm_blank(x)
    if s == "":
        return ""
    s = str(s).replace("\u00A0", " ")
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip('"').strip("'")
    return s.casefold()

def normalize_paytype_text(x) -> str:
    s = norm_blank(x)
    if s == "":
        return ""
    s = str(s).replace("\u00A0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.casefold()

def paytype_bucket(paytype_norm: str) -> str:
    s = ("" if paytype_norm is None else str(paytype_norm)).casefold()
    if "hour" in s:
        return "hourly"
    if "salary" in s or "salaried" in s:
        return "salaried"
    return ""

def is_annual_salary_field(field_name: str) -> bool:
    return "annual salary" in norm_colname(field_name).casefold()

def is_hourly_rate_field(field_name: str) -> bool:
    f = norm_colname(field_name).casefold()
    return ("hourly pay rate" in f) or ("hourly rate" in f)

# ---------- Core runner ----------
def run_comparison(file_bytes: bytes,
                   uzio_sheet: str,
                   adp_sheet: str,
                   map_sheet: str) -> dict:
    """
    Returns dict of output DataFrames + report bytes:
      {
        "summary": df,
        "field_summary_by_status": df,
        "mapping_missing_adp_col": df,
        "comparison_detail": df,
        "mismatches_only": df,
        "report_bytes": bytes
      }
    """
    xls = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")

    uzio = pd.read_excel(xls, sheet_name=uzio_sheet, dtype=object)
    adp = pd.read_excel(xls, sheet_name=adp_sheet, dtype=object)
    mapping = pd.read_excel(xls, sheet_name=map_sheet, dtype=object)

    uzio.columns = [norm_colname(c) for c in uzio.columns]
    adp.columns = [norm_colname(c) for c in adp.columns]
    mapping.columns = [norm_colname(c) for c in mapping.columns]

    if "Uzio Coloumn" not in mapping.columns or "ADP Coloumn" not in mapping.columns:
        raise ValueError("Mapping sheet must contain columns: 'Uzio Coloumn' and 'ADP Coloumn'")

    mapping["Uzio Coloumn"] = mapping["Uzio Coloumn"].map(norm_colname)
    mapping["ADP Coloumn"] = mapping["ADP Coloumn"].map(norm_colname)

    mapping_valid = mapping.dropna(subset=["Uzio Coloumn", "ADP Coloumn"]).copy()
    mapping_valid = mapping_valid[(mapping_valid["Uzio Coloumn"] != "") & (mapping_valid["ADP Coloumn"] != "")]
    mapping_valid = mapping_valid.drop_duplicates(subset=["Uzio Coloumn"], keep="first").copy()

    key_row = mapping_valid[mapping_valid["Uzio Coloumn"].str.contains("Employee ID", case=False, na=False)]
    if len(key_row) == 0:
        raise ValueError("Mapping sheet must include UZIO 'Employee ID' mapped to ADP key (usually 'Associate ID').")

    UZIO_KEY = key_row.iloc[0]["Uzio Coloumn"]
    ADP_KEY = key_row.iloc[0]["ADP Coloumn"]

    if UZIO_KEY not in uzio.columns:
        raise ValueError(f"UZIO key column '{UZIO_KEY}' not found in Uzio Data tab.")
    if ADP_KEY not in adp.columns:
        raise ValueError(f"ADP key column '{ADP_KEY}' not found in ADP Data tab.")

    uzio[UZIO_KEY] = norm_emp_key_series(uzio[UZIO_KEY])
    adp[ADP_KEY] = norm_emp_key_series(adp[ADP_KEY])

    uzio_keys = set(uzio[UZIO_KEY].dropna().astype(str).str.strip()) - {""}
    adp_keys = set(adp[ADP_KEY].dropna().astype(str).str.strip()) - {""}
    all_keys = sorted(uzio_keys.union(adp_keys))

    uzio_idx = uzio.set_index(UZIO_KEY, drop=False)
    adp_idx = adp.set_index(ADP_KEY, drop=False)

    uz_to_adp = dict(zip(mapping_valid["Uzio Coloumn"], mapping_valid["ADP Coloumn"]))
    mapped_fields = [f for f in mapping_valid["Uzio Coloumn"].tolist() if f != UZIO_KEY]

    mapping_missing_adp_col = mapping_valid[~mapping_valid["ADP Coloumn"].isin(adp.columns)].copy()

    # Employment Status column (UZIO)
    uzio_employment_status_col = None
    for c in uzio.columns:
        if norm_colname(c).casefold() == "employment status":
            uzio_employment_status_col = c
            break
    if uzio_employment_status_col is None:
        for c in uzio.columns:
            cc = norm_colname(c).casefold()
            if "employment" in cc and "status" in cc:
                uzio_employment_status_col = c
                break

    def get_uzio_employment_status(emp_id: str) -> str:
        if uzio_employment_status_col is None:
            return ""
        if emp_id in uzio_idx.index and uzio_employment_status_col in uzio_idx.columns:
            v = uzio_idx.at[emp_id, uzio_employment_status_col]
            return "" if norm_blank(v) == "" else str(v)
        return ""

    # Pay Type mapping (prefer ADP)
    paytype_row = mapping_valid[mapping_valid["Uzio Coloumn"].str.contains(r"\bpay\s*type\b", case=False, na=False)]
    UZIO_PAYTYPE_COL = paytype_row.iloc[0]["Uzio Coloumn"] if len(paytype_row) else None
    ADP_PAYTYPE_COL  = paytype_row.iloc[0]["ADP Coloumn"]  if len(paytype_row) else None

    def get_employee_pay_type(emp_id: str, adp_exists: bool, uz_exists: bool) -> str:
        if ADP_PAYTYPE_COL and adp_exists and (ADP_PAYTYPE_COL in adp_idx.columns):
            v = adp_idx.at[emp_id, ADP_PAYTYPE_COL]
            if norm_blank(v) != "":
                return str(v)
        if UZIO_PAYTYPE_COL and uz_exists and (UZIO_PAYTYPE_COL in uzio_idx.columns):
            v = uzio_idx.at[emp_id, UZIO_PAYTYPE_COL]
            if norm_blank(v) != "":
                return str(v)
        return ""

    rows = []
    for emp_id in all_keys:
        uz_exists = emp_id in uzio_idx.index
        adp_exists = emp_id in adp_idx.index

        uz_emp_status = get_uzio_employment_status(emp_id)
        emp_paytype = get_employee_pay_type(emp_id, adp_exists=adp_exists, uz_exists=uz_exists)
        emp_pay_bucket = paytype_bucket(normalize_paytype_text(emp_paytype))

        for field in mapped_fields:
            adp_col = uz_to_adp.get(field, "")

            uz_val = uzio_idx.at[emp_id, field] if uz_exists and field in uzio_idx.columns else ""
            adp_val = adp_idx.at[emp_id, adp_col] if (adp_exists and (adp_col in adp_idx.columns)) else ""

            if not adp_exists and uz_exists:
                status = "MISSING_IN_ADP"
            elif adp_exists and not uz_exists:
                status = "MISSING_IN_UZIO"
            elif adp_exists and uz_exists and (adp_col not in adp.columns):
                status = "ADP_COLUMN_MISSING"
            else:
                uz_n = norm_value(uz_val, field)
                adp_n = norm_value(adp_val, field)

                if is_employment_status_field(field) and adp_n != "":
                    adp_is_term_or_ret = status_contains_any(adp_n, ["terminated", "retired"])
                    if adp_is_term_or_ret:
                        if uz_n == "":
                            status = "UZIO_MISSING_VALUE"
                        elif uzio_is_active(uz_n):
                            status = "MISMATCH"
                        elif uzio_is_terminated(uz_n):
                            status = "OK"
                        else:
                            status = "MISMATCH"
                    else:
                        if (uz_n == adp_n) or (uz_n == "" and adp_n == ""):
                            status = "OK"
                        elif uz_n == "" and adp_n != "":
                            status = "UZIO_MISSING_VALUE"
                        elif uz_n != "" and adp_n == "":
                            status = "ADP_MISSING_VALUE"
                        else:
                            status = "MISMATCH"

                elif is_termination_reason_field(field):
                    uz_reason = normalize_reason_text(uz_val)
                    adp_reason = normalize_reason_text(adp_val)

                    if uz_reason == "other" and adp_reason in ALLOWED_TERM_REASONS:
                        status = "OK"
                    else:
                        if (uz_n == adp_n) or (uz_n == "" and adp_n == ""):
                            status = "OK"
                        elif uz_n == "" and adp_n != "":
                            status = "UZIO_MISSING_VALUE"
                        elif uz_n != "" and adp_n == "":
                            status = "ADP_MISSING_VALUE"
                        else:
                            status = "MISMATCH"
                else:
                    if (uz_n == adp_n) or (uz_n == "" and adp_n == ""):
                        status = "OK"
                    elif uz_n == "" and adp_n != "":
                        status = "UZIO_MISSING_VALUE"
                    elif uz_n != "" and adp_n == "":
                        status = "ADP_MISSING_VALUE"
                    else:
                        status = "MISMATCH"

                    # PayType exceptions overriding UZIO_MISSING_VALUE
                    if status == "UZIO_MISSING_VALUE":
                        if emp_pay_bucket == "hourly" and is_annual_salary_field(field):
                            status = "OK"
                        elif emp_pay_bucket == "salaried" and is_hourly_rate_field(field):
                            status = "OK"

            rows.append({
                "Employee ID": emp_id,
                "Employment Status": uz_emp_status,
                "Pay Type": emp_paytype,
                "Field": field,
                "UZIO_Value": uz_val,
                "ADP_Value": adp_val,
                "ADP_SourceOfTruth_Status": status
            })

    comparison_detail = pd.DataFrame(rows)
    comparison_detail = comparison_detail[[
        "Employee ID", "Employment Status", "Pay Type",
        "Field", "UZIO_Value", "ADP_Value", "ADP_SourceOfTruth_Status"
    ]]

    mismatches_only = comparison_detail[comparison_detail["ADP_SourceOfTruth_Status"] != "OK"].copy()

    # Field Summary By Status
    cols_needed = [
        "OK",
        "MISMATCH",
        "UZIO_MISSING_VALUE",
        "ADP_MISSING_VALUE",
        "MISSING_IN_UZIO",
        "MISSING_IN_ADP",
        "ADP_COLUMN_MISSING",
    ]

    pivot = comparison_detail.pivot_table(
        index="Field",
        columns="ADP_SourceOfTruth_Status",
        values="Employee ID",
        aggfunc="count",
        fill_value=0
    )

    for c in cols_needed:
        if c not in pivot.columns:
            pivot[c] = 0

    pivot["Total"] = pivot.sum(axis=1)
    pivot["OK"] = pivot["OK"].astype(int)
    pivot["NOT_OK"] = (pivot["Total"] - pivot["OK"]).astype(int)

    field_summary_by_status = pivot.reset_index()[[
        "Field",
        "Total",
        "OK",
        "NOT_OK",
        "MISMATCH",
        "UZIO_MISSING_VALUE",
        "ADP_MISSING_VALUE",
        "MISSING_IN_UZIO",
        "MISSING_IN_ADP",
        "ADP_COLUMN_MISSING",
    ]]

    summary = pd.DataFrame({
        "Metric": [
            "Employees in UZIO sheet",
            "Employees in ADP sheet",
            "Employees present in both",
            "Employees missing in ADP (UZIO only)",
            "Employees missing in UZIO (ADP only)",
            "Mapped fields total (from mapping sheet)",
            "Mapped fields with ADP column missing",
            "Total comparison rows (employees x mapped fields)",
            "Total NOT OK rows"
        ],
        "Value": [
            len(uzio_keys),
            len(adp_keys),
            len(uzio_keys.intersection(adp_keys)),
            len(uzio_keys - adp_keys),
            len(adp_keys - uzio_keys),
            len(mapped_fields),
            mapping_missing_adp_col.shape[0],
            comparison_detail.shape[0],
            mismatches_only.shape[0]
        ]
    })

    # Build Excel report in-memory
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        field_summary_by_status.to_excel(writer, sheet_name="Field_Summary_By_Status", index=False)
        mapping_missing_adp_col.to_excel(writer, sheet_name="Mapping_ADP_Col_Missing", index=False)
        comparison_detail.to_excel(writer, sheet_name="Comparison_Detail_AllFields", index=False)
        mismatches_only.to_excel(writer, sheet_name="Mismatches_Only", index=False)

    return {
        "summary": summary,
        "field_summary_by_status": field_summary_by_status,
        "mapping_missing_adp_col": mapping_missing_adp_col,
        "comparison_detail": comparison_detail,
        "mismatches_only": mismatches_only,
        "report_bytes": out.getvalue(),
    }


# ======================
# Streamlit UI
# ======================
st.set_page_config(page_title="UZIO vs ADP Comparison", layout="wide")
st.title("UZIO vs ADP Comparison (ADP = Source of Truth)")
st.caption("Upload the Excel workbook with sheets: Uzio Data, ADP Data, Mapping Sheet. Then download the generated report.")

with st.sidebar:
    st.header("Inputs")
    uzio_sheet = st.text_input("UZIO sheet name", value=UZIO_SHEET_DEFAULT)
    adp_sheet = st.text_input("ADP sheet name", value=ADP_SHEET_DEFAULT)
    map_sheet = st.text_input("Mapping sheet name", value=MAP_SHEET_DEFAULT)
    st.divider()
    st.write("Output file name:")
    st.code(OUTPUT_FILENAME)

uploaded_file = st.file_uploader("Upload Excel workbook (.xlsx)", type=["xlsx"])

run = st.button("Run Comparison", type="primary", disabled=(uploaded_file is None))

if run:
    try:
        file_bytes = uploaded_file.getvalue()
        with st.spinner("Running comparison..."):
            result = run_comparison(
                file_bytes=file_bytes,
                uzio_sheet=uzio_sheet,
                adp_sheet=adp_sheet,
                map_sheet=map_sheet,
            )

        st.success("Report generated successfully.")

        # Quick KPIs
        col1, col2 = st.columns([1, 2], vertical_alignment="top")
        with col1:
            st.subheader("Summary")
            st.dataframe(result["summary"], use_container_width=True, hide_index=True)

            st.download_button(
                label="Download Report (.xlsx)",
                data=result["report_bytes"],
                file_name=OUTPUT_FILENAME,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )

        with col2:
            st.subheader("Field Summary By Status (Top 30 by NOT_OK)")
            fs = result["field_summary_by_status"].copy()
            fs = fs.sort_values("NOT_OK", ascending=False).head(30)
            st.dataframe(fs, use_container_width=True, hide_index=True)

            st.subheader("Mismatches Only (Preview)")
            st.dataframe(result["mismatches_only"].head(200), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Failed: {e}")
        st.stop()
