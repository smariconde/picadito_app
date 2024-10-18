import streamlit as st
import sqlite3
import pandas as pd
import random
from itertools import combinations
import altair as alt
import numpy as np
import time


# Configurar el título de la página
st.set_page_config(page_title="Picadito App ⚽")

# Conexión a la base de datos
conn = sqlite3.connect('picadito.db')
c = conn.cursor()

# Crear tablas si no existen
c.execute('''CREATE TABLE IF NOT EXISTS jugadores
             (id INTEGER PRIMARY KEY, nombre TEXT, posicion TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS partidos
             (id INTEGER PRIMARY KEY, fecha TEXT, equipo1 TEXT, equipo2 TEXT, goles1 INTEGER, goles2 INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS equipos_generados
             (id INTEGER PRIMARY KEY, fecha TEXT, equipo1 TEXT, equipo2 TEXT)''')
conn.commit()

# Funciones auxiliares
def agregar_jugador(nombre, posicion):
    c.execute("INSERT INTO jugadores (nombre, posicion) VALUES (?, ?)", (nombre, posicion))
    conn.commit()

def obtener_jugadores():
    return pd.read_sql_query("SELECT id, nombre, posicion FROM jugadores ORDER BY nombre", conn)

def obtener_victorias_jugador(jugador):
    query = """
    SELECT COUNT(*) as victorias
    FROM partidos
    WHERE (equipo1 LIKE ? AND goles1 > goles2) OR (equipo2 LIKE ? AND goles2 > goles1)
    """
    result = c.execute(query, (f'%{jugador}%', f'%{jugador}%')).fetchone()
    return result[0] if result else 0

def generar_equipos_con_progreso(jugadores_disponibles, jugadores_por_equipo, max_defensores, min_mediocampistas, min_delanteros, ponderacion_victorias):
    # Obtener información de los jugadores
    jugadores_info = obtener_jugadores()
    jugadores_info = jugadores_info[jugadores_info['nombre'].isin(jugadores_disponibles)]
    
    # Calcular victorias para cada jugador
    jugadores_info['victorias'] = jugadores_info['nombre'].apply(obtener_victorias_jugador)
    
    # Generar todas las combinaciones posibles de equipos
    todas_combinaciones = list(combinations(jugadores_disponibles, jugadores_por_equipo))
    
    mejor_combinacion = None
    menor_diferencia = float('inf')
    mejor_victorias_equipo1 = 0
    mejor_victorias_equipo2 = 0
    
    # Crear una barra de progreso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, combo in enumerate(todas_combinaciones):
        # Actualizar la barra de progreso
        progress = (i + 1) / len(todas_combinaciones)
        progress_bar.progress(progress)
        status_text.text(f"Analizando combinación {i+1} de {len(todas_combinaciones)}")
        
        equipo1 = list(combo)
        equipo2 = [j for j in jugadores_disponibles if j not in equipo1]
        
        # Verificar que ambos equipos tengan el mismo número de jugadores
        if len(equipo1) != len(equipo2):
            continue
        
        # Verificar restricciones de posiciones
        posiciones_equipo1 = jugadores_info[jugadores_info['nombre'].isin(equipo1)]['posicion'].tolist()
        posiciones_equipo2 = jugadores_info[jugadores_info['nombre'].isin(equipo2)]['posicion'].tolist()
        
        if (posiciones_equipo1.count('Defensor') > max_defensores or
            posiciones_equipo2.count('Defensor') > max_defensores or
            posiciones_equipo1.count('Mediocampista') < min_mediocampistas or
            posiciones_equipo2.count('Mediocampista') < min_mediocampistas or
            posiciones_equipo1.count('Delantero') < min_delanteros or
            posiciones_equipo2.count('Delantero') < min_delanteros):
            continue
        
        # Calcular diferencia de victorias
        victorias_equipo1 = sum(jugadores_info[jugadores_info['nombre'].isin(equipo1)]['victorias'])
        victorias_equipo2 = sum(jugadores_info[jugadores_info['nombre'].isin(equipo2)]['victorias'])
        diferencia = abs(victorias_equipo1 - victorias_equipo2)
        
        # Aplicar ponderación de victorias
        diferencia *= ponderacion_victorias
        
        if diferencia < menor_diferencia:
            menor_diferencia = diferencia
            mejor_combinacion = (equipo1, equipo2)
            mejor_victorias_equipo1 = victorias_equipo1
            mejor_victorias_equipo2 = victorias_equipo2
        
        # Simular un pequeño retraso para que la animación sea visible
        time.sleep(0.01)
    
    # Limpiar la barra de progreso y el texto de estado
    progress_bar.empty()
    status_text.empty()
    
    if mejor_combinacion is None:
        return None
    else:
        return mejor_combinacion, mejor_victorias_equipo1, mejor_victorias_equipo2, menor_diferencia

