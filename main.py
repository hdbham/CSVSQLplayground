import streamlit as st
import duckdb
import pandas as pd
import os

SAVE_DIR = "saved_tables"
os.makedirs(SAVE_DIR, exist_ok=True)

st.set_page_config(page_title="CSV SQL App", layout="wide")
st.title("📊 CSV SQL Playground")

# Set up DuckDB connection
if "con" not in st.session_state:
    st.session_state.con = duckdb.connect()

# Load saved tables into DuckDB on startup
for file in os.listdir(SAVE_DIR):
    if file.endswith(".csv"):
        table = file.replace(".csv", "")
        path = os.path.join(SAVE_DIR, file)
        try:
            st.session_state.con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{path}')")
        except Exception as e:
            st.warning(f"Could not load {file}: {e}")

# Upload CSV
uploaded_file = st.file_uploader("Upload a CSV file", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file, sep=None, engine="python")
    st.dataframe(df.head())

table_name = st.text_input("Save table as (no spaces):", value="my_table")

if st.button("📅 Register Table"):
    save_path = os.path.join(SAVE_DIR, f"{table_name}.csv")
    try:
        df.to_csv(save_path, index=False)
        st.session_state.con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{save_path}')")
        st.success(f"Table saved: {table_name}")
    except Exception as e:
        st.error(f"Error: {e}")

# Show list of saved tables
st.markdown("### 📂 Registered DuckDB Tables")

try:
    table_names = st.session_state.con.execute("SHOW TABLES").fetchdf()['name'].tolist()

    if not table_names:
        st.info("No tables registered yet.")
    else:
        for table in table_names:
            st.subheader(f"🧃 {table}")
            try:
                preview_df = st.session_state.con.execute(f"SELECT * FROM {table} LIMIT 5").fetchdf()
                st.dataframe(preview_df)
            except Exception as e:
                st.warning(f"Preview failed for {table}: {e}")

except Exception as e:
    st.error(f"Failed to fetch tables: {e}")

st.markdown("### ✍️ Run SQL Query")
default_query = "SELECT * FROM my_table LIMIT 5"
query = st.text_area("Write your SQL query here:", value=default_query, height=200)

if st.button("🏃 Run Query"):
    try:
        result = st.session_state.con.execute(query).fetchdf()
        st.session_state.query_result = result

        st.success("✅ Query executed!")
        st.dataframe(result)

        csv = result.to_csv(index=False)
        st.download_button("📅 Download Result as CSV", data=csv, file_name="query_result.csv", mime="text/csv")

    except Exception as e:
        st.error(f"❌ Query failed: {e}")

### todo: 
### integrate streamlit-js-eval to save uploaded CSVs in base64 localstorage
### Delete / Rename tables
### integrate openai?
### print via html
### use eval to make jupyter like cells
