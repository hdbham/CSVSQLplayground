import os
import shutil
import json
import duckdb
import pandas as pd
import streamlit as st

AUTOSAVE_DIR = "autosaves"
AUTOSAVE_LIMIT = 4
SESSION_DB_PATH = "session_temp.duckdb"
WORKSPACE_ROOT = "workspaces"

os.makedirs(AUTOSAVE_DIR, exist_ok=True)
os.makedirs(WORKSPACE_ROOT, exist_ok=True)

def delete_named_workspace(name):
    path = os.path.join(WORKSPACE_ROOT, name)
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
            st.success(f"🗑️ Workspace '{name}' deleted.")
            if st.session_state.get("last_loaded_workspace") == name:
                st.session_state.pop("last_loaded_workspace", None)
                st.session_state.pop("sql_editor_key", None)
                st.rerun()
        except Exception as e:
            st.error(f"❌ Failed to delete workspace: {e}")
    else:
        st.warning(f"⚠️ Workspace '{name}' does not exist.")

def rotate_recent_sessions():
    for i in range(AUTOSAVE_LIMIT, 0, -1):
        src = f"{AUTOSAVE_DIR}/workspace_{i - 1}" if i > 1 else None
        dst = f"{AUTOSAVE_DIR}/workspace_{i}"
        if src and os.path.exists(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.move(src, dst)


def save_autosession(tables):
    rotate_recent_sessions()
    save_path = f"{AUTOSAVE_DIR}/workspace_1"
    os.makedirs(save_path, exist_ok=True)
    for table_name in tables:
        try:
            df = st.session_state.con.execute(f"SELECT * FROM {table_name}").fetchdf()
            df.to_csv(f"{save_path}/{table_name}.csv", index=False)
        except Exception as e:
            st.warning(f"Could not save table {table_name}: {e}")


def auto_save_if_enabled():
    try:
        if st.session_state.get("con"):
            table_df = st.session_state.con.execute("SHOW TABLES").fetchdf()
            table_names = table_df['name'].tolist()
            save_autosession(table_names)
    except Exception as e:
        st.warning(f"⚠️ Auto-save skipped: {e}")


def save_named_workspace(name):
    base_path = os.path.join(WORKSPACE_ROOT, name)
    table_dir = os.path.join(base_path, "tables")
    meta_path = os.path.join(base_path, "meta.json")

    os.makedirs(table_dir, exist_ok=True)

    if "con" not in st.session_state:
        st.warning("No database connection found.")
        return

    try:
        table_df = st.session_state.con.execute("SHOW TABLES").fetchdf()
        table_names = table_df["name"].tolist()
    except Exception as e:
        st.error(f"Could not list tables: {e}")
        return

    metadata = {
        "tables": {},
        "last_query": st.session_state.get("last_query", ""),
        "last_description": st.session_state.get("generated_description", "")
    }

    for t in table_names:
        try:
            df = st.session_state.con.execute(f"SELECT * FROM {t}").fetchdf()
            fname = f"{t}.csv"
            df.to_csv(os.path.join(table_dir, fname), index=False)
            metadata["tables"][t] = {
                "source": fname,
                "custom_name": t,
                "description": f"Saved from workspace '{name}'"
            }
        except Exception as e:
            st.warning(f"❌ Failed to save table {t}: {e}")

    try:
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        st.session_state["workspace_dir"] = base_path
        st.success(f"✅ Workspace '{name}' saved!")
    except Exception as e:
        st.error(f"❌ Failed to write metadata: {e}")


def load_named_workspace(name):
    path = os.path.join(WORKSPACE_ROOT, name)
    table_dir = os.path.join(path, "tables")
    meta_path = os.path.join(path, "meta.json")

    if not os.path.exists(meta_path):
        st.error("Workspace metadata not found.")
        return

    # Clear current tables
    try:
        current_tables = st.session_state.con.execute("SHOW TABLES").fetchdf()["name"].tolist()
        for t in current_tables:
            st.session_state.con.execute(f"DROP TABLE IF EXISTS {t}")
    except Exception as e:
        st.warning(f"Failed to reset tables: {e}")

    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
        for table, info in meta["tables"].items():
            csv_path = os.path.join(table_dir, info["source"])
            if not os.path.exists(csv_path):
                st.warning(f"Missing table file: {csv_path}")
                continue
            st.session_state.con.execute(
                f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{csv_path}')"
            )

        # Load previous query state
        st.session_state["generated_sql"] = meta.get("last_query", "")
        st.session_state["last_query"] = meta.get("last_query", "")
        st.session_state["generated_description"] = meta.get("last_description", "")
        st.session_state["description_banner"] = bool(meta.get("last_description", ""))
        
        st.session_state.generated_sql = meta.get("last_query", "")
        st.session_state.generated_description = meta.get("last_description", "")

        st.session_state["workspace_dir"] = path
        st.success(f"✅ Workspace '{name}' loaded.")
    except Exception as e:
        st.error(f"❌ Failed to load workspace '{name}': {e}")
