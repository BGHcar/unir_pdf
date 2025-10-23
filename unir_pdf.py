import streamlit as st
import io
import zipfile
import math
from datetime import datetime
from collections import Counter

# Configuración debe ser PRIMERO
st.set_page_config(
    page_title="PDF Toolkit - Unir, Dividir y Reescalar PDFs",
    page_icon="📄",
    layout="wide"
)

try:
    from pypdf import PdfReader, PdfWriter, PdfMerger
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, letter, legal, A3, A5
    from reportlab.lib.utils import ImageReader
    from PIL import Image
except ImportError as e:
    st.error(f"❌ Error importando dependencias: {e}")
    st.stop()

# Tamaños de papel predefinidos
PAPER_SIZES = {
    "A4": A4,
    "A4 Horizontal": (A4[1], A4[0]),
    "Letter": letter,
    "Letter Horizontal": (letter[1], letter[0]),
    "Legal": legal,
    "Legal Horizontal": (legal[1], legal[0]),
    "A3": A3,
    "A3 Horizontal": (A3[1], A3[0]),
    "A5": A5,
    "A5 Horizontal": (A5[1], A5[0])
}

# Función mejorada para detectar el tamaño óptimo
def detect_optimal_size(uploaded_files):
    """Detecta el tamaño óptimo considerando todas las páginas"""
    all_sizes = []
    all_ratios = []
    
    for file in uploaded_files:
        try:
            file.seek(0)
            pdf_reader = PdfReader(file)
            
            for page in pdf_reader.pages:
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)
                all_sizes.append((width, height))
                all_ratios.append(width / height)
                
        except Exception:
            continue
    
    if not all_sizes:
        return A4
    
    # Encontrar la relación de aspecto más común
    ratio_counter = Counter([round(ratio, 2) for ratio in all_ratios])
    most_common_ratio = ratio_counter.most_common(1)[0][0]
    
    # Encontrar el tamaño estándar que mejor se adapte
    return find_best_fit_size(all_sizes, most_common_ratio)

def find_best_fit_size(all_sizes, target_ratio, tolerance=0.1):
    """Encuentra el tamaño estándar que mejor se adapte a las páginas"""
    best_size = A4
    best_score = float('inf')
    
    for name, std_size in PAPER_SIZES.items():
        std_width, std_height = std_size
        std_ratio = std_width / std_height
        
        # Calcular qué tan bien se adapta este tamaño
        score = 0
        for width, height in all_sizes:
            page_ratio = width / height
            
            # Penalizar diferencias en relación de aspecto
            ratio_diff = abs(page_ratio - std_ratio)
            
            # Penalizar si la página es más grande que el tamaño estándar
            size_penalty = 0
            if width > std_width or height > std_height:
                size_penalty = max(width - std_width, height - std_height)
            
            score += ratio_diff + size_penalty * 0.001
        
        if score < best_score:
            best_score = score
            best_size = std_size
    
    return best_size

# Función MEJORADA para reescalado preciso
def resize_pdf_page_precise(pdf_reader, page_num, target_size):
    """
    Reescala una página PDF al tamaño objetivo de manera precisa
    Inspirado en el enfoque de pdf-toolkit
    """
    try:
        original_page = pdf_reader.pages[page_num]
        target_width, target_height = target_size
        
        # Obtener dimensiones originales
        original_width = float(original_page.mediabox.width)
        original_height = float(original_page.mediabox.height)
        
        # Calcular factores de escala
        scale_x = target_width / original_width
        scale_y = target_height / original_height
        
        # Usar el factor de escala más pequeño para mantener relación de aspecto
        # y evitar recortes
        scale = min(scale_x, scale_y)
        
        # Calcular nuevas dimensiones después del escalado
        new_width = original_width * scale
        new_height = original_height * scale
        
        # Calcular offsets para centrar el contenido
        x_offset = (target_width - new_width) / 2
        y_offset = (target_height - new_height) / 2
        
        # Crear nueva página
        pdf_writer = PdfWriter()
        pdf_writer.add_page(original_page)
        
        # Aplicar transformaciones
        page = pdf_writer.pages[0]
        
        # Escalar la página
        page.scale(scale, scale)
        
        # Mover la página al centro si es necesario
        if x_offset > 0 or y_offset > 0:
            page.translate(x_offset, y_offset)
        
        # Establecer el mediabox al tamaño objetivo
        page.mediabox.upper_right = (target_width, target_height)
        
        # Guardar en buffer
        buffer = io.BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        return PdfReader(buffer).pages[0]
        
    except Exception as e:
        st.warning(f"Error en reescalado preciso página {page_num + 1}: {e}")
        # Fallback: método simple
        return resize_pdf_page_simple(pdf_reader, page_num, target_size)

