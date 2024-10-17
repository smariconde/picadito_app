import streamlit as st
import sqlite3
import pandas as pd
import random
from itertools import combinations

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
    return pd.read_sql_query("SELECT * FROM jugadores", conn)

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

# Interfaz de Streamlit
st.title('Picadito App ⚽')

tab1, tab2, tab3, tab4 = st.tabs(["Jugadores", "Generar Equipos", "Registrar Partido", "Posiciones"])

with tab1:
    st.header("Registro de Jugadores 👤")
    nombre = st.text_input("Nombre del jugador")
    posicion = st.selectbox("Posición", ["Delantero", "Mediocampista", "Defensor", "Arquero"])
    if st.button("Agregar Jugador"):
        agregar_jugador(nombre, posicion)
        st.success(f"Jugador {nombre} agregado como {posicion}")
    
    st.subheader("Lista de Jugadores")
    st.dataframe(obtener_jugadores())

with tab2:
    st.header("Generar Equipos 👥")
    fecha_generacion = st.date_input("Fecha del partido", key="fecha_generacion")
    jugadores = obtener_jugadores()['nombre'].tolist()
    jugadores_disponibles = st.multiselect("Selecciona los jugadores disponibles", jugadores)
    
    # Mostrar el contador de jugadores seleccionados
    st.write(f"Jugadores seleccionados: {len(jugadores_disponibles)}")
    
    # Calculate max_value based on the number of available players
    max_jugadores_por_equipo = len(jugadores_disponibles) // 2
    
    # Only show the number input if there are enough players selected
    if max_jugadores_por_equipo > 0:
        jugadores_por_equipo = st.number_input("Jugadores por equipo", 
                                               min_value=1, 
                                               max_value=max_jugadores_por_equipo, 
                                               value=min(5, max_jugadores_por_equipo))
        
        # Parámetros adicionales para la generación de equipos
        st.subheader("Parámetros de generación")
        max_defensores = st.number_input("Máximo de defensores por equipo", min_value=0, max_value=jugadores_por_equipo, value=4)
        min_mediocampistas = st.number_input("Mínimo de mediocampistas por equipo", min_value=0, max_value=jugadores_por_equipo, value=1)
        min_delanteros = st.number_input("Mínimo de delanteros por equipo", min_value=0, max_value=jugadores_por_equipo, value=1)
        ponderacion_victorias = st.slider("Ponderación de victorias", min_value=0.0, max_value=2.0, value=1.0, step=0.1)
        
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
    
    # Ordenar por porcentaje de victorias (descendente) y luego por partidos jugados (descendente)
    estadisticas = estadisticas.sort_values(by=['porcentaje_victorias', 'partidos_jugados'], ascending=[False, False])
    
    # Función para aplicar colores alternados a las filas
    def highlight_rows(row):
        if row.name % 2 == 0:
            return ['background-color: #f2f2f2'] * len(row)
        else:
            return ['background-color: white'] * len(row)
    
    # Mostrar la tabla de posiciones con estilos
    st.dataframe(estadisticas.style
                 .apply(highlight_rows, axis=1)
                 .highlight_max(subset=['victorias', 'partidos_jugados', 'porcentaje_victorias'], color='lightgreen')
                 .format({'porcentaje_victorias': '{:.2f}%'})
                 .set_properties(**{'text-align': 'center'})
                 .set_table_styles([dict(selector='th', props=[('text-align', 'center')])])
                )

# Cerrar conexión
conn.close()
