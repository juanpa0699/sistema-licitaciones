import streamlit as st
import pandas as pd
import hashlib, re
from datetime import datetime, timedelta
import plotly.express as px
from supabase import create_client

# 1. CONEXIÓN (Claves actuales)
URL = "https://fszpctbemyrcoktcemfd.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZzenBjdGJlbXlyY29rdGNlbWZkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5Nzg2ODgsImV4cCI6MjA5MjU1NDY4OH0.p3uBZXkfNlzAqQJEpc0elHPEfDhNCQsHEF_Gi7AyBWk"
supabase = create_client(URL, KEY)

st.set_page_config(layout="wide", page_title="Sistema Licitaciones v2")

# 2. LOGIN Y SESIÓN
if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🔑 Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Clave", type="password")
    if st.button("Entrar", width='stretch'):
        # Hasheamos la clave para buscarla
        hp = hashlib.sha256(p.encode()).hexdigest()
        res = supabase.table("usuarios").select("*").eq("username", u).eq("password", hp).execute()
        if res.data:
            st.session_state.update({"login": True, "user": u, "rol": res.data[0]["rol"], "emp": res.data[0]["empresa"]})
            st.rerun()
        else:
            st.error("Datos incorrectos")
    st.stop()

# 3. FILTRO DE ROLES (Aquí es donde se hace la magia que pediste)
st.sidebar.title(f"👤 {st.session_state.user}")
st.sidebar.write(f"Rol: {st.session_state.rol}")

# Si es admin, ve 5 opciones. Si es invitado, solo ve 2.
if st.session_state.rol == "admin":
    paginas = ["Dashboard", "Mis tareas", "Procesos", "Cronograma", "Usuarios"]
else:
    paginas = ["Dashboard", "Mis tareas"]

menu = st.sidebar.radio("Menú", paginas)

if st.sidebar.button("Salir"):
    st.session_state.login = False
    st.rerun()

# 4. CONTENIDO DE LAS PÁGINAS
if menu == "Dashboard":
    st.header("📊 Resumen")
    st.write(f"Bienvenido al panel de {st.session_state.rol}")
    # (Aquí va tu lógica de gráficas que ya funcionaba)

elif menu == "Mis tareas":
    st.header("📅 Mis Tareas Asignadas")
    # Filtramos procesos según el usuario logueado
    q = supabase.table("procesos").select("*").eq("asignado_a", st.session_state.user).execute()
    if q.data:
        for r in q.data:
            with st.expander(f"📌 {r['titulo']}"):
                st.write(r['objeto'])
    else:
        st.info("No tienes tareas pendientes.")

# 5. SOLO PARA ADMINS
elif menu == "Usuarios" and st.session_state.rol == "admin":
    st.header("👤 Gestión de Usuarios")
    # LISTA DE USUARIOS
    res_u = supabase.table("usuarios").select("*").execute()
    df_u = pd.DataFrame(res_u.data)
    st.subheader("Usuarios actuales")
    st.dataframe(df_u[["username", "rol"]], width='stretch')
    
    st.divider()
    st.subheader("Cambiar Clave o Crear")
    with st.form("f_usuarios"):
        new_u = st.text_input("Nombre de Usuario")
        new_p = st.text_input("Nueva Clave", type="password")
        new_r = st.selectbox("Rol", ["invitado", "admin"])
        if st.form_submit_button("Guardar/Actualizar"):
            h_new = hashlib.sha256(new_p.encode()).hexdigest()
            # Upsert busca si existe para actualizar, si no lo crea
            supabase.table("usuarios").upsert({"username": new_u, "password": h_new, "rol": new_r, "empresa": st.session_state.emp}).execute()
            st.success("Usuario procesado correctamente")
            st.rerun()

elif menu == "Procesos" and st.session_state.rol == "admin":
    st.header("🆕 Configurar Procesos")
    st.write("Panel exclusivo para administradores")
