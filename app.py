# app.py
import io
import re
from datetime import datetime, date

import numpy as np
import pandas as pd
import streamlit as st

# =========================================================
# Data_Audit_Tool (Streamlit)
# - User uploads Excel workbook (.xlsx)
# - No table previews on UI
# - No sidebar / left panel
# - Generates Excel report and provides download button
#
# OUTPUT TABS:
#   - Summary
#   - Field_Summary_By_Status   (Columns G,H,I removed)
#   - Comparison_Detail_AllFields
#
# Removed sheets from output report:
#   - Mismatches_Only
#   - Mapping_ADP_Col_Missing
# =========================================================

APP_TITLE = "Census ADP and Uzio Data Review Tool"
# OUTPUT_FILENAME will be generated dynamically

UZIO_SHEET = "Uzio Data"
ADP_SHEET = "ADP Data"
MAP_SHEET = "Mapping Sheet"

# ---------- UI: Hide sidebar + Streamlit chrome ----------
st.set_page_config(page_title=APP_TITLE, layout="centered", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
      [data-testid="stSidebar"] { display: none !important; }
      [data-testid="collapsedControl"] { display: none !important; }
      header { display: none !important; }
      footer { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True
)

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
    if x is None:
        return ""
    if isinstance(x, float) and np.isnan(x):
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

def norm_ssn_9digits(x):
    # ONLY CHANGE: SSN compare as 9 digits (pad leading zeros if Excel dropped them)
    d = digits_only(x)
    if d == "":
        return ""
    if len(d) < 9:
        return d.zfill(9)
    if len(d) > 9:
        return d[-9:]
    return d

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
DATE_KEYWORDS = {"date", "dob", "birth", "doh", "hire"}
SSN_KEYWORDS = {"ssn", "tax id"}
ZIP_KEYWORDS = {"zip", "zipcode", "postal"}
GENDER_KEYWORDS = {"gender"}
PHONE_KEYWORDS = {"phone"}
MIDDLE_INITIAL_KEYWORDS = {"middle initial"}  # ONLY CHANGE: treat as initial vs full middle name
JOB_TITLE_KEYWORDS = {"job title", "position title"}
VETERAN_KEYWORDS = {"veteran"}

JOB_TITLE_MAPPINGS = {
    "admin": "administrator",
    "management": "manager",
    "dsp owner": "owner"
}

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

def norm_middle_initial(x):
    # ONLY CHANGE: compare middle initial to the first letter of ADP middle name
    x = norm_blank(x)
    if x == "":
        return ""
    s = str(x).strip()
    m = re.search(r"[A-Za-z]", s)
    return (m.group(0).casefold() if m else "")

def norm_job_title(x):
    x = norm_blank(x)
    if x == "":
        return ""
    s = str(x).replace("\u00A0", " ")
    s = re.sub(r"\s+", " ", s).strip().casefold()
    return JOB_TITLE_MAPPINGS.get(s, s)

def norm_veteran_status(x):
    x = norm_blank(x)
    if x == "":
        return ""
    s = str(x).replace("\u00A0", " ")
    s = re.sub(r"\s+", " ", s).strip().casefold()
    
    # Normalize phrases
    # "i am not a protected veteran" -> "not a protected veteran"
    if "not a protected veteran" in s:
        return "not a protected veteran"
    
    # "identify as a protected veteran", "protected veteran" (without 'not') -> "protected veteran"
    if "protected veteran" in s and "not" not in s:
        return "protected veteran"
        
    return s

def norm_value(x, field_name: str):
    f = norm_colname(field_name).lower()
    x = norm_blank(x)
    if x == "":
        return ""

    if any(k in f for k in MIDDLE_INITIAL_KEYWORDS):  # ONLY CHANGE
        return norm_middle_initial(x)

    if any(k in f for k in GENDER_KEYWORDS):
        return norm_gender(x)

    if any(k in f for k in VETERAN_KEYWORDS):
        return norm_veteran_status(x)

    if any(k in f for k in JOB_TITLE_KEYWORDS):
        return norm_job_title(x)

    if any(k in f for k in SSN_KEYWORDS):  # ONLY CHANGE: use 9-digit padded SSN
        return norm_ssn_9digits(x)

    if any(k in f for k in PHONE_KEYWORDS):
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

# ---------- Guardrail: prevent ACTIVE/TERMINATED/RETIRED values leaking into non-status fields ----------
EMP_STATUS_TOKENS = {"active", "terminated", "retired"}

def field_allows_emp_status_value(field_name: str) -> bool:
    f = norm_colname(field_name).casefold()
    return (f == "status") or ("employment status" in f)

def cleanse_uzio_value_for_field(field_name: str, uz_val):
    if norm_blank(uz_val) == "":
        return uz_val
    s = str(uz_val).strip().casefold()
    if (s in EMP_STATUS_TOKENS) and (not field_allows_emp_status_value(field_name)):
        return ""
    return uz_val

# ---------- Pay Type equivalence (UZIO Salaried == ADP Salary) ----------
def is_pay_type_field(field_name: str) -> bool:
    f = norm_colname(field_name).casefold()
    return f == "pay type" or ("pay type" in f)

def normalize_paytype_for_compare(x) -> str:
    s = normalize_paytype_text(x)
    if s in {"salary", "salaried"}:
        return "salaried"
    if s in {"hourly", "hour"}:
        return "hourly"
    return s

# ---------- Core compare ----------
def run_comparison(file_bytes: bytes) -> bytes:
    xls = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")

    uzio = pd.read_excel(xls, sheet_name=UZIO_SHEET, dtype=object)
    adp = pd.read_excel(xls, sheet_name=ADP_SHEET, dtype=object)
    mapping = pd.read_excel(xls, sheet_name=MAP_SHEET, dtype=object)

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

    uzio[UZIO_KEY] = norm_emp_key_series(uzio[UZIO_KEY])
    adp[ADP_KEY] = norm_emp_key_series(adp[ADP_KEY])

    # NEW: Deduplicate ADP Data based on user logic
    def deduplicate_adp(df: pd.DataFrame, key_col: str) -> pd.DataFrame:
        # Identify special columns (normalized)
        col_map = {c: c.lower() for c in df.columns}
        
        status_col = next((c for c, l in col_map.items() if "position status" in l), None)
        term_date_col = next((c for c, l in col_map.items() if "termination date" in l), None)
        start_date_col = next((c for c, l in col_map.items() if "position start date" in l), None)
        loc_desc_col = next((c for c, l in col_map.items() if "work location description" in l), None)
        license_id_col = next((c for c, l in col_map.items() if "license/certification id" in l), None)
        
        # If we can't find status col, fallback to basic drop_duplicates
        if not status_col:
            return df.drop_duplicates(subset=[key_col], keep="first")
            
        def pick_best(group):
            if len(group) <= 1:
                return group.iloc[[0]]
            
            # Helper to parse date for sorting
            def get_date_val(row, col):
                if not col or pd.isna(row[col]):
                    return pd.Timestamp.min
                val = str(row[col]).strip()
                if not val:
                    return pd.Timestamp.min
                try:
                    return pd.to_datetime(val)
                except:
                    return pd.Timestamp.min

            if isinstance(group, pd.Series):
                 return group.to_frame().T

            group = group.copy()
            group['__norm_status'] = group[status_col].astype(str).str.lower().str.strip()
            
            # Add license check
            if license_id_col:
                group['__has_license'] = group[license_id_col].apply(lambda x: 1 if norm_blank(x) != "" else 0)
            else:
                group['__has_license'] = 0

            actives = group[group['__norm_status'] == 'active']
            terms = group[group['__norm_status'] == 'terminated']
            others = group[(group['__norm_status'] != 'active') & (group['__norm_status'] != 'terminated')]
            
            # Logic 1: If Actives exist, prioritize them
            if not actives.empty:
                # Rule: select row where Work Location Description is not blank
                actives['__sort_date'] = actives.apply(lambda r: get_date_val(r, start_date_col), axis=1)

                if loc_desc_col:
                    actives['__has_loc'] = actives[loc_desc_col].apply(lambda x: 1 if norm_blank(x) != "" else 0)
                    best_active = actives.sort_values(by=['__has_loc', '__has_license', '__sort_date'], ascending=[False, False, False]).iloc[[0]]
                else:
                    best_active = actives.sort_values(by=['__has_license', '__sort_date'], ascending=[False, False]).iloc[[0]]
                
                return best_active

            # Logic 2: Terminated
            if not terms.empty:
                # Rule: If term dates are different, select latest.
                # Rule: If one blank and one value -> select latest Position Start Date
                
                # Check for blank term dates
                terms['__sort_date'] = pd.Timestamp.min
                
                # Determine which date to sort by mainly
                use_start_date = False
                if term_date_col:
                    terms['__term_dt_val'] = terms[term_date_col].apply(norm_blank)
                    has_blank = (terms['__term_dt_val'] == "").any()
                    has_val = (terms['__term_dt_val'] != "").any()
                    
                    if has_blank and has_val:
                        use_start_date = True
                else:
                    use_start_date = True

                if use_start_date:
                     terms['__sort_date'] = terms.apply(lambda r: get_date_val(r, start_date_col), axis=1)
                elif term_date_col:
                     terms['__sort_date'] = terms.apply(lambda r: get_date_val(r, term_date_col), axis=1)
                
                # Add License priority to Terminated as well (implicitly safe)
                return terms.sort_values(by=['__has_license', '__sort_date'], ascending=[False, False]).iloc[[0]]

            # Fallback (Others, e.g. Leave)
            if not others.empty:
                 others['__sort_date'] = others.apply(lambda r: get_date_val(r, start_date_col), axis=1)
                 return others.sort_values(by=['__has_license', '__sort_date'], ascending=[False, False]).iloc[[0]]

            return group.iloc[[0]]

        # Apply grouping
        deduped = df.groupby(key_col, group_keys=False).apply(pick_best)
        
        # Cleanup temp columns if they leaked (apply usually returns pure subset but safe to drop)
        cols_to_drop = [c for c in ['__norm_status', '__has_loc', '__sort_date', '__term_dt_val', '__has_license'] if c in deduped.columns]
        if cols_to_drop:
            deduped = deduped.drop(columns=cols_to_drop)
            
        return deduped

    # Apply the new deduplication
    adp = deduplicate_adp(adp, ADP_KEY)
    
    # Old simple drop (keep unique) - technically redundant but safe as backup for Uzio
    uzio = uzio.drop_duplicates(subset=[UZIO_KEY], keep="first").copy()
    # adp = adp.drop_duplicates(subset=[ADP_KEY], keep="first").copy() # Replaced by above

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

    # ---------- Build FULL comparison ----------
    rows = []
    for emp_id in all_keys:
        uz_exists = emp_id in uzio_idx.index
        adp_exists = emp_id in adp_idx.index

        uz_emp_status = get_uzio_employment_status(emp_id)
        emp_paytype = get_employee_pay_type(emp_id, adp_exists=adp_exists, uz_exists=uz_exists)
        emp_pay_bucket = paytype_bucket(normalize_paytype_text(emp_paytype))

        for field in mapped_fields:
            adp_col = uz_to_adp.get(field, "")
            
            # Check if columns exist in the usage data
            uz_col_missing = (field not in uzio.columns)
            adp_col_missing = (adp_col not in adp.columns)

            uz_val_raw = uzio_idx.at[emp_id, field] if (uz_exists and not uz_col_missing) else ""
            uz_val = cleanse_uzio_value_for_field(field, uz_val_raw)

            adp_val = adp_idx.at[emp_id, adp_col] if (adp_exists and not adp_col_missing) else ""

            if not adp_exists and uz_exists:
                status = "Employee ID Not Found in ADP"
            elif adp_exists and not uz_exists:
                status = "Employee ID Not Found in Uzio"
            elif adp_exists and uz_exists and adp_col_missing:
                status = "Column Missing in ADP Sheet"
            elif adp_exists and uz_exists and uz_col_missing:
                status = "Column Missing in Uzio Sheet"
            else:
                if is_pay_type_field(field):
                    uz_pt = normalize_paytype_for_compare(uz_val)
                    adp_pt = normalize_paytype_for_compare(adp_val)

                    if (uz_pt == adp_pt) or (uz_pt == "" and adp_pt == ""):
                        status = "Data Match"
                    elif uz_pt == "" and adp_pt != "":
                        status = "Value missing in Uzio (ADP has value)"
                    elif uz_pt != "" and adp_pt == "":
                        status = "Value missing in ADP (Uzio has value)"
                    else:
                        status = "Data Mismatch"
                else:
                    uz_n = norm_value(uz_val, field)
                    adp_n = norm_value(adp_val, field)

                    if is_employment_status_field(field) and adp_n != "":
                        adp_is_term_or_ret = status_contains_any(adp_n, ["terminated", "retired"])
                        
                        # Special Case: UZIO Active == ADP Leave -> Match
                        is_active_leave = (uzio_is_active(uz_n) and "leave" in adp_n)
                        
                        # Special Case: UZIO Terminated == ADP Deceased -> Match
                        is_term_deceased = (uzio_is_terminated(uz_n) and "deceased" in adp_n)

                        if is_active_leave or is_term_deceased:
                            status = "Data Match"
                        elif (uz_n == adp_n) or (uz_n == "" and adp_n == ""):
                             status = "Data Match"
                        elif uzio_is_terminated(uz_n) and adp_is_term_or_ret:
                             # Both terminated/retired but strings diff -> Match
                             status = "Data Match"
                        else:
                            # MISMATCH / MISSING LOGIC per User Request
                            # 1. Active in Uzio
                            if uzio_is_active(uz_n):
                                status = "Active in Uzio"
                            # 2. Terminated in Uzio
                            elif uzio_is_terminated(uz_n):
                                status = "Terminated in Uzio"
                            # 3. Active in ADP (Uzio Blank)
                            elif uz_n == "" and not adp_is_term_or_ret:
                                status = "Active in ADP"
                            # 4. Terminated in ADP (Uzio Blank)
                            elif uz_n == "" and adp_is_term_or_ret:
                                status = "Terminated in ADP"
                            # Fallback for other cases
                            elif uz_n == "" and adp_n != "":
                                status = f"Value missing in Uzio (ADP: {adp_val})"  # Generic fallback
                            elif uz_n != "" and adp_n == "":
                                status = "Value missing in ADP (Uzio has value)"
                            else:
                                status = "Data Mismatch"

                    elif is_termination_reason_field(field):
                        uz_reason = normalize_reason_text(uz_val)
                        adp_reason = normalize_reason_text(adp_val)

                        if uz_reason == "other" and adp_reason in ALLOWED_TERM_REASONS:
                            status = "Data Match"
                        else:
                            if (uz_n == adp_n) or (uz_n == "" and adp_n == ""):
                                status = "Data Match"
                            elif uz_n == "" and adp_n != "":
                                status = "Value missing in Uzio (ADP has value)"
                            elif uz_n != "" and adp_n == "":
                                status = "Value missing in ADP (Uzio has value)"
                            else:
                                status = "Data Mismatch"
                    else:
                        if (uz_n == adp_n) or (uz_n == "" and adp_n == ""):
                            status = "Data Match"
                        elif uz_n == "" and adp_n != "":
                            status = "Value missing in Uzio (ADP has value)"
                        elif uz_n != "" and adp_n == "":
                            status = "Value missing in ADP (Uzio has value)"
                        else:
                            status = "Data Mismatch"

                        if status == "Value missing in Uzio (ADP has value)":
                            if emp_pay_bucket == "hourly" and is_annual_salary_field(field):
                                status = "Data Match"
                            elif emp_pay_bucket == "salaried" and is_hourly_rate_field(field):
                                status = "Data Match"

            rows.append({
                "Employee ID": emp_id,
                "Employment Status": uz_emp_status,
                "Pay Type": emp_paytype,
                "Field": field,
                "UZIO_Value": uz_val,
                "ADP_Value": adp_val,
                "ADP_SourceOfTruth_Status": status
            })

    comparison_detail = pd.DataFrame(rows)[[
        "Employee ID", "Employment Status", "Pay Type",
        "Field", "UZIO_Value", "ADP_Value", "ADP_SourceOfTruth_Status"
    ]]

    mismatches_only = comparison_detail[comparison_detail["ADP_SourceOfTruth_Status"] != "Data Match"].copy()

    # ---------- Field Summary By Status ----------
    cols_needed = [
        "Data Match",
        "Data Mismatch",
        "Value missing in Uzio (ADP has value)",
        "Value missing in ADP (Uzio has value)",
        "Employee ID Not Found in Uzio",
        "Employee ID Not Found in ADP",
        "Column Missing in ADP Sheet",
        "Column Missing in Uzio Sheet",
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
    pivot["Data Match"] = pivot["Data Match"].astype(int)
    # Removing NOT_OK aggregate column as per user request to avoid confusion with Data Mismatch

    field_summary_by_status = pivot.reset_index()[[
        "Field",
        "Total",
        "Data Match",
        "Data Mismatch",
        "Value missing in Uzio (ADP has value)",
        "Value missing in ADP (Uzio has value)",
        "Employee ID Not Found in Uzio",
        "Employee ID Not Found in ADP",
        "Column Missing in ADP Sheet",
        "Column Missing in Uzio Sheet",
    ]]

    # Remove columns H,I from Field_Summary_By_Status (keep Value missing in ADP)
    # H=Employee ID Not Found in Uzio, I=Employee ID Not Found in ADP
    # field_summary_by_status = field_summary_by_status.drop(
    #     columns=["Employee ID Not Found in Uzio", "Employee ID Not Found in ADP"],
    #     errors="ignore"
    # )

    # ---------- Summary metrics ----------
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

    # ---------- Export report ----------
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        field_summary_by_status.to_excel(writer, sheet_name="Field_Summary_By_Status", index=False)
        comparison_detail.to_excel(writer, sheet_name="Comparison_Detail_AllFields", index=False)
        # Do NOT write Mapping_ADP_Col_Missing and Mismatches_Only

    return out.getvalue()

# ---------- Minimal UI ----------
st.title(APP_TITLE)
st.write("Upload the Excel workbook (.xlsx). The tool will generate the audit report and provide a download button.")

uploaded_file = st.file_uploader("Upload Excel workbook", type=["xlsx"])
run_btn = st.button("Run Audit", type="primary", disabled=(uploaded_file is None))

if run_btn:
    try:
        with st.spinner("Running audit..."):
            report_bytes = run_comparison(uploaded_file.getvalue())

        st.success("Report generated.")
        
        today_str = date.today().isoformat()  # YYYY-MM-DD
        out_filename = f"Client_Name_ADP_Census_Data_Audit_{today_str}.xlsx"
        
        st.download_button(
            label="Download Report (.xlsx)",
            data=report_bytes,
            file_name=out_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    except Exception as e:
        st.error(f"Failed: {e}")
