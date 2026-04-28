import streamlit as st
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import math
import io

# Configuración de la página
st.set_page_config(page_title="Protector Anti-IA Avanzado", layout="centered")

st.title("🛡️ Generador de Marca de Agua Curvada (Anti-IA)")
st.write("Aplica deformación espacial al texto, malla anti-OCR y ruido adversarial para proteger documentos sensibles.")

# ==========================================
# 1. CONTROLES DE LA INTERFAZ (BARRA LATERAL)
# ==========================================
st.sidebar.header("Ajustes de la Marca de Agua")
watermark_text = st.sidebar.text_input("Texto", "USO EXCLUSIVO TRÁMITE 2026")
tamano_letra = st.sidebar.slider("Tamaño base de letra", 10, 100, 30)

# Permitimos valores negativos para juntar mucho el patrón
separacion_lineas = st.sidebar.slider("Separación entre líneas", -50, 200, 0)
separacion_texto = st.sidebar.slider("Separación horizontal del texto", -50, 200, 10)

st.sidebar.header("Ajustes de Deformación (Ondas)")
angulo_rotacion = st.sidebar.slider("Ángulo de inclinación", -90, 90, 45)
amplitud_onda = st.sidebar.slider("Fuerza de la curva (Amplitud)", 0, 100, 30)
longitud_onda = st.sidebar.slider("Ancho de la curva (Frecuencia)", 10, 300, 100)

st.sidebar.header("Seguridad y Visualización")
opacidad = st.sidebar.slider("Opacidad de la marca", 10, 255, 120)
ruido_ai = st.sidebar.checkbox("Añadir Ruido Adversarial", value=True)
intensidad_ruido_ajustada = st.sidebar.slider("Intensidad del Ruido", 10, 150, 50)

st.sidebar.header("Pie de Página Legal")
texto_footer = st.sidebar.text_input("Texto de la barra inferior", watermark_text) 
tamano_letra_footer = st.sidebar.slider("Tamaño de letra (Barra inferior)", 10, 100, 25)

# ==========================================
# 2. LÓGICA PRINCIPAL DE PROCESAMIENTO
# ==========================================
uploaded_file = st.file_uploader("Sube el DNI o Documento", type=["png", "jpg", "jpeg"])