# Función de reescalado simple (fallback)
def resize_pdf_page_simple(pdf_reader, page_num, target_size):
    """Reescalado simple como fallback"""
    try:
        original_page = pdf_reader.pages[page_num]
        target_width, target_height = target_size
        
        pdf_writer = PdfWriter()
        pdf_writer.add_page(original_page)
        
        # Solo ajustar el mediabox
        pdf_writer.pages[0].mediabox.upper_right = (target_width, target_height)
        
        buffer = io.BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        return PdfReader(buffer).pages[0]
    except Exception:
        return pdf_reader.pages[page_num]

# Función para analizar la distribución de tamaños
def analyze_size_distribution(uploaded_files):
    """Analiza en detalle la distribución de tamaños de página"""
    size_analysis = {
        'files': {},
        'summary': {
            'total_pages': 0,
            'unique_sizes': set(),
            'size_counts': Counter(),
            'ratio_counts': Counter()
        }
    }
    
    for file in uploaded_files:
        try:
            file.seek(0)
            pdf_reader = PdfReader(file)
            file_sizes = []
            
            for page_num, page in enumerate(pdf_reader.pages):
                width = round(float(page.mediabox.width), 1)
                height = round(float(page.mediabox.height), 1)
                ratio = round(width / height, 2)
                
                file_sizes.append((width, height, ratio))
                size_analysis['summary']['total_pages'] += 1
                size_analysis['summary']['unique_sizes'].add((width, height))
                size_analysis['summary']['size_counts'][(width, height)] += 1
                size_analysis['summary']['ratio_counts'][ratio] += 1
            
            size_analysis['files'][file.name] = {
                'sizes': file_sizes,
                'total_pages': len(pdf_reader.pages)
            }
            
        except Exception as e:
            size_analysis['files'][file.name] = {'error': str(e)}
    
    return size_analysis

# Función para mostrar análisis detallado
def display_size_analysis(analysis):
    """Muestra un análisis detallado de los tamaños de página"""
    st.subheader("📊 Análisis Detallado de Tamaños")
    
    # Resumen general
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total páginas", analysis['summary']['total_pages'])
    with col2:
        st.metric("Tamaños únicos", len(analysis['summary']['unique_sizes']))
    with col3:
        most_common_size = analysis['summary']['size_counts'].most_common(1)[0]
        st.metric("Tamaño más común", f"{most_common_size[1]} págs")
    with col4:
        most_common_ratio = analysis['summary']['ratio_counts'].most_common(1)[0]
        st.metric("Relación común", f"{most_common_ratio[0]:.2f}")
    
    # Tamaños más comunes
    st.write("**Distribución de tamaños:**")
    for size, count in analysis['summary']['size_counts'].most_common(10):
        width, height = size
        ratio = width / height
        st.write(f"- {width} × {height} pts (relación: {ratio:.2f}): {count} páginas")
    
    # Análisis por archivo
    with st.expander("📁 Ver análisis por archivo"):
        for filename, file_data in analysis['files'].items():
            if 'error' in file_data:
                st.write(f"**{filename}**: Error - {file_data['error']}")
            else:
                st.write(f"**{filename}** ({file_data['total_pages']} páginas):")
                file_sizes = file_data['sizes']
                if file_sizes:
                    unique_sizes = Counter([(w, h) for w, h, r in file_sizes])
                    for size, count in unique_sizes.most_common(5):
                        width, height = size
                        st.write(f"  - {width} × {height} pts: {count} páginas")

