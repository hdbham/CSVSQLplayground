import streamlit as st
import duckdb
import pandas as pd
import os
import json
from openai import OpenAI
from streamlit_ace import st_ace
from session_manager_autosave import (
    auto_save_if_enabled,
    load_named_workspace,
    save_named_workspace,
    delete_named_workspace
)

client = OpenAI(api_key=st.secrets["openai_api_key"])

st.set_page_config(page_title="CSV SQL App", layout="wide")

# --- Workspace Setup ---
workspace_root = "workspaces"
autosave_root = "autosaves"
os.makedirs(workspace_root, exist_ok=True)
os.makedirs(autosave_root, exist_ok=True)

# Workspace Dropdown
st.sidebar.title("🧭 Workspace Manager")
named_workspaces = [f for f in os.listdir(workspace_root) if os.path.isdir(os.path.join(workspace_root, f))]
named_workspace = st.sidebar.selectbox("📂 Load Workspace", named_workspaces or ["(none)"])

# Load workspace if changed
if st.session_state.get("last_loaded_workspace") != named_workspace:
    load_named_workspace(named_workspace)
    st.session_state.last_loaded_workspace = named_workspace
    st.session_state.sql_editor_key = f"sql_{named_workspace}"
    st.rerun()

# Save / Reset Workspace
with st.sidebar.expander("📦 Save/Reset/Delete Workspace"):
    new_name = st.text_input("New Workspace name", key="save_ws_name")
    if st.button("💾 Save Workspace") and new_name:
        save_named_workspace(new_name)
        st.sidebar.success(f"Saved '{new_name}'")

    if st.button("🧹 Reset Workspace"):
        st.session_state.clear()
        st.rerun()

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if st.session_state.confirm_delete:
        st.warning(f"⚠️ This will permanently delete workspace: `{named_workspace}`")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("✅ Confirm Delete"):
                delete_named_workspace(named_workspace)
        with col2:
            if st.button("❌ Cancel"):
                st.session_state.confirm_delete = False
    else:
        if st.button("🗑️ Delete Workspace"):
            st.session_state.confirm_delete = True


# Paths
active_workspace = os.path.join(workspace_root, named_workspace)
SAVE_DIR = os.path.join(active_workspace, "tables")
QUERY_JSON = os.path.join(active_workspace, "last_query.json")
os.makedirs(SAVE_DIR, exist_ok=True)

# DuckDB Init
if "con" not in st.session_state:
    st.session_state.con = duckdb.connect()

# Load CSV Tables
for file in os.listdir(SAVE_DIR):
    if file.endswith(".csv"):
        name = file.replace(".csv", "")
        path = os.path.join(SAVE_DIR, file)
        try:
            st.session_state.con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_csv_auto('{path}')")
        except Exception as e:
            st.warning(f"Could not load {name}: {e}")

# File Upload
uploaded = st.file_uploader("Upload CSV", type="csv")
if uploaded:
    try:
        df = pd.read_csv(uploaded)
    except:
        uploaded.seek(0)
        df = pd.read_csv(uploaded, encoding="latin1", errors="replace")
    df = df.applymap(lambda x: x.encode("utf-8", "replace").decode("utf-8") if isinstance(x, str) else x)
    st.dataframe(df.head())
    table_name = st.text_input("Save as table:", value="my_table")
    if st.button("📅 Register Table"):
        path = os.path.join(SAVE_DIR, f"{table_name}.csv")
        df.to_csv(path, index=False)
        st.session_state.con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{path}')")
        st.success(f"Saved: {table_name}")


