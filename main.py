import streamlit as st
import pandas as pd
import hashlib, re
from datetime import datetime, timedelta
import plotly.express as px
from supabase import create_client

# =====================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# =====================================
SUPABASE_URL = "https://fszpctbemyrcoktcemfd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZzenBjdGJlbXlyY29rdGNlbWZkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5Nzg2ODgsImV4cCI6MjA5MjU1NDY4OH0.p3uBZXkfNlzAqQJEpc0elHPEfDhNCQsHEF_Gi7AyBWk"

# Inicialización segura de Supabase
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Error de conexión con la base de datos: {e}")

st.set_page_config(layout="wide", page_title="Sistema de Licitaciones 2026")

# =====================================
# 2. FUNCIONES DE SEGURIDAD Y LIMPIEZA
# =====================================
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def limpiar_actividad_estricto(texto):
    if not texto: return ""
    # Limpieza de muletillas de tiempo SECOP
    texto = re.sub(r"\d+\s+(de|para|terminar|hora|horas|minutos|min|días|segundos).*", "", texto, flags=re.IGNORECASE)
    palabras_basura = [r"\btiempo transcurrido\b", r"\btranscurrido\b", r"\bBogotá\b", r"\bUTC\b", r"\bAM\b", r"\bPM\b"]
    for patron in palabras_basura:
        texto = re.sub(patron, "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\d{1,2}/\d{1,2}/\d{4}.*", "", texto) 
    texto = re.sub(r"[\(\)\-\:\,]", "", texto)
    return " ".join(texto.split()).strip()

# =====================================
# 3. MANEJO DE SESIÓN Y ACCESO
# =====================================
if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🔑 Control de Acceso")
    with st.container(border=True):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Iniciar Sesión", width='stretch'):
            res = supabase.table("usuarios").select("*").eq("username", u).eq("password", hash_password(p)).execute()
            if res.data:
                user_data = res.data[0]
                st.session_state.update({
                    "login": True, 
                    "user": user_data["username"], 
                    "rol": user_data["rol"], 
                    "empresa": user_data["empresa"]
                })
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

# =====================================
# 4. NAVEGACIÓN (LÓGICA DE ROLES)
# =====================================
st.sidebar.title(f"👤 {st.session_state.user}")
st.sidebar.markdown(f"**Rol:** `{st.session_state.rol.upper()}`")

# FILTRO DE MENÚ: Solo admin ve Procesos, Cronograma y Usuarios
if st.session_state.rol == "admin":
    nav_options = ["Dashboard", "Mis tareas", "Procesos", "Cronograma", "Usuarios"]
else:
    nav_options = ["Dashboard", "Mis tareas"]

menu = st.sidebar.radio("Navegación Principal", nav_options)

if st.sidebar.button("Cerrar Sesión", icon="🚀"):
    st.session_state.login = False
    st.rerun()

# Fecha actual ajustada (Colombia UTC-5)
hoy = datetime.now() - timedelta(hours=5)

# =====================================
# 5. MÓDULO: DASHBOARD
# =====================================
if menu == "Dashboard":
    st.header("📊 Resumen General")
    query = supabase.table("procesos").select("*")
    if st.session_state.rol != "admin":
        query = query.eq("asignado_a", st.session_state.user)
    
    res = query.execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        sel = st.selectbox("Seleccione Proceso para Analizar:", df_p['titulo'].tolist())
        proc = df_p[df_p['titulo'] == sel].iloc[0]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Presupuesto", f"${proc['valor']:,.0f}")
        c2.metric("🏛️ Entidad", proc['entidad'])
        c3.metric("🆔 ID Interno", proc['id'])

        st.divider()
        col_chart, col_list = st.columns([1, 1])
        with col_chart:
            st.plotly_chart(px.bar(df_p[df_p['id'] == proc['id']], x="titulo", y="valor", color_discrete_sequence=["#00CC96"]), width='stretch')
        with col_list:
            res_act = supabase.table("actividades").select("*").eq("id_proceso", proc['id']).execute()
            if res_act.data:
                df_act = pd.DataFrame(res_act.data)
                df_act["act_limpia"] = df_act["actividad"].apply(limpiar_actividad_estricto)
                fig = px.timeline(df_act, x_start="inicio", x_end="fin", y="act_limpia", title="Cronograma de Actividades")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, width='stretch')
    else:
        st.info("No tienes procesos asignados actualmente.")