if uploaded_file and watermark_text:
    # Cargar imagen original
    original_img = Image.open(uploaded_file).convert("RGBA")
    width, height = original_img.size

    # --- CALCULAR FACTOR DE ESCALA ---
    # Esto asegura que los efectos se vean igual en fotos pequeñas o gigantes (4K)
    escala = max(width, height) / 1000.0

    t_letra_real = max(10, int(tamano_letra * escala))
    sep_lineas_real = int(separacion_lineas * escala)
    sep_texto_real = int(separacion_texto * escala)
    
    amp_onda_real = amplitud_onda * escala
    long_onda_real = max(1, longitud_onda * escala)
    
    t_letra_footer_real = max(10, int(tamano_letra_footer * escala))
    
    espaciado_malla_real = max(2, int(4 * escala))
    grosor_linea_real = max(1, int(1 * escala))
    # ---------------------------------

    original_cv = np.array(original_img)

    # --- BLOQUE MALLA ANTI-OCR (SCANLINES) ---
    # Creamos un lienzo transparente para la malla
    capa_malla = np.zeros_like(original_cv)
    
    # Dibujamos líneas horizontales oscuras
    for y in range(0, height, espaciado_malla_real):
        cv2.line(capa_malla, (0, y), (width, y), (30, 30, 30, 255), grosor_linea_real)
        
    # Añadimos algo de ruido de "Sal y Pimienta" solo a la malla para romper patrones perfectos
    ruido_sal_pimienta = np.random.randint(0, 2, capa_malla.shape[:2]) * 255
    mascara_ruido = ruido_sal_pimienta > 200
    capa_malla[mascara_ruido] = [0, 0, 0, 255] # Píxeles negros aleatorios
    
    # Fusionamos la malla con el DNI original con una opacidad del 30%
    opacidad_malla = 0.3
    for c in range(3):
        original_cv[:, :, c] = cv2.addWeighted(original_cv[:, :, c], 1.0, capa_malla[:, :, c], opacidad_malla, 0)
    # --- FIN DEL BLOQUE MALLA ---

    # --- BLOQUE MARCA DE AGUA ONDULADA Y ROTADA ---
    # Calcular el tamaño de un lienzo GIGANTE seguro para la rotación (Teorema de Pitágoras)
    diagonal = int(math.hypot(width, height))
    canvas_size = diagonal + int(400 * escala) # Margen extra de seguridad escalado
    
    txt_layer = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    # Cargar fuente principal escalada
    try:
        font = ImageFont.truetype("arial.ttf", t_letra_real)
    except IOError:
        font = ImageFont.load_default()

    # Calcular anchos y pasos
    try:
        text_width = int(font.getlength(watermark_text))
    except AttributeError:
        text_width = len(watermark_text) * (t_letra_real // 2)

    # Usamos max(10, ...) para evitar bucles infinitos si el usuario pone valores negativos muy altos
    step_x = max(10, text_width + sep_texto_real)
    step_y = max(10, t_letra_real + sep_lineas_real)

    # Llenamos todo el lienzo gigante (Texto Recto)
    for y in range(0, canvas_size, step_y):
        offset_x = (y // step_y % 2) * (step_x // 2) 
        for x in range(-int(200*escala), canvas_size, step_x):
            draw.text((x + offset_x, y), watermark_text, font=font, fill=(50, 50, 50, opacidad))

    txt_cv = np.array(txt_layer)

    # La Magia 1: Deformación Espacial (Ondas)
    X, Y = np.meshgrid(np.arange(canvas_size), np.arange(canvas_size))
    map_x = X.astype(np.float32)
    map_y = (Y + amp_onda_real * np.sin(X / long_onda_real)).astype(np.float32)

    warped_txt = cv2.remap(txt_cv, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # La Magia 2: Rotación al ángulo seleccionado
    centro_lienzo = (canvas_size // 2, canvas_size // 2)
    M = cv2.getRotationMatrix2D(centro_lienzo, angulo_rotacion, 1.0)
    rotated_txt = cv2.warpAffine(warped_txt, M, (canvas_size, canvas_size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # Recortar el centro exacto para volver al tamaño del documento original
    start_x = centro_lienzo[0] - width // 2
    start_y = centro_lienzo[1] - height // 2
    warped_txt_cropped = rotated_txt[start_y:start_y+height, start_x:start_x+width]

    # --- DEFENSAS AVANZADAS ANTI-INPAINTING IA ---
    
    # A. Desenfoque de Bordes (Feathering)
    # Suaviza los bordes para que la IA no pueda crear una máscara de selección perfecta.
    radio_desenfoque = max(3, int(5 * escala)) | 1 # Aseguramos que sea impar
    warped_txt_cropped = cv2.GaussianBlur(warped_txt_cropped, (radio_desenfoque, radio_desenfoque), 0)

    # B. Aberración Cromática (Separación RGB)
    # Desplazamos los colores para destruir la correlación de píxeles que buscan los LLM visuales
    desplazamiento = max(2, int(4 * escala))
    
    # Separamos los canales (En OpenCV el orden es Blue, Green, Red, Alpha)
    b, g, r, a = cv2.split(warped_txt_cropped)
    
    # Creamos matrices de transformación para mover los colores
    # Movemos el ROJO a la derecha y abajo
    M_r = np.float32([[1, 0, desplazamiento], [0, 1, desplazamiento]])
    r_shifted = cv2.warpAffine(r, M_r, (r.shape[1], r.shape[0]))
    
    # Movemos el AZUL a la izquierda y arriba
    M_b = np.float32([[1, 0, -desplazamiento], [0, 1, -desplazamiento]])
    b_shifted = cv2.warpAffine(b, M_b, (b.shape[1], b.shape[0]))
    
    # Volvemos a fusionar los canales desplazados manteniendo el verde intacto
    warped_txt_cropped = cv2.merge((b_shifted, g, r_shifted, a))
    
    # --- FIN DEFENSAS AVANZADAS ---

    # Aplicar Ruido Adversarial solo a las letras (Anti-Inpainting IA)
    if ruido_ai:
        std_dev = (opacidad / 255.0) * intensidad_ruido_ajustada 
        ruido = np.random.normal(0, std_dev, warped_txt_cropped.shape).astype(np.float32)
        
        # Máscara basada en el canal alfa (transparencia) del texto
        mask_alpha = warped_txt_cropped[:, :, 3] / 255.0
        
        for c in range(3):
            temp_channel = warped_txt_cropped[:, :, c].astype(np.float32)
            temp_channel += ruido[:, :, c] * mask_alpha
            warped_txt_cropped[:, :, c] = np.clip(temp_channel, 0, 255).astype(np.uint8)

    # Fusionar Capa de Texto con Imagen Original (que ya tiene la malla)
    alpha_text = warped_txt_cropped[:, :, 3] / 255.0
    alpha_inv = 1.0 - alpha_text

    resultado_cv = np.zeros_like(original_cv)
    for c in range(3): 
        resultado_cv[:, :, c] = (alpha_text * warped_txt_cropped[:, :, c] + alpha_inv * original_cv[:, :, c])
    
    resultado_cv[:, :, 3] = original_cv[:, :, 3] # Mantener el alpha original

    final_image = Image.fromarray(resultado_cv)
    # --- FIN BLOQUE MARCA DE AGUA ---

    # --- BLOQUE BARRA INFERIOR LEGAL ---
    try:
        font_footer = ImageFont.truetype("arial.ttf", t_letra_footer_real)
    except IOError:
        font_footer = ImageFont.load_default()

    alto_barra = t_letra_footer_real + int(40 * escala)  
    ancho_final, alto_original = final_image.size
    nuevo_alto = alto_original + alto_barra

    # Crear lienzo expandido
    imagen_con_barra = Image.new("RGBA", (ancho_final, nuevo_alto), (255, 255, 255, 255))
    imagen_con_barra.paste(final_image, (0, 0))

    # Dibujar rectángulo oscuro en la base
    draw_footer = ImageDraw.Draw(imagen_con_barra)
    draw_footer.rectangle([0, alto_original, ancho_final, nuevo_alto], fill=(40, 40, 40, 255))

    # Centrar texto del footer
    try:
        w_text_footer = int(font_footer.getlength(texto_footer))
    except:
        w_text_footer = len(texto_footer) * (t_letra_footer_real // 2)
    
    pos_x = (ancho_final - w_text_footer) // 2
    pos_y = alto_original + (alto_barra - t_letra_footer_real) // 2 - int(5 * escala)

    draw_footer.text((pos_x, pos_y), texto_footer, font=font_footer, fill=(255, 255, 255, 255))
    
    final_image = imagen_con_barra
    # --- FIN BLOQUE BARRA INFERIOR ---

    # ==========================================
    # 3. MOSTRAR RESULTADOS Y DESCARGA
    # ==========================================
    # Mostramos la imagen ocupando el ancho del contenedor (Actualizado para Streamlit moderno)
    st.image(final_image, caption="Documento Protegido Listamente", use_container_width=True)

    # Preparar para descarga en formato JPG (Requiere RGB)
    final_rgb = final_image.convert("RGB")
    buf = io.BytesIO()
    final_rgb.save(buf, format="JPEG", quality=95)
    byte_im = buf.getvalue()

    st.download_button(
        label="📥 Descargar Documento Protegido",
        data=byte_im,
        file_name="documento_protegido_seguro.jpg",
        mime="image/jpeg"
    )