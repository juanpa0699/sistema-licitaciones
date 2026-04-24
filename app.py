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

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(layout="wide", page_title="Sistema de Gestión de Licitaciones")

# =====================================
# 2. FUNCIONES DE APOYO
# =====================================
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def limpiar_actividad_estricto(texto):
    if not texto: return ""
    texto = re.sub(r"\d+\s+(de|para|terminar|hora|horas|minutos|min|días|segundos).*", "", texto, flags=re.IGNORECASE)
    palabras_basura = [r"\btiempo transcurrido\b", r"\btranscurrido\b", r"\bBogotá\b", r"\bUTC\b", r"\bAM\b", r"\bPM\b"]
    for patron in palabras_basura:
        texto = re.sub(patron, "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\d{1,2}/\d{1,2}/\d{4}.*", "", texto) 
    texto = re.sub(r"[\(\)\-\:\,]", "", texto)
    return " ".join(texto.split()).strip()

# =====================================
# 3. MANEJO DE SESIÓN Y LOGIN
# =====================================
if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🔑 Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Clave", type="password")
    if st.button("Entrar", use_container_width=True):
        res = supabase.table("usuarios").select("*").eq("username", u).eq("password", hash_password(p)).execute()
        if res.data:
            user = res.data[0]
            st.session_state.update({
                "login": True, "user": user["username"], 
                "rol": user["rol"], "empresa": user["empresa"]
            })
            st.rerun()
        else:
            st.error("Credenciales incorrectas.")
    st.stop()

# =====================================
# 4. NAVEGACIÓN LATERAL (FILTRADA POR ROL)
# =====================================
st.sidebar.title(f"👤 {st.session_state.user}")
st.sidebar.write(f"🏢 {st.session_state.empresa} ({st.session_state.rol})")

# Lógica solicitada: Invitados solo Dashboard y Mis Tareas
if st.session_state.rol == "admin":
    nav = ["Dashboard", "Mis tareas", "Procesos", "Cronograma", "Usuarios"]
else:
    nav = ["Dashboard", "Mis tareas"]

menu = st.sidebar.radio("Navegación", nav)

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.login = False
    st.rerun()

# Fecha de hoy ajustada (Colombia UTC-5)
hoy = datetime.now() - timedelta(hours=5)

# =====================================
# 5. DASHBOARD
# =====================================
if menu == "Dashboard":
    st.header("📊 Análisis por Contrato")
    query = supabase.table("procesos").select("*")
    if st.session_state.rol != "admin":
        query = query.eq("asignado_a", st.session_state.user)
    
    res_p = query.execute()
    if res_p.data:
        df_p = pd.DataFrame(res_p.data)
        sel = st.selectbox("Seleccione un proceso:", df_p['titulo'].tolist())
        proc = df_p[df_p['titulo'] == sel].iloc[0]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Presupuesto", f"${proc['valor']:,.0f}")
        c2.metric("🏛️ Entidad", proc['entidad'])
        c3.metric("🆔 ID", proc['id'])

        st.divider()
        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.plotly_chart(px.bar(df_p[df_p['id'] == proc['id']], x="titulo", y="valor", color_discrete_sequence=["#00CC96"]), use_container_width=True)
        with col_b:
            res_act = supabase.table("actividades").select("*").eq("id_proceso", proc['id']).execute()
            if res_act.data:
                df_act = pd.DataFrame(res_act.data)
                df_act["act_limpia"] = df_act["actividad"].apply(limpiar_actividad_estricto)
                fig = px.timeline(df_act, x_start="inicio", x_end="fin", y="act_limpia")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay procesos asignados.")

# =====================================
# 6. MIS TAREAS
# =====================================
if menu == "Mis tareas":
    st.header("📅 Mis Compromisos")
    query = supabase.table("procesos").select("*")
    if st.session_state.rol != "admin":
        query = query.eq("asignado_a", st.session_state.user)
    
    res_p = query.execute()
    if res_p.data:
        for row in res_p.data:
            with st.expander(f"📌 {row['titulo']} - {row['entidad']}", expanded=True):
                st.table(pd.DataFrame({
                    "Campo": ["Objeto", "Exp. General", "Exp. Específica"],
                    "Detalle": [row.get('objeto', 'N/A'), row.get('exp_general', 'N/A'), row.get('exp_especifica', 'N/A')]
                }))
                res_a = supabase.table("actividades").select("*").eq("id_proceso", row['id']).execute()
                if res_a.data:
                    df_a = pd.DataFrame(res_a.data)
                    df_a["act_limpia"] = df_a["actividad"].apply(limpiar_actividad_estricto)
                    df_a["fin"] = pd.to_datetime(df_a["fin"])
                    df_a["Estado"] = df_a["fin"].apply(lambda f: "🔴 Cerrado" if (f-hoy).days < 0 else ("🟡 Próximo" if (f-hoy).days <= 3 else "🟢 Activo"))
                    st.dataframe(df_a[["act_limpia", "fin", "Estado"]].sort_values("fin"), use_container_width=True, hide_index=True)