# =====================================
# 6. MÓDULO: MIS TAREAS
# =====================================
elif menu == "Mis tareas":
    st.header("📅 Mis Tareas y Requisitos")
    query = supabase.table("procesos").select("*")
    if st.session_state.rol != "admin":
        query = query.eq("asignado_a", st.session_state.user)
    
    res = query.execute()
    if res.data:
        for row in res.data:
            with st.expander(f"📌 {row['titulo']} - {row['entidad']}", expanded=True):
                st.markdown(f"**Objeto:** {row.get('objeto', 'No definido')}")
                st.markdown(f"**Experiencia:** {row.get('exp_general', 'No definida')}")
                
                res_a = supabase.table("actividades").select("*").eq("id_proceso", row['id']).execute()
                if res_a.data:
                    df_a = pd.DataFrame(res_a.data)
                    df_a["act_limpia"] = df_a["actividad"].apply(limpiar_actividad_estricto)
                    df_a["fin"] = pd.to_datetime(df_a["fin"])
                    # Lógica de Semáforo
                    df_a["Estado"] = df_a["fin"].apply(lambda f: "🔴 Cerrado" if (f-hoy).days < 0 else ("🟡 Próximo (3d)" if (f-hoy).days <= 3 else "🟢 Activo"))
                    st.dataframe(df_a[["act_limpia", "fin", "Estado"]].sort_values("fin"), width='stretch', hide_index=True)

# =====================================
# 7. MÓDULO: PROCESOS (ADMIN)
# =====================================
elif menu == "Procesos" and st.session_state.rol == "admin":
    st.header("🆕 Registrar Nueva Licitación")
    res_u = supabase.table("usuarios").select("username").execute()
    lista_users = [u['username'] for u in res_u.data]

    with st.form("form_nuevo_proceso"):
        c1, c2 = st.columns(2)
        idp = c1.text_input("ID Proceso")
        tit = c1.text_input("Título")
        val = c2.number_input("Valor", min_value=0.0)
        ent = c2.text_input("Entidad")
        obj = st.text_area("Objeto del contrato")
        asig = st.selectbox("Asignar a Responsable:", lista_users)
        
        if st.form_submit_button("Crear Proceso"):
            supabase.table("procesos").insert({
                "id": idp, "titulo": tit, "valor": val, "entidad": ent, 
                "objeto": obj, "asignado_a": asig, "empresa": st.session_state.empresa
            }).execute()
            st.success("Proceso registrado exitosamente.")

# =====================================
# 8. MÓDULO: CRONOGRAMA (ADMIN)
# =====================================
elif menu == "Cronograma" and st.session_state.rol == "admin":
    st.header("⏳ Vincular Cronograma SECOP")
    res_c = supabase.table("procesos").select("id, titulo").execute()
    if res_c.data:
        df_c = pd.DataFrame(res_c.data)
        ps = st.selectbox("Seleccione Proceso:", df_c['titulo'].tolist())
        id_ref = df_c[df_c['titulo'] == ps].iloc[0]['id']
        
        txt = st.text_area("Pegue aquí el texto copiado de SECOP")
        if st.button("Procesar y Vincular"):
            count = 0
            for linea in txt.split("\n"):
                m = re.search(r"\d{1,2}/\d{1,2}/\d{4}", linea)
                if m:
                    supabase.table("actividades").insert({
                        "id_proceso": id_ref, "actividad": linea,
                        "inicio": hoy.isoformat(),
                        "fin": datetime.strptime(m.group(), "%d/%m/%Y").isoformat()
                    }).execute()
                    count += 1
            st.success(f"Se vincularon {count} actividades correctamente.")

# =====================================
# 9. MÓDULO: USUARIOS (GESTIÓN TOTAL)
# =====================================
elif menu == "Usuarios" and st.session_state.rol == "admin":
    st.header("👤 Administración de Usuarios")
    t_list, t_new, t_del = st.tabs(["👥 Lista y Claves", "➕ Nuevo Usuario", "🗑️ Eliminar Proceso"])
    
    with t_list:
        res_u = supabase.table("usuarios").select("username, rol, empresa").execute()
        if res_u.data:
            df_usuarios = pd.DataFrame(res_u.data)
            st.dataframe(df_usuarios, width='stretch', hide_index=True)
            
            st.divider()
            st.subheader("🔑 Cambiar Contraseña")
            user_mod = st.selectbox("Usuario a modificar:", df_usuarios['username'].tolist())
            pass_new = st.text_input("Nueva Contraseña", type="password")
            if st.button("Actualizar Clave"):
                supabase.table("usuarios").update({"password": hash_password(pass_new)}).eq("username", user_mod).execute()
                st.success(f"La contraseña de {user_mod} ha sido actualizada.")

    with t_new:
        with st.form("form_new_user"):
            nu = st.text_input("Username")
            np = st.text_input("Password", type="password")
            nr = st.selectbox("Rol", ["invitado", "admin"])
            if st.form_submit_button("Registrar Usuario"):
                supabase.table("usuarios").insert({
                    "username": nu, "password": hash_password(np), 
                    "rol": nr, "empresa": st.session_state.empresa
                }).execute()
                st.success(f"Usuario {nu} creado correctamente.")
                st.rerun()

    with t_del:
        st.subheader("⚠️ Zona de Borrado")
        res_p = supabase.table("procesos").select("id, titulo").execute()
        if res_p.data:
            df_p = pd.DataFrame(res_p.data)
            b = st.selectbox("Proceso a eliminar:", df_p['titulo'].tolist())
            if st.button("❌ ELIMINAR AHORA"):
                supabase.table("procesos").delete().eq("id", df_p[df_p['titulo']==b].iloc[0]['id']).execute()
                st.warning("Proceso eliminado de la base de datos.")
                st.rerun()