# Función para procesar un PDF individual
def process_single_pdf(pdf_file, pages_to_remove, target_size, use_precise_resize=True):
    """Procesa un PDF individual: elimina páginas y reescala"""
    try:
        pdf_reader = PdfReader(pdf_file)
        pdf_writer = PdfWriter()
        
        total_pages = len(pdf_reader.pages)
        pages_to_keep = [i for i in range(total_pages) if i not in pages_to_remove]
        
        for page_num in pages_to_keep:
            # Usar reescalado preciso o simple según configuración
            if use_precise_resize:
                resized_page = resize_pdf_page_precise(pdf_reader, page_num, target_size)
            else:
                resized_page = resize_pdf_page_simple(pdf_reader, page_num, target_size)
            
            pdf_writer.add_page(resized_page)
        
        buffer = io.BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        return buffer, total_pages, len(pages_to_keep)
        
    except Exception as e:
        raise Exception(f"Error procesando PDF: {str(e)}")

# Las demás funciones permanecen igual (merge_processed_pdfs, parse_pages_input, split_pdf)

def merge_processed_pdfs(processed_pdfs):
    """Une múltiples PDFs en uno solo"""
    try:
        merger = PdfMerger()
        
        for pdf_buffer in processed_pdfs:
            merger.append(pdf_buffer)
        
        merged_buffer = io.BytesIO()
        merger.write(merged_buffer)
        merger.close()
        merged_buffer.seek(0)
        
        return merged_buffer
    except Exception as e:
        raise Exception(f"Error uniendo PDFs: {str(e)}")

def parse_pages_input(pages_input, total_pages=None):
    """Convierte texto de páginas a eliminar en conjunto de números"""
    pages_to_remove = set()
    if not pages_input or not pages_input.strip():
        return pages_to_remove
    
    parts = pages_input.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                start_idx = max(0, start - 1)
                end_idx = end
                if total_pages:
                    end_idx = min(end_idx, total_pages)
                pages_to_remove.update(range(start_idx, end_idx))
            except ValueError:
                continue
        else:
            try:
                page_num = int(part) - 1
                if total_pages is None or (0 <= page_num < total_pages):
                    pages_to_remove.add(page_num)
            except ValueError:
                continue
    
    return pages_to_remove

def split_pdf(pdf_file, split_option, custom_ranges=None):
    """Divide un PDF en múltiples archivos"""
    try:
        pdf_reader = PdfReader(pdf_file)
        total_pages = len(pdf_reader.pages)
        pdf_files = []
        
        if split_option == "todas":
            for page_num in range(total_pages):
                pdf_writer = PdfWriter()
                pdf_writer.add_page(pdf_reader.pages[page_num])
                
                buffer = io.BytesIO()
                pdf_writer.write(buffer)
                buffer.seek(0)
                pdf_files.append(buffer)
        
        elif split_option == "rango_personalizado" and custom_ranges:
            for range_str in custom_ranges:
                pdf_writer = PdfWriter()
                
                if '-' in range_str:
                    try:
                        start, end = map(int, range_str.split('-'))
                        start = max(1, start) - 1
                        end = min(total_pages, end)
                        
                        for page_num in range(start, end):
                            pdf_writer.add_page(pdf_reader.pages[page_num])
                    except ValueError:
                        continue
                else:
                    try:
                        page_num = int(range_str) - 1
                        if 0 <= page_num < total_pages:
                            pdf_writer.add_page(pdf_reader.pages[page_num])
                    except ValueError:
                        continue
                
                buffer = io.BytesIO()
                pdf_writer.write(buffer)
                buffer.seek(0)
                pdf_files.append(buffer)
        
        return pdf_files
    except Exception as e:
        raise Exception(f"Error dividiendo PDF: {str(e)}")