def registrar_partido(fecha, equipo1, equipo2, goles1, goles2):
    c.execute("INSERT INTO partidos (fecha, equipo1, equipo2, goles1, goles2) VALUES (?, ?, ?, ?, ?)",
              (fecha, ','.join(equipo1), ','.join(equipo2), goles1, goles2))
    conn.commit()

def guardar_equipos_generados(fecha, equipo1, equipo2):
    c.execute("INSERT INTO equipos_generados (fecha, equipo1, equipo2) VALUES (?, ?, ?)",
              (fecha, ','.join(equipo1), ','.join(equipo2)))
    conn.commit()

def obtener_equipos_generados():
    return pd.read_sql_query("SELECT * FROM equipos_generados", conn)

def obtener_estadisticas_jugadores():
    query = """
    SELECT 
        j.nombre,
        j.posicion,
        COUNT(DISTINCT p.id) as partidos_jugados,
        SUM(CASE 
            WHEN (p.equipo1 LIKE '%' || j.nombre || '%' AND p.goles1 > p.goles2) OR 
                 (p.equipo2 LIKE '%' || j.nombre || '%' AND p.goles2 > p.goles1) 
            THEN 1 ELSE 0 END) as victorias
    FROM 
        jugadores j
    LEFT JOIN 
        partidos p ON p.equipo1 LIKE '%' || j.nombre || '%' OR p.equipo2 LIKE '%' || j.nombre || '%'
    GROUP BY 
        j.id
    ORDER BY 
        victorias DESC, partidos_jugados DESC
    """
    df = pd.read_sql_query(query, conn)
    df['porcentaje_victorias'] = (df['victorias'] / df['partidos_jugados'] * 100).round(2)
    df['porcentaje_victorias'] = df['porcentaje_victorias'].fillna(0)
    return df

def obtener_partidos():
    query = """
    SELECT id, fecha, equipo1, equipo2, goles1, goles2
    FROM partidos
    ORDER BY fecha DESC
    """
    return pd.read_sql_query(query, conn)

def borrar_partido(partido_id):
    c.execute("DELETE FROM partidos WHERE id = ?", (partido_id,))
    conn.commit()

def borrar_jugador(jugador_id):
    c.execute("DELETE FROM jugadores WHERE id = ?", (jugador_id,))
    conn.commit()

def actualizar_jugador(jugador_id, nombre, posicion):
    c.execute("UPDATE jugadores SET nombre = ?, posicion = ? WHERE id = ?", (nombre, posicion, jugador_id))
    conn.commit()

def get_table_style():
    return [
        dict(selector="th", props=[("font-weight", "bold"), 
                                   ("color", "#FFA500"), 
                                   ("background-color", "#1E1E1E")]),
        dict(selector="td", props=[("color", "#FFFFFF"), 
                                   ("background-color", "#2E2E2E")]),
        dict(selector="tr:nth-of-type(even)", props=[("background-color", "#3E3E3E")])
    ]

# Interfaz de Streamlit
st.title('Picadito App ⚽')

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Jugadores 👤", "Generar Equipos 👥", "Registrar Partido 📝", "Posiciones 🥇", "Historial de Partidos 🏟️"])

