import streamlit as st
import pandas as pd
import sqlite3, hashlib, re, os
from datetime import datetime
import plotly.express as px

# =========================
# IMPORTS SEGUROS (IA)
# =========================
try:
    import joblib
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
    SKLEARN_OK = True
except:
    SKLEARN_OK = False

st.set_page_config(layout="wide")

# =========================
# DB
# =========================
def get_conn():
    conn = sqlite3.connect("licitaciones.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def crear_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS usuarios(
        username TEXT PRIMARY KEY,
        password TEXT,
        rol TEXT,
        email TEXT,
        empresa TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS procesos(
        id TEXT,
        empresa TEXT,
        objeto TEXT,
        tipo TEXT,
        valor REAL,
        asignado_a TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS cronograma(
        id_proceso TEXT,
        evento TEXT,
        fecha TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS historial(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_proceso TEXT,
        resultado TEXT
    )""")

    # 🔧 FIX BD antigua
    try: c.execute("ALTER TABLE usuarios ADD COLUMN empresa TEXT")
    except: pass

    conn.commit()
    conn.close()

crear_db()

# =========================
# SEGURIDAD
# =========================
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def crear_usuario(u,p,rol,email,empresa):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO usuarios VALUES (?,?,?,?,?)",
                     (u,hash_password(p),rol,email,empresa))
        conn.commit()
    except:
        pass
    conn.close()

def login(u,p):
    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM usuarios WHERE username=? AND password=?",
        (u,hash_password(p))
    ).fetchone()
    conn.close()
    return user

crear_usuario("admin","1234","admin","admin@mail.com","ADMIN")

# =========================
# UTILIDADES
# =========================
def limpiar_evento(t):
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"\d+.*?d[ií]as.*?", "", t)
    return t.strip()

def extraer_fecha(t):
    m = re.search(r"\d{2}/\d{2}/\d{4}", t)
    return datetime.strptime(m.group(), "%d/%m/%Y") if m else None

def dias_restantes(f):
    return (f - datetime.now()).days if f else None

# =========================
# IA
# =========================
MODEL = "modelo.pkl"

def entrenar(conn):
    if not SKLEARN_OK:
        return None

    df = pd.read_sql("""
    SELECT p.valor, p.objeto, h.resultado
    FROM historial h JOIN procesos p ON h.id_proceso=p.id
    WHERE h.resultado IS NOT NULL
    """, conn)

    if df.empty:
        return None

    df["target"] = df["resultado"].apply(lambda x: 1 if x=="Ganado" else 0)

    X = df[["valor","objeto"]]
    y = df["target"]

    prep = ColumnTransformer([
        ("num", StandardScaler(), ["valor"]),
        ("txt", TfidfVectorizer(max_features=50), "objeto")
    ])

    model = Pipeline([
        ("prep", prep),
        ("clf", RandomForestClassifier())
    ])

    Xtr,Xte,ytr,yte = train_test_split(X,y,test_size=0.2)
    model.fit(Xtr,ytr)

    joblib.dump(model, MODEL)
    return model.score(Xte,yte)

def cargar_modelo():
    if not SKLEARN_OK:
        return None
    return joblib.load(MODEL) if os.path.exists(MODEL) else None

# =========================
# LOGIN
# =========================
if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("Login")

    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):
        user = login(u,p)
        if user:
            st.session_state.login = True
            st.session_state.user = user["username"]
            st.session_state.rol = user["rol"]
            st.session_state.empresa = user["empresa"] if user["empresa"] else "DEFAULT"
            st.rerun()

    st.stop()

# =========================
# MENU
# =========================
menu = st.sidebar.radio("Menú",
["Dashboard","Procesos","Cronograma","Usuarios","Listado"])

conn = get_conn()

# =========================
# DASHBOARD
# =========================
if menu == "Dashboard":

    st.title("💰 Dashboard Gerencial")

    df = pd.read_sql(f"""
    SELECT * FROM procesos
    WHERE empresa='{st.session_state.empresa}'
    """, conn)

    if not df.empty:
        st.metric("Valor total", f"${df['valor'].sum():,.0f}")

        fig = px.bar(df.sort_values("valor"), x="valor", y="objeto", orientation="h")
        st.plotly_chart(fig, use_container_width=True)

# =========================
# PROCESOS
# =========================
if menu == "Procesos":

    with st.form("f"):
        idp = st.text_input("ID")
        obj = st.text_area("Objeto")
        val = st.number_input("Valor", 0.0)

        if st.form_submit_button("Guardar"):
            conn.execute("INSERT INTO procesos VALUES (?,?,?,?,?,?)",
                         (idp, st.session_state.empresa, obj, "", val, st.session_state.user))
            conn.commit()
            st.success("Proceso guardado")

# =========================
# CRONOGRAMA
# =========================
if menu == "Cronograma":

    idp = st.text_input("ID proceso")
    txt = st.text_area("Pegar cronograma")

    if st.button("Procesar"):
        for l in txt.split("\n"):
            ev = limpiar_evento(l)
            f = extraer_fecha(l)
            if ev and f:
                conn.execute("INSERT INTO cronograma VALUES (?,?,?)",(idp,ev,f))
        conn.commit()

    cron = pd.read_sql(f"SELECT * FROM cronograma WHERE id_proceso='{idp}'", conn)

    if not cron.empty:
        cron["fecha"] = pd.to_datetime(cron["fecha"])
        fig = px.timeline(cron, x_start="fecha", x_end="fecha", y="evento")
        st.plotly_chart(fig)

# =========================
# USUARIOS
# =========================
if menu == "Usuarios" and st.session_state.rol == "admin":

    u = st.text_input("Usuario")
    p = st.text_input("Clave", type="password")
    e = st.text_input("Empresa")

    if st.button("Crear"):
        crear_usuario(u,p,"invitado","",e)
        st.success("Usuario creado")

# =========================
# LISTADO + IA
# =========================
if menu == "Listado":

    df = pd.read_sql(f"""
    SELECT * FROM procesos
    WHERE empresa='{st.session_state.empresa}'
    """, conn)

    st.dataframe(df)

    if not SKLEARN_OK:
        st.warning("Instala scikit-learn y joblib para activar IA")

    if st.button("Entrenar IA"):
        score = entrenar(conn)
        if score:
            st.success(f"Modelo entrenado: {round(score*100,2)}%")

    model = cargar_modelo()

    for _, row in df.iterrows():

        if model:
            prob = model.predict_proba(pd.DataFrame([{
                "valor": row["valor"],
                "objeto": row["objeto"]
            }]))[0][1]

            st.write(row["objeto"])
            st.progress(prob)
            st.write(f"{int(prob*100)}%")

conn.close()
