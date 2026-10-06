import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Slider, TextBox, Button

# --- CONFIGURACIÓN ANTROPOMÉTRICA (Zatsiorsky / Dempster) ---
P_TRONCO = 0.50
P_MUSLO = 0.10
P_PIERNA = 0.045
P_PIE = 0.015
P_CABEZA = 0.08
P_BRAZOS = 0.10  # Masa de ambos brazos

L_TRONCO_RATIO = 0.288
L_MUSLO_RATIO = 0.245
L_PIERNA_RATIO = 0.246
L_BRAZO_RATIO = 0.35 

CM_TRONCO = 0.44
CM_MUSLO = 0.433
CM_PIERNA = 0.433
CM_PIE = 0.50
CM_BRAZO = 0.45 

# --- PALETA DE COLORES "SPORT-TECH" ---
COLOR_BG = '#1A1A1A'        # Gris Carbón del Libro
COLOR_VOLT = '#39FF14'      # Verde Volt Deportivo
COLOR_TECHBLUE = '#00E5FF'  # Azul Eléctrico (Tronco)
COLOR_NEON_RED = '#FF1744'  # Rojo Neón (Muslo)
COLOR_NEON_ORG = '#FF5722'  # Naranja Eléctrico (Pierna)
COLOR_GRAY_DARK = '#2D2D2D' # Fondo de Sliders
COLOR_WHITE = '#FFFFFF'     # Texto y Articulaciones

# Estado global para visibilidad de los detalles gráficos
mostrar_detalles = True

def calcular_fuerza_precisa(torque_neto, theta_lean_deg):
    r_ins = 0.146  
    alpha_deg = 25.0  
    alpha_rad = np.radians(alpha_deg)
    brazo_momento_interno = r_ins * np.sin(alpha_rad)
    fuerza = torque_neto / brazo_momento_interno
    return fuerza

def calcular_planche(peso_total, altura, ang_straddle, ang_cadera, ang_rodilla):
    rad_straddle = np.radians(ang_straddle) / 2
    rad_cadera = np.radians(ang_cadera)
    rad_rodilla = np.radians(ang_rodilla)

    l_tronco = altura * L_TRONCO_RATIO
    l_muslo = altura * L_MUSLO_RATIO
    l_pierna = altura * L_PIERNA_RATIO
    l_brazo = altura * L_BRAZO_RATIO * 0.9 

    # --- CÁLCULO DEL CG CUERPO (SIN BRAZOS) RELATIVO AL HOMBRO ---
    m_tronco = peso_total * P_TRONCO
    m_muslo = peso_total * P_MUSLO * 2
    m_pierna = peso_total * P_PIERNA * 2
    m_pie = peso_total * P_PIE * 2
    m_cabeza = peso_total * P_CABEZA
    m_brazos = peso_total * P_BRAZOS
    
    x_cabeza = -0.15 
    x_tronco = l_tronco * CM_TRONCO
    x_muslo = l_tronco + (l_muslo * CM_MUSLO * np.cos(rad_cadera) * np.cos(rad_straddle))
    dist_rodilla_x = l_tronco + (l_muslo * np.cos(rad_cadera))
    x_pierna = dist_rodilla_x + (l_pierna * CM_PIERNA * np.cos(rad_cadera - rad_rodilla) * np.cos(rad_straddle))
    x_pie = dist_rodilla_x + (l_pierna * np.cos(rad_cadera - rad_rodilla) * np.cos(rad_straddle))
    
    suma_momentos_cuerpo = (m_cabeza*x_cabeza) + (m_tronco*x_tronco) + (m_muslo*x_muslo) + (m_pierna*x_pierna) + (m_pie*x_pie)
    masa_cuerpo = m_cabeza + m_tronco + m_muslo + m_pierna + m_pie
    d_cg_cuerpo = suma_momentos_cuerpo / masa_cuerpo
    
    # Inclinación (Lean) para equilibrio
    ratio = d_cg_cuerpo / l_brazo
    if ratio > 1: ratio = 1
    theta_rad = np.arcsin(ratio)
    theta_deg = np.degrees(theta_rad)
    
    hombro_x = -d_cg_cuerpo
    hombro_y = l_brazo * np.cos(theta_rad)
    
    # --- MOMENTOS DE FUERZA EN EL BRAZO ---
    g = 9.81
    torque_suelo = (peso_total * g) * d_cg_cuerpo
    dist_horizontal_cm_brazo = (l_brazo * CM_BRAZO) * np.sin(theta_rad)
    torque_brazo = m_brazos * g * dist_horizontal_cm_brazo
    torque_neto = torque_suelo - torque_brazo
    
    f_deltoides = calcular_fuerza_precisa(torque_neto, theta_deg)
    
    # COORDENADAS COMPLETAS
    cadera_x, cadera_y = hombro_x + l_tronco, hombro_y
    rodilla_x = cadera_x + l_muslo * np.cos(rad_cadera)
    rodilla_y = cadera_y - l_muslo * np.sin(rad_cadera)
    tobillo_x = rodilla_x + l_pierna * np.cos(rad_cadera - rad_rodilla)
    tobillo_y = rodilla_y - l_pierna * np.sin(rad_cadera - rad_rodilla)
    
    cm_brazo_x = hombro_x + (0 - hombro_x) * CM_BRAZO
    cm_brazo_y = hombro_y + (0 - hombro_y) * CM_BRAZO

    coords = {
        'muñeca': (0,0), 'hombro': (hombro_x, hombro_y),
        'cadera': (cadera_x, cadera_y), 'rodilla': (rodilla_x, rodilla_y),
        'tobillo': (tobillo_x, tobillo_y),
        'cg': (0, hombro_y), 'cm_brazo': (cm_brazo_x, cm_brazo_y)
    }
    
    datos = {
        'd_cg': d_cg_cuerpo, 'theta': theta_deg, 'torque_suelo': torque_suelo,
        'f_deltoides': f_deltoides, 'torque_neto': torque_neto, 'torque_brazo': torque_brazo
    }
    return coords, datos