with tab1:
    st.header("Registro de Jugadores 👤")
    
    # Formulario para agregar nuevo jugador
    with st.form("nuevo_jugador"):
        nuevo_nombre = st.text_input("Nombre del jugador")
        nueva_posicion = st.selectbox("Posición", ["Delantero", "Mediocampista", "Defensor", "Arquero"])
        submitted = st.form_submit_button("Agregar Jugador")
        if submitted:
            agregar_jugador(nuevo_nombre, nueva_posicion)
            st.success(f"Jugador {nuevo_nombre} agregado como {nueva_posicion}")
            st.rerun()
    
    st.subheader("Lista de Jugadores")
    
    # Obtener y mostrar la lista de jugadores
    jugadores = obtener_jugadores()
    
    # Crear un DataFrame con columnas adicionales para edición y eliminación
    jugadores_edit = jugadores.copy()
    
    # Mostrar la tabla editable
    edited_df = st.data_editor(
        jugadores_edit,
        hide_index=True,
        column_config={
            "id": None,  # Ocultar la columna ID
            "nombre": "Nombre",
            "posicion": st.column_config.SelectboxColumn(
                "Posición",
                options=["Delantero", "Mediocampista", "Defensor", "Arquero"],
                required=True
            ),
        },
        key="jugadores_table"
    )
    
    # Procesar las ediciones y eliminaciones
    if st.button("Guardar Cambios"):
        for index, row in edited_df.iterrows():
            original_row = jugadores.loc[jugadores['id'] == row['id']].iloc[0]
            if row['nombre'] != original_row['nombre'] or row['posicion'] != original_row['posicion']:
                actualizar_jugador(row['id'], row['nombre'], row['posicion'])
                st.success(f"Jugador {row['nombre']} actualizado.")
        
        st.rerun()  # Recargar la app para mostrar los cambios
    
    # Opción para borrar jugadores
    st.subheader("Borrar Jugadores")
    jugadores_a_borrar = st.multiselect("Selecciona jugadores para borrar", jugadores['nombre'].tolist())
    if st.button("Borrar Jugadores Seleccionados"):
        if jugadores_a_borrar:
            for nombre in jugadores_a_borrar:
                jugador_id = jugadores[jugadores['nombre'] == nombre]['id'].iloc[0]
                borrar_jugador(jugador_id)
                st.success(f"Jugador {nombre} eliminado.")
            st.rerun()  # Recargar la app para mostrar los cambios
        else:
            st.warning("No se seleccionaron jugadores para borrar.")

