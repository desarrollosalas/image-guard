import streamlit as st
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import math

st.set_page_config(page_title="Protector Anti-IA Avanzado", layout="centered")

st.title("🛡️ Generador de Marca de Agua Curvada (Anti-IA)")
st.write("Aplica deformación espacial al texto para crear verdaderos patrones de ondas.")

# 1. Controles de la interfaz en una barra lateral para mayor comodidad
st.sidebar.header("Ajustes de la Marca de Agua")
watermark_text = st.sidebar.text_input("Texto", "USO EXCLUSIVO TRÁMITE 2026")
tamano_letra = st.sidebar.slider("Tamaño de letra", 10, 100, 10)

separacion_lineas = st.sidebar.slider("Separación entre líneas", 0, 200, 0)
separacion_texto = st.sidebar.slider("Separación horizontal del texto", 0, 200, 0)

st.sidebar.header("Ajustes de Deformación (Ondas)")
angulo_rotacion = st.sidebar.slider("Ángulo de inclinación", -90, 90, 45)
amplitud_onda = st.sidebar.slider("Fuerza de la curva (Amplitud)", 0, 100, 30)
longitud_onda = st.sidebar.slider("Ancho de la curva (Frecuencia)", 10, 300, 100)

st.sidebar.header("Seguridad y Visualización")
opacidad = st.sidebar.slider("Opacidad", 10, 255, 120)
ruido_ai = st.sidebar.checkbox("Añadir Ruido Adversarial", value=True)
intensidad_ruido_ajustada = st.sidebar.slider("Intensidad del Ruido", 10, 150, 50)

st.sidebar.header("Pie de Página Legal")
texto_footer = st.sidebar.text_input("Texto de la barra inferior", watermark_text) 
tamano_letra_footer = st.sidebar.slider("Tamaño de letra (Barra inferior)", 10, 100, 25)

uploaded_file = st.file_uploader("Sube el DNI o Documento", type=["png", "jpg", "jpeg"])