# --- CONFIGURACIÓN DE LA INTERFAZ CON ESTILO SPORT-TECH ---
plt.style.use('dark_background') # Configura el tema oscuro nativo
fig, ax = plt.subplots(figsize=(15, 9), facecolor=COLOR_BG)
plt.subplots_adjust(left=0.1, bottom=0.35, right=0.9, top=0.95)

y_base, y_step = 0.04, 0.05

# Configuración de Sliders oscuros con barra en verde Volt
s_peso = Slider(plt.axes([0.15, y_base + 4*y_step, 0.55, 0.025], facecolor=COLOR_GRAY_DARK), 'Peso (kg)', 50.0, 110.0, valinit=81.0, color=COLOR_VOLT)
s_peso.label.set_color(COLOR_WHITE)
s_peso.valtext.set_color(COLOR_WHITE)

s_alt = Slider(plt.axes([0.15, y_base + 3*y_step, 0.55, 0.025], facecolor=COLOR_GRAY_DARK), 'Altura (m)', 1.50, 2.10, valinit=1.84, color=COLOR_VOLT)
s_alt.label.set_color(COLOR_WHITE)
s_alt.valtext.set_color(COLOR_WHITE)

s_str = Slider(plt.axes([0.15, y_base + 2*y_step, 0.55, 0.025], facecolor=COLOR_GRAY_DARK), 'Straddle (deg)', 0.0, 180.0, valinit=120.0, color=COLOR_VOLT)
s_str.label.set_color(COLOR_WHITE)
s_str.valtext.set_color(COLOR_WHITE)

s_cad = Slider(plt.axes([0.15, y_base + 1*y_step, 0.55, 0.025], facecolor=COLOR_GRAY_DARK), 'Cadera (deg)', 0.0, 120.0, valinit=0.0, color=COLOR_VOLT)
s_cad.label.set_color(COLOR_WHITE)
s_cad.valtext.set_color(COLOR_WHITE)

s_rod = Slider(plt.axes([0.15, y_base, 0.55, 0.025], facecolor=COLOR_GRAY_DARK), 'Rodilla (deg)', 0.0, 120.0, valinit=0.0, color=COLOR_VOLT)
s_rod.label.set_color(COLOR_WHITE)
s_rod.valtext.set_color(COLOR_WHITE)