with tab2:
    st.header("Generar Equipos 👥")
    fecha_generacion = st.date_input("Fecha del partido", key="fecha_generacion")
    jugadores = obtener_jugadores()['nombre'].tolist()
    jugadores_disponibles = st.multiselect("Selecciona los jugadores disponibles", jugadores)
    
    # Mostrar el contador de jugadores seleccionados
    num_jugadores_seleccionados = len(jugadores_disponibles)
    st.write(f"Jugadores seleccionados: {num_jugadores_seleccionados}")
    
    # Calculate max_value based on the number of available players
    max_jugadores_por_equipo = num_jugadores_seleccionados // 2
    
    # Only show the options if there are enough players selected
    if max_jugadores_por_equipo >= 1:
        jugadores_por_equipo = st.number_input("Jugadores por equipo", 
                                               min_value=1, 
                                               max_value=max_jugadores_por_equipo, 
                                               value=min(5, max_jugadores_por_equipo))
        
        # Parámetros adicionales para la generación de equipos
        st.subheader("Parámetros de generación")
        max_defensores = st.number_input("Máximo de defensores por equipo", 
                                         min_value=0, 
                                         max_value=jugadores_por_equipo, 
                                         value=min(4, jugadores_por_equipo))
        min_mediocampistas = st.number_input("Mínimo de mediocampistas por equipo", 
                                             min_value=0, 
                                             max_value=jugadores_por_equipo, 
                                             value=min(1, jugadores_por_equipo))
        min_delanteros = st.number_input("Mínimo de delanteros por equipo", 
                                         min_value=0, 
                                         max_value=jugadores_por_equipo, 
                                         value=min(1, jugadores_por_equipo))
        ponderacion_victorias = st.slider("Ponderación de victorias", 
                                          min_value=0.0, 
                                          max_value=2.0, 
                                          value=1.0, 
                                          step=0.1)

        st.markdown("""
        <p style='color: gray; font-style: italic; font-size: 0.9em;'>
        <strong>Efecto de diferentes valores de ponderación:</strong><br>
        • 1.0 (predeterminado): Equilibrio normal entre victorias de ambos equipos.<br>
        • > 1.0: Mayor énfasis en igualar victorias, posiblemente menos balance en otros aspectos.<br>
        • < 1.0: Menor énfasis en victorias, posiblemente más balance en otros aspectos.<br>
        • 0.0: Ignora completamente el historial de victorias.
        </p>
        """, unsafe_allow_html=True)

        if st.button("Generar Equipos"):
            if len(jugadores_disponibles) < jugadores_por_equipo * 2:
                st.error("No hay suficientes jugadores disponibles para formar dos equipos.")
            else:
                with st.spinner('Generando equipos...'):
                    resultado = generar_equipos_con_progreso(jugadores_disponibles, jugadores_por_equipo, max_defensores, min_mediocampistas, min_delanteros, ponderacion_victorias)
                if resultado is not None:
                    equipos, victorias_equipo1, victorias_equipo2, diferencia_ponderada = resultado
                    equipo1, equipo2 = equipos
                    
                    # Crear DataFrames para cada equipo
                    df_equipo1 = obtener_jugadores()[obtener_jugadores()['nombre'].isin(equipo1)][['nombre', 'posicion']]
                    df_equipo2 = obtener_jugadores()[obtener_jugadores()['nombre'].isin(equipo2)][['nombre', 'posicion']]
                    
                    # Mostrar los equipos en dos columnas
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Equipo 1")
                        st.table(df_equipo1)
                        st.write(f"Victorias totales: {victorias_equipo1}")
                    with col2:
                        st.subheader("Equipo 2")
                        st.table(df_equipo2)
                        st.write(f"Victorias totales: {victorias_equipo2}")
                    
                    st.write(f"Diferencia de victorias (ponderada): {diferencia_ponderada:.2f}")
                    st.write(f"Diferencia de victorias (sin ponderar): {abs(victorias_equipo1 - victorias_equipo2)}")
                    
                    # Guardar los equipos generados
                    guardar_equipos_generados(fecha_generacion, equipo1, equipo2)
                    st.success(f"Equipos generados y guardados para la fecha {fecha_generacion}")
                else:
                    st.error("No se pudo generar equipos que cumplan con todas las restricciones. Intenta con diferentes parámetros o jugadores.")
    else:
        st.warning("Selecciona al menos dos jugadores para generar equipos.")

with tab3:
    st.header("Registrar Partido 📝")
    fecha = st.date_input("Fecha del partido", key="fecha_registro")
    
    # Obtener equipos generados para la fecha seleccionada
    equipos_generados = obtener_equipos_generados()
    equipos_fecha = equipos_generados[equipos_generados['fecha'] == str(fecha)]
    
    if not equipos_fecha.empty:
        st.write("Equipos generados para esta fecha:")
        equipo1 = equipos_fecha.iloc[0]['equipo1'].split(',')
        equipo2 = equipos_fecha.iloc[0]['equipo2'].split(',')
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Equipo 1")
            st.write(", ".join(equipo1))
        with col2:
            st.subheader("Equipo 2")
            st.write(", ".join(equipo2))
        
        usar_equipos_generados = st.checkbox("Usar estos equipos")
    else:
        st.write("No hay equipos generados para esta fecha. Puedes seleccionar los jugadores manualmente.")
        usar_equipos_generados = False
    
    if not usar_equipos_generados:
        jugadores = obtener_jugadores()['nombre'].tolist()
        equipo1 = st.multiselect("Equipo 1", jugadores, key='eq1')
        equipo2 = st.multiselect("Equipo 2", jugadores, key='eq2')
    
    goles1 = st.number_input("Goles Equipo 1", min_value=0, step=1)
    goles2 = st.number_input("Goles Equipo 2", min_value=0, step=1)
    
    if st.button("Registrar Partido"):
        registrar_partido(fecha, equipo1, equipo2, goles1, goles2)
        st.success("Partido registrado exitosamente")