# --- Table Management ---
st.markdown("### 📂 Registered DuckDB Tables")
try:
    table_names = st.session_state.con.execute("SHOW TABLES").fetchdf()["name"].tolist()
    for table in table_names:
        with st.expander(f"🧃 Table: `{table}`"):
            col1, col2 = st.columns([4, 1])
            with col1:
                try:
                    preview = st.session_state.con.execute(f"SELECT * FROM {table} LIMIT 5").fetchdf()
                    st.dataframe(preview)
                except Exception as e:
                    st.warning(f"Preview failed: {e}")

                new_csv = st.file_uploader(f"Replace `{table}`", type="csv", key=f"replace_{table}")
                if new_csv:
                    try:
                        df_new = pd.read_csv(new_csv)
                        path = os.path.join(SAVE_DIR, f"{table}.csv")
                        df_new.to_csv(path, index=False)
                        st.session_state.con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{path}')")
                        st.success(f"🔁 Replaced: {table}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Replace failed: {e}")

            with col2:
                if st.button("✏️ Rename", key=f"rename_btn_{table}"):
                    new_name = st.text_input("New name", key=f"rename_input_{table}")
                    if new_name:
                        os.rename(os.path.join(SAVE_DIR, f"{table}.csv"), os.path.join(SAVE_DIR, f"{new_name}.csv"))
                        st.session_state.con.execute(f"ALTER TABLE {table} RENAME TO {new_name}")
                        st.success(f"Renamed to {new_name}")
                        st.rerun()

                if st.button("🗑️ Delete", key=f"del_{table}"):
                    try:
                        st.session_state.con.execute(f"DROP TABLE IF EXISTS {table}")
                        os.remove(os.path.join(SAVE_DIR, f"{table}.csv"))
                        st.success(f"Deleted: {table}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")
except Exception as e:
    st.error(f"Failed to fetch tables: {e}")

# --- Natural Language SQL ---
st.markdown("### 🧠 Natural Language to SQL")
if table_names:
    selected_tables = st.multiselect("Choose tables", table_names)
    qualified_columns = []
    for t in selected_tables:
        cols = st.session_state.con.execute(f"PRAGMA table_info({t})").fetchdf()["name"].tolist()
        qualified_columns += [f"{t}.{col}" for col in cols]
    st.code(", ".join(qualified_columns))
    nl_prompt = st.text_input("Ask a question:")

    if st.button("🪄 Generate SQL") and nl_prompt and qualified_columns:
        with st.spinner("Calling GPT..."):
            try:
                sys_msg = "You are a duckdb professional helpful assistant. Always return SQL using the DuckDB dialect. Do not use markdown or code blocks.Begin your response with a line starting: -- Description: Wrap any column names that contain hyphens or special characters in DOUBLE ticks (""). this is valid  my_table.'this-is-a-column' wrapping the table name is not 'my_table.this-is-a-col'; Only return valid DuckDB SQL — no explanations or commentary."
                user_msg = f"Only using columns: {qualified_columns}. Question: {nl_prompt}"
                res = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
                )
                txt = res.choices[0].message.content.strip()
                
                
                sql_clean = txt
            
                # Save to session
                st.session_state["generated_sql"] = sql_clean
                st.session_state["generated_description"] = desc
                st.session_state["description_banner"] = bool(desc)
                
                st.rerun()
            except Exception as e:
                st.error(f"GPT error: {e}")

# Description banner
if st.session_state.get("description_banner"):
    st.success("📝 Description: " + st.session_state.get("generated_description", ""))
    st.session_state.description_banner = False

# SQL Editor (Ace)
st.markdown("### ✍️ SQL Editor")
editor_value = st.session_state.get("generated_sql", "")
sql_code = st_ace(
    value=editor_value,
    language="sql",
    theme="dracula",
    key=st.session_state.get("sql_editor_key", "sql_editor"),
    height=300,
    show_gutter=True,
    auto_update=True,
    wrap=True,
)

# Run Query
if st.button("🏃 Run Query"):
    try:
        result = st.session_state.con.execute(sql_code).fetchdf()
        st.dataframe(result)
        csv = result.to_csv(index=False)
        st.download_button("⬇️ Download", data=csv, file_name="result.csv", mime="text/csv")
        st.session_state["last_result"] = result
        st.session_state["last_query"] = sql_code
        auto_save_if_enabled()
    except Exception as e:
        st.error(f"❌ Query failed: {e}")

# Footer
st.markdown("---\n📚 [Kaggle: Super Store dataset](https://www.kaggle.com/datasets/itssuru/super-store)")