# Cajas de texto a la derecha con estilo unificado y asignación de color compatible
tb_peso = TextBox(plt.axes([0.75, y_base + 4*y_step, 0.08, 0.025]), '', initial="81.0", color=COLOR_GRAY_DARK)
tb_peso.text_disp.set_color(COLOR_WHITE)

tb_alt = TextBox(plt.axes([0.75, y_base + 3*y_step, 0.08, 0.025]), '', initial="1.84", color=COLOR_GRAY_DARK)
tb_alt.text_disp.set_color(COLOR_WHITE)

tb_str = TextBox(plt.axes([0.75, y_base + 2*y_step, 0.08, 0.025]), '', initial="120", color=COLOR_GRAY_DARK)
tb_str.text_disp.set_color(COLOR_WHITE)

tb_cad = TextBox(plt.axes([0.75, y_base + 1*y_step, 0.08, 0.025]), '', initial="0", color=COLOR_GRAY_DARK)
tb_cad.text_disp.set_color(COLOR_WHITE)

tb_rod = TextBox(plt.axes([0.75, y_base, 0.08, 0.025]), '', initial="0", color=COLOR_GRAY_DARK)
tb_rod.text_disp.set_color(COLOR_WHITE)

# Botón interactivo para ocultar vectores y telemetrías (Ideal para capturas de pantalla)
btn_ax = plt.axes([0.84, y_base + 2*y_step, 0.12, 0.04])
btn_toggle = Button(btn_ax, 'Ocultar Detalles', color=COLOR_GRAY_DARK, hovercolor='#3D3D3D')
btn_toggle.label.set_color(COLOR_WHITE)
btn_toggle.label.set_fontweight('bold')

