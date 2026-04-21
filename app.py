import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import re
from datetime import datetime
import plotly.express as px
import smtplib
from email.mime.text import MIMEText

st.set_page_config(page_title="Sistema Licitaciones", layout="wide")

# =========================
# ESTILOS
# =========================
st.markdown("""
<style>
.block-container {padding-top: 1.5rem;}
.kpi {border-radius: 14px; padding: 14px 18px; background: #0f172a; color: #e5e7eb;}
.kpi h4 {margin:0; font-size: 0.9rem; color:#94a3b8}
.kpi h2 {margin:0; font-size: 1.6rem;}
</style>
""", unsafe_allow_html=True)

# =========================
# BASE DE DATOS
# =========================
def get_conn():
    return sqlite3.connect("licitaciones.db", check_same_thread=False)

def crear_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS usuarios(
        username TEXT PRIMARY KEY,
        password TEXT,
        rol TEXT,
        email TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS procesos(
        id TEXT,
        entidad TEXT,
        objeto TEXT,
        tipo TEXT,
        exp_general TEXT,
        exp_especifica TEXT,
        link TEXT,
        asignado_a TEXT,
        valor REAL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS cronograma(
        id_proceso TEXT,
        evento TEXT,
        fecha TEXT
    )""")

    conn.commit()
    conn.close()

crear_db()

# =========================
# SEGURIDAD
# =========================
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def crear_usuario(u,p,rol,email):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO usuarios VALUES (?,?,?,?)",
                     (u,hash_password(p),rol,email))
        conn.commit()
    except:
        pass
    conn.close()

def verificar_usuario(u,p):
    conn = get_conn()
    df = conn.execute("SELECT * FROM usuarios WHERE username=? AND password=?",
                      (u,hash_password(p))).fetchone()
    conn.close()
    return df

crear_usuario("admin","1234","admin","tucorreo@gmail.com")

# =========================
# EMAIL
# =========================
def enviar_correo(destino, asunto, mensaje):
    try:
        remitente = st.secrets["EMAIL_USER"]
        clave = st.secrets["EMAIL_PASS"]

        msg = MIMEText(mensaje)
        msg["Subject"] = asunto
        msg["From"] = remitente
        msg["To"] = destino

        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(remitente, clave)
        s.sendmail(remitente, destino, msg.as_string())
        s.quit()
    except:
        pass

# =========================
# FUNCIONES CRONOGRAMA
# =========================
def limpiar_evento(texto):
    texto = re.sub(r"\(.*?\)", "", texto)
    texto = re.sub(r"\d+.*?(d[ií]as|horas).*?(terminar|transcurrido)", "", texto)
    return texto.strip()

def extraer_fecha(texto):
    m = re.search(r"\d{2}/\d{2}/\d{4}", texto)
    return datetime.strptime(m.group(), "%d/%m/%Y") if m else None

def dias_restantes(fecha):
    return (fecha - datetime.now()).days if fecha else None

def estado_proceso(dias):
    if dias is None: return "Sin fecha"
    elif dias < 0: return "🔴 Vencido"
    elif dias <= 3: return "🟡 Próximo"
    else: return "🟢 En curso"

def generar_alertas(df, correo):
    alertas = []
    for _, r in df.iterrows():
        if r["dias"] is not None and r["dias"] <= 3:
            msg = f"{r['evento']} | {r['fecha']} | {r['dias']} días"
            alertas.append(msg)
            enviar_correo(correo, "Alerta Licitación", msg)
    return alertas

# =========================
# LOGIN
# =========================
if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🔐 Login")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        user = verificar_usuario(u,p)
        if user:
            st.session_state.login = True
            st.session_state.usuario = user[0]
            st.session_state.rol = user[2]
            st.session_state.email = user[3]
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

    st.stop()

# =========================
# SIDEBAR
# =========================
st.sidebar.title(f"👤 {st.session_state.usuario}")
menu = st.sidebar.radio("Menú", ["Dashboard","Procesos","Cronograma"])

# =========================
# ADMIN
# =========================
if st.session_state.rol == "admin":

    conn = get_conn()

    if menu == "Dashboard":
        st.title("📊 Dashboard")

        cron = pd.read_sql("SELECT * FROM cronograma", conn)

        if not cron.empty:
            cron["fecha"] = pd.to_datetime(cron["fecha"])
            cron["dias"] = cron["fecha"].apply(dias_restantes)

            col1, col2, col3 = st.columns(3)
            col1.markdown(f"<div class='kpi'><h4>Total eventos</h4><h2>{len(cron)}</h2></div>", unsafe_allow_html=True)
            col2.markdown(f"<div class='kpi'><h4>Próximos</h4><h2>{(cron['dias']<=3).sum()}</h2></div>", unsafe_allow_html=True)
            col3.markdown(f"<div class='kpi'><h4>Vencidos</h4><h2>{(cron['dias']<0).sum()}</h2></div>", unsafe_allow_html=True)

            st.subheader("Ranking por urgencia")
            st.dataframe(cron.sort_values("dias"))

    if menu == "Procesos":
        st.title("📁 Crear proceso")

        usuarios = pd.read_sql("SELECT username FROM usuarios WHERE rol='invitado'", conn)

        with st.form("form"):
            idp = st.text_input("ID")
            entidad = st.text_input("Entidad")
            objeto = st.text_area("Objeto")
            tipo = st.text_input("Tipo")
            expg = st.text_input("Exp General")
            expe = st.text_input("Exp Específica")
            link = st.text_input("Link")
            valor = st.number_input("Valor oferta", 0.0)
            asignado = st.selectbox("Asignar", usuarios["username"] if not usuarios.empty else [""])

            if st.form_submit_button("Guardar"):
                conn.execute("INSERT INTO procesos VALUES (?,?,?,?,?,?,?,?,?)",
                             (idp, entidad, objeto, tipo, expg, expe, link, asignado, valor))
                conn.commit()
                st.success("Proceso guardado")

    if menu == "Cronograma":
        st.title("📅 Cargar cronograma")

        idp = st.text_input("ID proceso")
        texto = st.text_area("Pegar cronograma SECOP")

        if st.button("Procesar"):
            for l in texto.split("\n"):
                evento = limpiar_evento(l)
                fecha = extraer_fecha(l)
                if evento and fecha:
                    conn.execute("INSERT INTO cronograma VALUES (?,?,?)",
                                 (idp, evento, fecha.strftime("%Y-%m-%d")))
            conn.commit()
            st.success("Cronograma guardado")

    conn.close()

# =========================
# INVITADO
# =========================
if st.session_state.rol == "invitado":

    conn = get_conn()

    st.title("📊 Mis procesos")

    df = pd.read_sql(f"SELECT * FROM procesos WHERE asignado_a='{st.session_state.usuario}'", conn)

    st.dataframe(df)

    for _, row in df.iterrows():

        st.subheader(f"📌 {row['id']}")

        cron = pd.read_sql(f"SELECT * FROM cronograma WHERE id_proceso='{row['id']}'", conn)

        if not cron.empty:
            cron["fecha"] = pd.to_datetime(cron["fecha"])
            cron["dias"] = cron["fecha"].apply(dias_restantes)
            cron["estado"] = cron["dias"].apply(estado_proceso)

            st.dataframe(cron)

            alertas = generar_alertas(cron, st.session_state.email)

            if alertas:
                st.warning("🔔 Alertas")
                for a in alertas:
                    st.write(a)

            fig = px.timeline(
                cron,
                x_start="fecha",
                x_end="fecha",
                y="evento",
                color="estado"
            )

            st.plotly_chart(fig, use_container_width=True)

    conn.close()