# =====================================
# 7. PROCESOS (ADMIN)
# =====================================
if menu == "Procesos":
    st.header("🆕 Registro de Licitación")
    res_users = supabase.table("usuarios").select("username").execute()
    lista_usuarios = [u['username'] for u in res_users.data] if res_users.data else [st.session_state.user]

    with st.form("form_proc"):
        c1, c2 = st.columns(2)
        idp = c1.text_input("ID Proceso")
        tit = c1.text_input("Título")
        val = c2.number_input("Valor", min_value=0.0)
        ent = c2.text_input("Entidad")
        obj = st.text_area("Objeto")
        exp_g = st.text_area("Exp. General")
        exp_e = st.text_area("Exp. Específica")
        asig = st.selectbox("Asignar a:", lista_usuarios)
        if st.form_submit_button("Guardar Proceso"):
            supabase.table("procesos").insert({"id": idp, "titulo": tit, "valor": val, "entidad": ent, "objeto": obj, "exp_general": exp_g, "exp_especifica": exp_e, "asignado_a": asig, "empresa": st.session_state.empresa}).execute()
            st.success("Guardado.")

# =====================================
# 8. CRONOGRAMA (ADMIN)
# =====================================
if menu == "Cronograma":
    st.header("⏳ Cargar Cronograma")
    res_c = supabase.table("procesos").select("id, titulo").execute()
    if res_c.data:
        df_c = pd.DataFrame(res_c.data)
        proc_sel = st.selectbox("Proceso:", df_c['titulo'].tolist())
        id_ref = df_c[df_c['titulo'] == proc_sel].iloc[0]['id']
        txt = st.text_area("Pegue texto de SECOP")
        if st.button("Vincular"):
            for linea in txt.split("\n"):
                m = re.search(r"\d{1,2}/\d{1,2}/\d{4}", linea)
                if m:
                    supabase.table("actividades").insert({"id_proceso": id_ref, "actividad": linea, "inicio": hoy.isoformat(), "fin": datetime.strptime(m.group(), "%d/%m/%Y").isoformat()}).execute()
            st.success("Cronograma cargado.")

# =====================================
# 9. USUARIOS (ADMIN - GESTIÓN TOTAL)
# =====================================
if menu == "Usuarios" and st.session_state.rol == "admin":
    st.header("👤 Gestión de Usuarios")
    
    t_lista, t_nuevo, t_borrar = st.tabs(["👥 Lista de Usuarios", "➕ Crear Nuevo", "🗑️ Eliminar Proceso"])
    
    with t_lista:
        res_u = supabase.table("usuarios").select("username, rol, empresa").execute()
        if res_u.data:
            df_u = pd.DataFrame(res_u.data)
            st.dataframe(df_u, use_container_width=True)
            
            st.divider()
            st.subheader("🔑 Cambiar Contraseña")
            user_to_mod = st.selectbox("Seleccione usuario para cambiar clave:", df_u['username'].tolist())
            new_pass = st.text_input("Nueva Clave", type="password")
            if st.button("Actualizar Clave"):
                supabase.table("usuarios").update({"password": hash_password(new_pass)}).eq("username", user_to_mod).execute()
                st.success(f"Clave de {user_to_mod} actualizada.")

    with t_nuevo:
        with st.form("f_new_user"):
            nu = st.text_input("Username")
            np = st.text_input("Password", type="password")
            ne = st.text_input("Empresa", value=st.session_state.empresa)
            nr = st.selectbox("Rol", ["invitado", "admin"])
            if st.form_submit_button("Registrar"):
                supabase.table("usuarios").insert({"username": nu, "password": hash_password(np), "rol": nr, "email": f"{nu}@mail.com", "empresa": ne}).execute()
                st.success(f"Usuario {nu} creado.")
                st.rerun()

    with t_borrar:
        st.subheader("⚠️ Zona de Peligro")
        res_del = supabase.table("procesos").select("id, titulo").execute()
        if res_del.data:
            df_del = pd.DataFrame(res_del.data)
            borrar = st.selectbox("Eliminar proceso:", df_del['titulo'].tolist())
            if st.button("❌ ELIMINAR PROCESO"):
                id_b = df_del[df_del['titulo'] == borrar].iloc[0]['id']
                supabase.table("procesos").delete().eq("id", id_b).execute()
                st.warning("Eliminado.")
                st.rerun()