def update(val):
    global mostrar_detalles
    ax.clear()
    
    # Forzar fondo y estilo oscuro estable en cada refresco de pantalla
    ax.set_facecolor(COLOR_BG)
    for spine in ax.spines.values():
        spine.set_color('#333333')
    ax.tick_params(colors=COLOR_WHITE)
    ax.grid(True, color='#2D2D2D', linestyle='--', linewidth=0.5)
    
    # Obtención de cálculos
    c, d = calcular_planche(s_peso.val, s_alt.val, s_str.val, s_cad.val, s_rod.val)
    
    # --- LÍNEA DE ALINEACIÓN BIOMECÁNICA (Siempre visible, no oculta por el botón) ---
    # Traza un vector discontinuo vertical en x=0 (eje de equilibrio que une apoyo y CG)
    ax.axvline(0, color=COLOR_VOLT, linestyle='--', lw=1.5, alpha=0.5, zorder=2)
    
    # Dibujo de segmentos con colores neón de alto contraste
    ax.plot([c['muñeca'][0], c['hombro'][0]], [c['muñeca'][1], c['hombro'][1]], color='#FFFFFF', lw=5, label='Brazo (Soporte)', zorder=5)
    ax.plot([c['hombro'][0], c['cadera'][0]], [c['hombro'][1], c['cadera'][1]], color=COLOR_TECHBLUE, lw=8, label='Torso', zorder=4)
    ax.plot([c['cadera'][0], c['rodilla'][0]], [c['cadera'][1], c['rodilla'][1]], color=COLOR_NEON_RED, lw=7, label='Muslo', zorder=3)
    ax.plot([c['rodilla'][0], c['tobillo'][0]], [c['rodilla'][1], c['tobillo'][1]], color=COLOR_NEON_ORG, lw=5, label='Pierna', zorder=3)
    
    # Articulaciones limpias (Círculos blancos con reborde oscuro)
    for p in ['hombro', 'cadera', 'rodilla', 'tobillo']:
        ax.plot(c[p][0], c[p][1], 'o', color=COLOR_WHITE, markeredgecolor=COLOR_BG, ms=8, zorder=6)
    
    # Centros de Masas del cuerpo y brazo
    ax.plot(c['cg'][0], c['cg'][1], 'o', color=COLOR_VOLT, markeredgecolor=COLOR_WHITE, ms=12, label='CG Cuerpo', zorder=10)
    ax.plot(c['cm_brazo'][0], c['cm_brazo'][1], 'o', color='darkgreen', markeredgecolor=COLOR_WHITE, ms=8, label='CM Brazo', zorder=10)
    ax.axhline(0, color='#444444', lw=2)
    
    # Dibujar vectores y telemetrías únicamente si está activado el botón
    if mostrar_detalles:
        # Escala reducida de vectores para un look más discreto y estilizado
        v_scale = 0.22
        
        # Fuerza Normal (Púrpura Neón)
        ax.arrow(0, 0, 0, v_scale, head_width=0.03, fc='#D500F9', ec='#D500F9', lw=2, label='F. Normal', zorder=7)
        # Peso Brazo (Cyan Eléctrico)
        ax.arrow(c['cm_brazo'][0], c['cm_brazo'][1], 0, -v_scale*0.6, head_width=0.03, fc='#00B0FF', ec='#00B0FF', lw=2, label='Peso Brazo', zorder=7)
        
        # Vector de fuerza del Deltoides Anterior (Naranja Eléctrico, ángulo α=25°)
        brazo_dir = np.array([c['hombro'][0] - c['muñeca'][0], c['hombro'][1] - c['muñeca'][1]]) # Vector desde muñeca (0,0) a hombro
        brazo_dir /= np.linalg.norm(brazo_dir)
        rot = np.array([[np.cos(np.radians(25)), -np.sin(np.radians(25))], [np.sin(np.radians(25)), np.cos(np.radians(25))]])
        delt_dir = rot @ brazo_dir
        ins_p = np.array(c['hombro']) + (np.array(c['muñeca']) - np.array(c['hombro'])) * 0.3 # Punto de inserción a 30% del hombro
        ax.arrow(ins_p[0], ins_p[1], delt_dir[0]*v_scale, delt_dir[1]*v_scale, head_width=0.03, fc='orange', ec='orange', lw=2, label='F. Deltoides', zorder=7)

        # Cuadro Informativo de Ingeniería (Fuerza del Deltoides expresada directamente en Newtons)
        info = (f"Torque Suelo: {d['torque_suelo']:.1f} Nm\n"
                f"Torque Ayuda Brazo: {d['torque_brazo']:.1f} Nm\n"
                f"TORQUE NETO HOMBRO: {d['torque_neto']:.1f} Nm\n"
                f"FUERZA DELTOIDES: {d['f_deltoides']:.1f} N\n"
                f"LEAN (Inclinación): {d['theta']:.1f}°")
        
        info_box_style = dict(boxstyle='round,pad=0.5', facecolor='#1F1F1F', edgecolor=COLOR_VOLT, lw=1.2)
        ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=10, fontfamily='monospace', verticalalignment='top', color=COLOR_WHITE, bbox=info_box_style)

        # Ubicación de la leyenda en la parte superior derecha (Upper Right)
        ax.legend(loc='upper right', fontsize='small', facecolor='#111111', framealpha=0.9, edgecolor='gray')

    ax.set_xlim(-0.8, 1.8)
    ax.set_ylim(-0.2, 1.2)
    ax.set_aspect('equal')

# Función Callback para el Botón de Ocultar/Mostrar
def toggle_detalles(event):
    global mostrar_detalles
    mostrar_detalles = not mostrar_detalles
    if mostrar_detalles:
        btn_toggle.label.set_text('Ocultar Detalles')
    else:
        btn_toggle.label.set_text('Mostrar Detalles')
    update(0)
    plt.draw()

btn_toggle.on_clicked(toggle_detalles)

# Callbacks de sincronización e inicio de bucle
def make_submit(s): return lambda text: [s.set_val(float(text)) if text else None]
tb_peso.on_submit(make_submit(s_peso)); tb_alt.on_submit(make_submit(s_alt))
tb_str.on_submit(make_submit(s_str)); tb_cad.on_submit(make_submit(s_cad)); tb_rod.on_submit(make_submit(s_rod))
s_peso.on_changed(update); s_alt.on_changed(update); s_str.on_changed(update); s_cad.on_changed(update); s_rod.on_changed(update)

update(0)
plt.show()