# Interfaz principal MEJORADA
def main():
    st.title("📄 PDF Toolkit - Unir, Dividir y Reescalar PDFs")
    st.markdown("**Reescalado preciso que mantiene la relación de aspecto y centra el contenido**")
    
    # Sidebar para configuración avanzada
    with st.sidebar:
        st.header("⚙️ Configuración Avanzada")
        
        # Método de reescalado
        resize_method = st.radio(
            "Método de reescalado:",
            ["Preciso (recomendado)", "Rápido"],
            help="Preciso: Mantiene relación de aspecto y centra. Rápido: Solo ajusta tamaño."
        )
        
        # Opción de tamaño
        size_option = st.radio(
            "Tamaño de salida:",
            ["Automático (inteligente)", "Manual"]
        )
        
        if size_option == "Manual":
            target_size_name = st.selectbox(
                "Selecciona tamaño:",
                options=list(PAPER_SIZES.keys())
            )
            target_size = PAPER_SIZES[target_size_name]
        else:
            target_size = None
        
        st.info("""
        **Reescalado preciso:**
        - Mantiene relación de aspecto
        - Centra el contenido automáticamente
        - Agrega márgenes si es necesario
        - Preserva toda la información
        """)
    
    # Pestañas principales
    tab1, tab2 = st.tabs(["🔗 Unir y Reescalar PDFs", "✂️ Dividir PDF"])
    
    with tab1:
        st.header("Unir PDFs y Reescalar Páginas")
        
        uploaded_files = st.file_uploader(
            "Selecciona los archivos PDF a unir",
            type="pdf",
            accept_multiple_files=True,
            help="Todas las páginas se reescalarán al tamaño óptimo detectado",
            key="merge_uploader"
        )
        
        if uploaded_files:
            # Detectar tamaño objetivo
            if target_size is None:
                detected_size = detect_optimal_size(uploaded_files)
                target_size_name = [k for k, v in PAPER_SIZES.items() if v == detected_size][0]
                target_size = detected_size
            else:
                target_size_name = [k for k, v in PAPER_SIZES.items() if v == target_size][0]
            
            target_width, target_height = target_size
            
            # Mostrar información del tamaño
            st.success(f"📐 **Tamaño de salida:** {target_size_name}")
            st.info(f"**Dimensiones:** {target_width} × {target_height} puntos ({target_width * 0.3528:.1f} × {target_height * 0.3528:.1f} mm)")
            st.info(f"**Método:** {resize_method} - {'Centrado con márgenes' if resize_method == 'Preciso (recomendado)' else 'Ajuste directo'}")
            
            # Análisis detallado
            size_analysis = analyze_size_distribution(uploaded_files)
            display_size_analysis(size_analysis)
            
            st.subheader("📋 Configurar páginas a eliminar")
            
            if 'pages_inputs' not in st.session_state:
                st.session_state.pages_inputs = {}
            
            # Configuración por archivo
            for i, file in enumerate(uploaded_files):
                try:
                    file.seek(0)
                    pdf_reader = PdfReader(file)
                    total_pages = len(pdf_reader.pages)
                    
                    with st.expander(f"📄 {file.name} ({total_pages} páginas)", expanded=True):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            key = f"pages_{i}_{file.name}"
                            if key not in st.session_state.pages_inputs:
                                st.session_state.pages_inputs[key] = ""
                            
                            pages_input = st.text_input(
                                f"Páginas a eliminar de {file.name}",
                                value=st.session_state.pages_inputs[key],
                                key=key,
                                placeholder=f"Ej: 1,3,5-7 (de {total_pages} páginas)",
                                help="Usa comas para páginas individuales y guiones para rangos"
                            )
                            st.session_state.pages_inputs[key] = pages_input
                        
                        with col2:
                            st.metric("Total páginas", total_pages)
                            
                            if pages_input:
                                pages_to_remove = parse_pages_input(pages_input, total_pages)
                                st.metric("A eliminar", len(pages_to_remove))
                                st.metric("Quedarán", total_pages - len(pages_to_remove))
                
                except Exception as e:
                    st.error(f"Error leyendo {file.name}: {str(e)}")
            
            # Botón de procesamiento
            if st.button("🔄 Procesar y Unir PDFs", type="primary", key="merge_button"):
                try:
                    use_precise = resize_method == "Preciso (recomendado)"
                    
                    with st.spinner("Reescalando páginas y uniendo PDFs..."):
                        processed_pdfs = []
                        total_stats = {
                            'original_pages': 0,
                            'removed_pages': 0,
                            'final_pages': 0,
                            'processed_files': 0
                        }
                        
                        # Barra de progreso
                        progress_bar = st.progress(0)
                        total_files = len(uploaded_files)
                        
                        # Procesar cada PDF
                        for i, file in enumerate(uploaded_files):
                            file.seek(0)
                            
                            key = f"pages_{i}_{file.name}"
                            pages_input = st.session_state.pages_inputs.get(key, "")
                            pages_to_remove = parse_pages_input(pages_input)
                            
                            processed_pdf, original_pages, final_pages = process_single_pdf(
                                file, pages_to_remove, target_size, use_precise
                            )
                            
                            processed_pdfs.append(processed_pdf)
                            total_stats['original_pages'] += original_pages
                            total_stats['removed_pages'] += len(pages_to_remove)
                            total_stats['final_pages'] += final_pages
                            total_stats['processed_files'] += 1
                            
                            # Actualizar barra de progreso
                            progress_bar.progress((i + 1) / total_files)
                        
                        # Unir PDFs procesados
                        final_pdf = merge_processed_pdfs(processed_pdfs)
                        
                        # Mostrar resultados
                        st.success("✅ PDFs reescalados y unidos correctamente!")
                        
                        # Estadísticas
                        st.subheader("📊 Resumen del Procesamiento")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Archivos", total_stats['processed_files'])
                        with col2:
                            st.metric("Páginas originales", total_stats['original_pages'])
                        with col3:
                            st.metric("Eliminadas", total_stats['removed_pages'])
                        with col4:
                            st.metric("Páginas finales", total_stats['final_pages'])
                        
                        st.info(f"📏 **Todas las páginas reescaladas a:** {target_size_name}")
                        st.info(f"🔧 **Método usado:** {resize_method}")
                        
                        # Descarga
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        st.download_button(
                            label="📥 Descargar PDF Procesado",
                            data=final_pdf.getvalue(),
                            file_name=f"pdf_reescalado_{timestamp}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
                        
                except Exception as e:
                    st.error(f"❌ Error al procesar: {str(e)}")
    
    with tab2:
        st.header("✂️ Dividir PDF")
        
        uploaded_file_split = st.file_uploader(
            "Selecciona el PDF a dividir",
            type="pdf",
            key="split_uploader"
        )
        
        if uploaded_file_split:
            try:
                uploaded_file_split.seek(0)
                pdf_reader = PdfReader(uploaded_file_split)
                total_pages = len(pdf_reader.pages)
                
                # Mostrar información del PDF
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📄 Archivo", uploaded_file_split.name)
                with col2:
                    st.metric("📑 Total páginas", total_pages)
                with col3:
                    # Calcular tamaño aproximado
                    file_size = len(uploaded_file_split.getvalue()) / 1024
                    st.metric("📊 Tamaño", f"{file_size:.1f} KB")
                
                # Opciones de división
                split_option = st.radio(
                    "Selecciona cómo quieres dividir el PDF:",
                    ["todas", "rango_personalizado"],
                    format_func=lambda x: "📄 Dividir en páginas individuales" if x == "todas" else "🎯 Dividir por rangos personalizados",
                    key="split_option"
                )
                
                if split_option == "rango_personalizado":
                    st.subheader("🎯 Configurar rangos de división")
                    
                    st.info("""
                    **Formato de rangos:**
                    - Una página: `3`
                    - Rango de páginas: `1-5`
                    - Múltiples rangos: uno por línea
                    """)
                    
                    default_example = "1-3\n4-5\n6\n7-10"
                    ranges_input = st.text_area(
                        "Especifica los rangos de páginas (uno por línea):",
                        value=default_example,
                        placeholder="Ejemplo:\n1-3\n4-5\n6\n7-10",
                        help="Cada línea creará un PDF separado",
                        key="ranges_input",
                        height=120
                    )
                    
                    # Validar y mostrar preview de rangos
                    if ranges_input:
                        ranges_list = [r.strip() for r in ranges_input.split('\n') if r.strip()]
                        valid_ranges = []
                        invalid_ranges = []
                        
                        for range_str in ranges_list:
                            if '-' in range_str:
                                try:
                                    start, end = map(int, range_str.split('-'))
                                    if 1 <= start <= end <= total_pages:
                                        valid_ranges.append(f"{start}-{end}")
                                    else:
                                        invalid_ranges.append(range_str)
                                except ValueError:
                                    invalid_ranges.append(range_str)
                            else:
                                try:
                                    page_num = int(range_str)
                                    if 1 <= page_num <= total_pages:
                                        valid_ranges.append(str(page_num))
                                    else:
                                        invalid_ranges.append(range_str)
                                except ValueError:
                                    invalid_ranges.append(range_str)
                        
                        # Mostrar validación
                        col1, col2 = st.columns(2)
                        with col1:
                            if valid_ranges:
                                st.success(f"✅ {len(valid_ranges)} rangos válidos")
                                with st.expander("Ver rangos válidos"):
                                    for rango in valid_ranges:
                                        st.write(f"- {rango}")
                        
                        with col2:
                            if invalid_ranges:
                                st.error(f"❌ {len(invalid_ranges)} rangos inválidos")
                                with st.expander("Ver rangos inválidos"):
                                    for rango in invalid_ranges:
                                        st.write(f"- {rango}")
                        
                        ranges_list = valid_ranges
                    else:
                        ranges_list = []
                else:
                    ranges_list = None
                
                # Botón de división
                if st.button("✂️ Dividir PDF", type="primary", key="split_button"):
                    if split_option == "rango_personalizado" and not ranges_list:
                        st.error("❌ Debes especificar al menos un rango válido")
                        return
                    
                    try:
                        with st.spinner("Dividiendo PDF..."):
                            pdf_files = split_pdf(uploaded_file_split, split_option, ranges_list)
                            
                            if not pdf_files:
                                st.warning("⚠️ No se generaron archivos. Verifica los rangos especificados.")
                                return
                            
                            st.success(f"✅ PDF dividido en {len(pdf_files)} archivos!")
                            
                            # Estadísticas de división
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Archivos generados", len(pdf_files))
                            with col2:
                                if split_option == "todas":
                                    st.metric("Tipo", "Páginas individuales")
                                else:
                                    st.metric("Tipo", "Rangos personalizados")
                            with col3:
                                total_size = sum(len(pdf.getvalue()) for pdf in pdf_files) / 1024
                                st.metric("Tamaño total", f"{total_size:.1f} KB")
                            
                            # Opción de descarga en ZIP (si hay muchos archivos)
                            if len(pdf_files) > 1:
                                st.subheader("📦 Descarga múltiple")
                                
                                zip_buffer = io.BytesIO()
                                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                    for i, pdf_buffer in enumerate(pdf_files):
                                        if split_option == "todas":
                                            filename = f"pagina_{i+1}.pdf"
                                        else:
                                            range_name = ranges_list[i] if i < len(ranges_list) else f"rango_{i+1}"
                                            filename = f"rango_{range_name}.pdf".replace('-', '_')
                                        
                                        zip_file.writestr(filename, pdf_buffer.getvalue())
                                
                                zip_buffer.seek(0)
                                zip_size = len(zip_buffer.getvalue()) / 1024
                                
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.download_button(
                                        label=f"📥 Descargar todos como ZIP ({zip_size:.1f} KB)",
                                        data=zip_buffer.getvalue(),
                                        file_name="pdf_divididos.zip",
                                        mime="application/zip",
                                        type="primary"
                                    )
                                with col2:
                                    st.caption(f"{len(pdf_files)} archivos")
                            
                            # Descargas individuales
                            st.subheader("📄 Descargas individuales")
                            st.info("💡 **Tip:** Para muchos archivos, usa la descarga ZIP arriba")
                            
                            # Organizar en columnas
                            if split_option == "todas":
                                # Para páginas individuales, mostrar en una tabla compacta
                                pages_per_row = 6
                                total_pages = len(pdf_files)
                                
                                for start_idx in range(0, total_pages, pages_per_row):
                                    end_idx = min(start_idx + pages_per_row, total_pages)
                                    cols = st.columns(pages_per_row)
                                    
                                    for i, pdf_buffer in enumerate(pdf_files[start_idx:end_idx]):
                                        page_num = start_idx + i + 1
                                        with cols[i]:
                                            st.download_button(
                                                label=f"Pág {page_num}",
                                                data=pdf_buffer.getvalue(),
                                                file_name=f"pagina_{page_num}.pdf",
                                                mime="application/pdf",
                                                key=f"page_{page_num}",
                                                use_container_width=True
                                            )
                            else:
                                # Para rangos personalizados, mostrar en 2 columnas
                                cols = st.columns(2)
                                for i, pdf_buffer in enumerate(pdf_files):
                                    range_name = ranges_list[i] if i < len(ranges_list) else f"rango_{i+1}"
                                    file_size = len(pdf_buffer.getvalue()) / 1024
                                    
                                    with cols[i % 2]:
                                        st.download_button(
                                            label=f"📑 {range_name} ({file_size:.1f} KB)",
                                            data=pdf_buffer.getvalue(),
                                            file_name=f"rango_{range_name}.pdf".replace('-', '_'),
                                            mime="application/pdf",
                                            key=f"range_{i}",
                                            use_container_width=True
                                        )
                    
                    except Exception as e:
                        st.error(f"❌ Error dividiendo PDF: {str(e)}")
                        st.info("💡 **Solución:** Verifica que los rangos sean válidos y estén en el formato correcto.")
            
            except Exception as e:
                st.error(f"❌ Error procesando archivo: {str(e)}")
        
        else:
            # Estado cuando no hay archivo cargado
            st.info("""
            ## 📋 Instrucciones para dividir PDF
            
            ### 🎯 **Dividir en páginas individuales:**
            1. Sube un archivo PDF
            2. Selecciona "Dividir en páginas individuales"
            3. Descarga un PDF por cada página
            
            ### 🎯 **Dividir por rangos personalizados:**
            1. Sube un archivo PDF
            2. Selecciona "Dividir por rangos personalizados"
            3. Especifica los rangos (uno por línea):
               - **Página única:** `3`
               - **Rango:** `1-5`
               - **Ejemplo completo:**
                 ```
                 1-3
                 4-5
                 6
                 7-10
                 ```
            4. Descarga los PDFs resultantes
            
            ### 💡 **Consejos:**
            - Usa **ZIP** cuando hay muchos archivos
            - Verifica que los números de página estén dentro del rango válido
            - Los archivos se generan en tu navegador, no se suben a ningún servidor
            """)

    # Sección de instrucciones generales
    with st.expander("📖 Guía completa de uso"):
        st.markdown("""
        ## 🎯 **Funcionalidades principales**
        
        ### 🔗 **Unir y Reescalar PDFs:**
        - **Unir múltiples PDFs** en un solo archivo
        - **Eliminar páginas específicas** de cada PDF antes de unir
        - **Reescalado automático** de todas las páginas al mismo tamaño
        - **Detección inteligente** del tamaño óptimo
        - **Preservación de contenido** sin pérdida de información
        
        ### ✂️ **Dividir PDF:**
        - **Dividir en páginas individuales** (un PDF por página)
        - **Dividir por rangos personalizados** (grupos de páginas)
        - **Validación automática** de rangos
        - **Descarga múltiple** en archivo ZIP
        - **Interfaz intuitiva** para configurar divisiones
        
        ## ⚙️ **Configuraciones avanzadas**
        
        ### 📐 **Opciones de reescalado:**
        - **Modo preciso:** Centra el contenido y agrega márgenes si es necesario
        - **Modo rápido:** Ajuste directo del tamaño de página
        - **Automático:** Detecta el mejor tamaño basado en todas las páginas
        - **Manual:** Selección manual del tamaño de salida (A4, Letter, etc.)
        
        ### 🎨 **Formatos soportados:**
        - A4 (vertical y horizontal)
        - Letter (vertical y horizontal)
        - Legal (vertical y horizontal)
        - A3, A5 (vertical y horizontal)
        
        ## 🔒 **Privacidad y seguridad**
        - ✅ **Procesamiento local:** Todo se hace en tu navegador
        - ✅ **Sin subida a servidores:** Tus archivos nunca salen de tu dispositivo
        - ✅ **Sin almacenamiento:** Los archivos se procesan en memoria y se eliminan después
        - ✅ **Código abierto:** Transparencia total en el procesamiento
        
        ## 🚀 **Recomendaciones de uso**
        - Para **PDFs grandes** (> 50 páginas), el proceso puede tomar unos segundos
        - **Verifica los rangos** antes de dividir PDFs grandes
        - Usa la **descarga ZIP** cuando generes muchos archivos
        - El **reescalado preciso** es más lento pero produce mejores resultados
        """)
    
    # Pie de página
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style='text-align: center;'>
            <p>Creado con ❤️ usando Streamlit • Procesamiento 100% en tu navegador</p>
            <p style='font-size: 0.8em; color: #666;'>
                Tus archivos nunca se suben a ningún servidor - Totalmente seguro y privado
            </p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()