if uploaded_file and watermark_text:
    # 2. Cargar imagen original
    original_img = Image.open(uploaded_file).convert("RGBA")
    width, height = original_img.size

    # --- BLOQUE MALLA ANTI-OCR (SCANLINES) ---
    original_cv = np.array(original_img)
    
    # Configuramos la malla
    grosor_linea = 1
    espaciado_malla = 4 # Una línea cada 4 píxeles. Si el DNI es muy grande, sube a 6 u 8.
    
    # Creamos un lienzo transparente para la malla
    capa_malla = np.zeros_like(original_cv)
    
    # Dibujamos líneas horizontales oscuras
    for y in range(0, height, espaciado_malla):
        cv2.line(capa_malla, (0, y), (width, y), (30, 30, 30, 255), grosor_linea)
        
    # Añadimos algo de ruido de "Sal y Pimienta" solo a la malla para romper patrones perfectos
    ruido_sal_pimienta = np.random.randint(0, 2, capa_malla.shape[:2]) * 255
    mascara_ruido = ruido_sal_pimienta > 200
    capa_malla[mascara_ruido] = [0, 0, 0, 255] # Píxeles negros aleatorios
    
    # Fusionamos la malla con el DNI original con una opacidad del 30%
    opacidad_malla = 0.3
    for c in range(3):
        original_cv[:, :, c] = cv2.addWeighted(original_cv[:, :, c], 1.0, capa_malla[:, :, c], opacidad_malla, 0)
    # --- FIN DEL BLOQUE MALLA ANTI-OCR (SCANLINES)---


    # 3. Calcular el tamaño de un lienzo GIGANTE seguro para la rotación
    # Usamos la hipotenusa para sacar la diagonal del documento y asegurarnos
    # de que al girar 45º no queden esquinas vacías.
    import math # Asegúrate de que math está importado arriba
    diagonal = int(math.hypot(width, height))
    canvas_size = diagonal + 400 # Margen extra de seguridad
    
    txt_layer = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    # Cargar fuente
    try:
        font = ImageFont.truetype("arial.ttf", tamano_letra)
    except IOError:
        font = ImageFont.load_default()

    # 4. Dibujar el texto en el lienzo gigante (Recto)
    try:
        text_width = int(font.getlength(watermark_text))
    except AttributeError:
        text_width = len(watermark_text) * (tamano_letra // 2)

    step_x = max(10, text_width + separacion_texto)
    step_y = max(10, tamano_letra + separacion_lineas)

    # Llenamos todo el lienzo gigante
    for y in range(0, canvas_size, step_y):
        offset_x = (y // step_y % 2) * (step_x // 2) 
        for x in range(-200, canvas_size, step_x):
            draw.text((x + offset_x, y), watermark_text, font=font, fill=(50, 50, 50, opacidad))

    txt_cv = np.array(txt_layer)

    # 5. La Magia 1: Deformación Espacial (Ondas)
    X, Y = np.meshgrid(np.arange(canvas_size), np.arange(canvas_size))
    map_x = X.astype(np.float32)
    map_y = (Y + amplitud_onda * np.sin(X / longitud_onda)).astype(np.float32)

    warped_txt = cv2.remap(txt_cv, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # 5.5 La Magia 2: Rotación de 45 Grados
    centro_lienzo = (canvas_size // 2, canvas_size // 2)
    # Creamos una matriz de rotación con OpenCV
    M = cv2.getRotationMatrix2D(centro_lienzo, angulo_rotacion, 1.0)
    # Giramos la imagen deformada
    rotated_txt = cv2.warpAffine(warped_txt, M, (canvas_size, canvas_size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # 5.6 Recortar el centro exacto para volver al tamaño del documento original
    start_x = centro_lienzo[0] - width // 2
    start_y = centro_lienzo[1] - height // 2
    
    # Extraemos solo el rectángulo central que nos interesa
    warped_txt_cropped = rotated_txt[start_y:start_y+height, start_x:start_x+width]

    # ... (El código continúa con tu paso 6 actual del Ruido Adversarial usando 'warped_txt_cropped')

    # 6. Aplicar Ruido Adversarial a las letras deformadas
    if ruido_ai:
        # Generamos ruido con una media de 0 para que no aclare ni oscurezca demasiado el texto
        # Usamos una desviación estándar proporcional a la opacidad
        std_dev = (opacidad / 255) * intensidad_ruido_ajustada 
        ruido = np.random.normal(0, std_dev, warped_txt_cropped.shape).astype(np.float32)
        
        # Creamos una máscara flotante basada en el canal alfa del texto
        # Esto hace que el ruido sea más fuerte en el centro de la letra y suave en los bordes (anti-aliasing)
        mask_alpha = warped_txt_cropped[:, :, 3] / 255.0
        
        for c in range(3): # Aplicar a R, G y B
            # Sumamos el ruido solo donde hay texto y limitamos los valores entre 0 y 255
            temp_channel = warped_txt_cropped[:, :, c].astype(np.float32)
            temp_channel += ruido[:, :, c] * mask_alpha
            warped_txt_cropped[:, :, c] = np.clip(temp_channel, 0, 255).astype(np.uint8)

    # 7. Fusionar con la imagen original
    original_cv = np.array(original_img)
    
    alpha_text = warped_txt_cropped[:, :, 3] / 255.0
    alpha_inv = 1.0 - alpha_text

    resultado_cv = np.zeros_like(original_cv)
    for c in range(3): # Canales RGB
        resultado_cv[:, :, c] = (alpha_text * warped_txt_cropped[:, :, c] + alpha_inv * original_cv[:, :, c])
    
    resultado_cv[:, :, 3] = original_cv[:, :, 3] # Mantener el alpha original

    final_image = Image.fromarray(resultado_cv)

    # --- BLOQUE PARA AÑADIR BARRA INFERIOR DE USO LEGAL ---
    try:
        font_footer = ImageFont.truetype("arial.ttf", tamano_letra_footer)
    except IOError:
        font_footer = ImageFont.load_default()

    # 2. Calcular el alto de la barra usando el NUEVO tamaño de letra
    alto_barra = tamano_letra_footer + 40  
    ancho_final, alto_original = final_image.size
    nuevo_alto = alto_original + alto_barra

    imagen_con_barra = Image.new("RGBA", (ancho_final, nuevo_alto), (255, 255, 255, 255))
    imagen_con_barra.paste(final_image, (0, 0))

    draw_footer = ImageDraw.Draw(imagen_con_barra)
    draw_footer.rectangle([0, alto_original, ancho_final, nuevo_alto], fill=(40, 40, 40, 255))

    # 3. Calcular el ancho del texto usando la NUEVA fuente
    try:
        w_text_footer = int(font_footer.getlength(texto_footer))
    except:
        w_text_footer = len(texto_footer) * (tamano_letra_footer // 2)
    
    pos_x = (ancho_final - w_text_footer) // 2
    # Centramos verticalmente usando el nuevo tamaño
    pos_y = alto_original + (alto_barra - tamano_letra_footer) // 2 - 5 

    # 4. Dibujar usando el nuevo texto y la nueva fuente
    draw_footer.text((pos_x, pos_y), texto_footer, font=font_footer, fill=(255, 255, 255, 255))
    
    final_image = imagen_con_barra
    # --- FIN DEL BLOQUE PARA AÑADIR BARRA INFERIOR DE USO LEGAL ---

    # 8. Mostrar Resultados
    st.image(final_image, caption="Documento Protegido (Curvado Real)", use_container_width=True)

    final_rgb = final_image.convert("RGB")
    import io
    buf = io.BytesIO()
    final_rgb.save(buf, format="JPEG", quality=95)
    byte_im = buf.getvalue()

    st.download_button(
        label="📥 Descargar Documento Protegido",
        data=byte_im,
        file_name="dni_protegido.jpg",
        mime="image/jpeg"
    )