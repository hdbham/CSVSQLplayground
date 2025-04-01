# 📊 CSV SQL Playground (Privacy-Friendly Streamlit App)

A lightweight SQL interface built with Streamlit + DuckDB that lets you upload CSV files, register them as DuckDB tables, and run SQL queries in your browser.

> 🛡️ Designed with privacy in mind — intended to evolve toward full client-side persistence using browser storage.

---

## 🚀 Features

- 📁 Upload CSV files directly in the browser
- 🧃 Register CSVs as DuckDB tables (locally)
- 🔍 Preview table data
- ✍️ Write and run custom SQL queries on uploaded tables
- 📤 Export query results as downloadable CSVs
- 🧠 Session-based state (no login required)

---

## 🛠️ Roadmap / TODO

- [ ] **Integrate [`streamlit-js-eval`](https://github.com/okld/streamlit-js-eval)**  
  Store uploaded CSVs in browser `localStorage` as base64  
  ➕ Enables user-side privacy and persistence across sessions

- [ ] **Delete / Rename Tables**  
  Add UI to remove or rename registered DuckDB tables

- [ ] **Integrate OpenAI**  
  Use natural language prompts to generate SQL queries

- [ ] **HTML Print View**  
  Render query results in a clean printable format

- [ ] **Jupyter-like Cells** via JS `eval()`  
  Allow users to write and execute SQL or markdown-like blocks inline

---

## 🧰 Tech Stack

- 🐍 Python 3.11+
- ⚡ Streamlit
- 🦆 DuckDB
- 🐼 Pandas
- 🍪 [`streamlit-js-eval`](https://github.com/okld/streamlit-js-eval) *(planned)*

---

## ⚙️ Setup

```bash
pip install -r requirements.txt
streamlit run main.py