with tab4:
    st.header("Tabla de Posiciones 🥇")
    
    estadisticas = obtener_estadisticas_jugadores()
    
    if estadisticas.empty:
        st.write("No hay datos de partidos para mostrar en la tabla de posiciones.")
    else:
        # Ordenar por porcentaje de victorias (descendente) y luego por partidos jugados (descendente)
        estadisticas = estadisticas.sort_values(by=['porcentaje_victorias', 'partidos_jugados'], ascending=[False, False])
        
        # Agregar columna de posición
        estadisticas['posicion'] = range(1, len(estadisticas) + 1)
        
        # Reordenar las columnas para que 'posicion' sea la primera
        estadisticas = estadisticas[['posicion'] + [col for col in estadisticas.columns if col != 'posicion']]
        
        # Detectar el tema actual
        is_dark_theme = st.get_option("theme.base") == "dark"
        
        # Función para aplicar el degradado de colores
        def color_scale(val):
            if pd.isna(val):
                return ''
            min_val = estadisticas['porcentaje_victorias'].min()
            max_val = estadisticas['porcentaje_victorias'].max()
            
            # Evitar división por cero
            if min_val == max_val:
                r, g = 0, 0
            else:
                # Crear un degradado de rojo (bajo) a verde (alto)
                r = max((max_val - val) / (max_val - min_val), 0)
                g = max((val - min_val) / (max_val - min_val), 0)
            b = 0
            
            # Ajustar la opacidad y el color del texto según el tema
            if is_dark_theme:
                return f'background-color: rgba({int(r*255)}, {int(g*255)}, {int(b*255)}, 0.7); color: white;'
            else:
                return f'background-color: rgba({int(r*255)}, {int(g*255)}, {int(b*255)}, 0.3); color: black;'
        
        # Aplicar estilos a la tabla
        styled_table = (estadisticas.style
            .applymap(color_scale, subset=['porcentaje_victorias'])
            .format({
                'posicion': '{:.0f}',  # Formato para la nueva columna de posición
                'porcentaje_victorias': '{:.2f}%',
                'victorias': '{:.0f}',
                'partidos_jugados': '{:.0f}'
            })
            .set_properties(**{
                'font-weight': 'bold',
                'text-align': 'center'
            })
            .set_table_styles([
                {'selector': 'th', 'props': [
                    ('background-color', '#4A4A4A' if is_dark_theme else '#E6E6E6'), 
                    ('color', 'white' if is_dark_theme else 'black')
                ]},
                {'selector': 'td', 'props': [('border', '1px solid #4A4A4A' if is_dark_theme else '1px solid #E6E6E6')]},
            ])
        )
        
        # Mostrar la tabla
        st.dataframe(styled_table, hide_index=True, height=400)

with tab5:
    st.header("Historial de Partidos 🏟️")
    
    partidos = obtener_partidos()
    
    if not partidos.empty:
        for _, partido in partidos.iterrows():
            with st.expander(f"Partido del {partido['fecha']} - {partido['equipo1'].split(',')[0]} vs {partido['equipo2'].split(',')[0]}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("**Equipo 1:**")
                    st.write(", ".join(partido['equipo1'].split(',')))
                with col2:
                    st.write("**Resultado:**")
                    st.write(f"{partido['goles1']} - {partido['goles2']}")
                with col3:
                    st.write("**Equipo 2:**")
                    st.write(", ".join(partido['equipo2'].split(',')))
                
                if st.button("Borrar Partido", key=f"borrar_{partido['id']}"):
                    borrar_partido(partido['id'])
                    st.success("Partido borrado exitosamente. Recarga la página para ver los cambios.")
    else:
        st.write("No hay partidos registrados.")

# Cerrar conexión
conn.close()
