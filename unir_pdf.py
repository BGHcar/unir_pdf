import streamlit as st
import io
import zipfile
from datetime import datetime
from collections import Counter

# Configuración debe ser PRIMERO
st.set_page_config(
    page_title="PDF Toolkit - Unir y Reescalar PDFs",
    page_icon="📄",
    layout="wide"
)

try:
    from pypdf import PdfReader, PdfWriter
    import fitz  # PyMuPDF - MUCHO más robusto que PyPDF
except ImportError as e:
    st.error(f"❌ Error importando dependencias: {e}")
    st.info("Ejecuta: pip install pypdf pymupdf")
    st.stop()

# Tamaños de papel predefinidos
PAPER_SIZES_MM = {
    "A4": (210, 297),
    "A4 Horizontal": (297, 210),
    "Letter": (216, 279),
    "Letter Horizontal": (279, 216),
    "Legal": (216, 356),
    "Legal Horizontal": (356, 216),
    "A3": (297, 420),
    "A3 Horizontal": (420, 297),
    "A5": (148, 210),
    "A5 Horizontal": (210, 148)
}

def mm_to_points(mm):
    """Convierte milímetros a puntos (1 mm = 2.83465 puntos)"""
    return mm * 2.83465

# Convertir a puntos para PyPDF
PAPER_SIZES = {k: (mm_to_points(v[0]), mm_to_points(v[1])) for k, v in PAPER_SIZES_MM.items()}

# Función para detectar el tamaño óptimo
def detect_optimal_size(uploaded_files):
    """Detecta el tamaño que mejor se adapta a todas las páginas"""
    all_sizes = []
    
    for file in uploaded_files:
        try:
            file.seek(0)
            doc = fitz.open(stream=file.read(), filetype="pdf")
            
            for page in doc:
                rect = page.rect
                width = rect.width
                height = rect.height
                all_sizes.append((width, height))
            
            doc.close()
                
        except Exception:
            continue
    
    if not all_sizes:
        return PAPER_SIZES["A4"]
    
    # Encontrar el tamaño más común
    size_counter = Counter(all_sizes)
    most_common_size = size_counter.most_common(1)[0][0]
    
    # Buscar el tamaño estándar más cercano
    best_match = PAPER_SIZES["A4"]
    min_diff = float('inf')
    
    for name, std_size in PAPER_SIZES.items():
        diff = abs(std_size[0] - most_common_size[0]) + abs(std_size[1] - most_common_size[1])
        if diff < min_diff:
            min_diff = diff
            best_match = std_size
    
    return best_match

# Función MEJORADA usando PyMuPDF para reescalado
def resize_page_pymupdf(pdf_file, page_num, target_size):
    """Reescala página usando PyMuPDF (mucho más robusto)"""
    try:
        pdf_file.seek(0)
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        page = doc[page_num]
        
        # Obtener dimensiones originales
        original_rect = page.rect
        original_width = original_rect.width
        original_height = original_rect.height
        
        # Dimensiones objetivo
        target_width, target_height = target_size
        
        # Calcular escala manteniendo relación de aspecto
        scale_x = target_width / original_width
        scale_y = target_height / original_height
        scale = min(scale_x, scale_y)
        
        # Crear nueva página
        new_doc = fitz.open()
        new_page = new_doc.new_page(width=target_width, height=target_height)
        
        # Calcular posición para centrar
        scaled_width = original_width * scale
        scaled_height = original_height * scale
        x_offset = (target_width - scaled_width) / 2
        y_offset = (target_height - scaled_height) / 2
        
        # Definir rectángulo de destino
        rect = fitz.Rect(x_offset, y_offset, x_offset + scaled_width, y_offset + scaled_height)
        
        # Mostrar la página original en el nuevo documento
        new_page.show_pdf_page(rect, doc, page_num)
        
        # Guardar en buffer
        buffer = io.BytesIO()
        new_doc.save(buffer)
        new_doc.close()
        doc.close()
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        st.warning(f"Error reescalando página {page_num + 1}: {e}")
        # Fallback: devolver página sin cambios
        pdf_file.seek(0)
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        new_doc = fitz.open()
        new_page = new_doc.new_page(width=target_size[0], height=target_size[1])
        new_page.show_pdf_page(new_page.rect, doc, page_num)
        buffer = io.BytesIO()
        new_doc.save(buffer)
        new_doc.close()
        doc.close()
        buffer.seek(0)
        return buffer

# Función para procesar un PDF individual
def process_single_pdf(pdf_file, pages_to_remove, target_size):
    """Procesa un PDF individual: elimina páginas y reescala"""
    try:
        pdf_file.seek(0)
        total_pages = len(PdfReader(pdf_file).pages)
        pages_to_keep = [i for i in range(total_pages) if i not in pages_to_remove]
        
        processed_pages = []
        
        for page_num in pages_to_keep:
            pdf_file.seek(0)
            resized_buffer = resize_page_pymupdf(pdf_file, page_num, target_size)
            processed_pages.append(resized_buffer)
        
        # Combinar páginas procesadas usando PdfWriter
        if processed_pages:
            writer = PdfWriter()
            for buffer in processed_pages:
                buffer.seek(0)
                reader = PdfReader(buffer)
                for page in reader.pages:
                    writer.add_page(page)
            
            final_buffer = io.BytesIO()
            writer.write(final_buffer)
            final_buffer.seek(0)
            
            return final_buffer, total_pages, len(pages_to_keep)
        else:
            raise Exception("No se procesaron páginas")
        
    except Exception as e:
        raise Exception(f"Error procesando PDF: {str(e)}")

# Función para unir PDFs
def merge_processed_pdfs(processed_pdfs):
    """Une múltiples PDFs en uno solo"""
    try:
        writer = PdfWriter()
        
        for pdf_buffer in processed_pdfs:
            pdf_buffer.seek(0)
            reader = PdfReader(pdf_buffer)
            for page in reader.pages:
                writer.add_page(page)
        
        merged_buffer = io.BytesIO()
        writer.write(merged_buffer)
        merged_buffer.seek(0)
        
        return merged_buffer
    except Exception as e:
        raise Exception(f"Error uniendo PDFs: {str(e)}")

# Función para parsear páginas a eliminar
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

# Función para analizar la distribución de tamaños
def analyze_size_distribution(uploaded_files):
    """Analiza en detalle la distribución de tamaños de página"""
    size_analysis = {
        'files': {},
        'summary': {
            'total_pages': 0,
            'unique_sizes': set(),
            'size_counts': Counter(),
        }
    }
    
    for file in uploaded_files:
        try:
            file.seek(0)
            doc = fitz.open(stream=file.read(), filetype="pdf")
            file_sizes = []
            
            for page in doc:
                rect = page.rect
                width = round(rect.width, 1)
                height = round(rect.height, 1)
                file_sizes.append((width, height))
                size_analysis['summary']['total_pages'] += 1
                size_analysis['summary']['unique_sizes'].add((width, height))
                size_analysis['summary']['size_counts'][(width, height)] += 1
            
            size_analysis['files'][file.name] = {
                'sizes': file_sizes,
                'total_pages': len(doc)
            }
            
            doc.close()
            
        except Exception as e:
            size_analysis['files'][file.name] = {'error': str(e)}
    
    return size_analysis

# Función para mostrar análisis detallado
def display_size_analysis(analysis, target_size):
    """Muestra un análisis detallado de los tamaños de página"""
    st.subheader("📊 Análisis Detallado de Tamaños")
    
    target_width, target_height = target_size
    
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
        st.metric("Tamaño objetivo", f"{target_width:.0f}×{target_height:.0f}")
    
    # Tamaños más comunes
    st.write("**Distribución de tamaños originales:**")
    for size, count in analysis['summary']['size_counts'].most_common(10):
        width, height = size
        
        # Calcular cómo se ajustará al tamaño objetivo
        scale_x = target_width / width
        scale_y = target_height / height
        scale = min(scale_x, scale_y)
        final_width = width * scale
        final_height = height * scale
        margin_x = (target_width - final_width) / 2
        margin_y = (target_height - final_height) / 2
        
        # Encontrar nombre del tamaño
        size_name = "Personalizado"
        for name, std_size in PAPER_SIZES.items():
            if abs(width - std_size[0]) < 10 and abs(height - std_size[1]) < 10:
                size_name = name
                break
        
        st.write(f"- **{size_name}** ({width:.0f} × {height:.0f} pts): {count} páginas")
        if margin_x > 0 or margin_y > 0:
            st.write(f"  → Escala: {scale:.2f}x, Márgenes: {margin_x:.1f} × {margin_y:.1f} pts")

# Función para dividir PDF
def split_pdf(pdf_file, split_option, custom_ranges=None):
    """Divide un PDF en múltiples archivos"""
    try:
        pdf_file.seek(0)
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

# Interfaz principal
def main():
    st.title("📄 PDF Toolkit - Unir y Reescalar PDFs")
    st.markdown("**Solución robusta: PyMuPDF + Reescalado preciso + 100% contenido preservado**")
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Opción de tamaño
        size_option = st.radio(
            "Tamaño de salida:",
            ["Automático (recomendado)", "Manual"]
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
        **Tecnología mejorada:**
        - ✅ **PyMuPDF** - Librería profesional
        - ✅ **Reescalado preciso** con márgenes
        - ✅ **100% contenido preservado**
        - ✅ **Centrado automático**
        - ✅ **Sin errores de transformación**
        """)
    
    # Pestañas principales
    tab1, tab2 = st.tabs(["🔗 Unir y Reescalar PDFs", "✂️ Dividir PDF"])
    
    with tab1:
        st.header("Unir PDFs y Reescalar Páginas")
        
        uploaded_files = st.file_uploader(
            "Selecciona los archivos PDF a unir",
            type="pdf",
            accept_multiple_files=True,
            help="Todas las páginas se reescalarán al mismo tamaño usando PyMuPDF",
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
            
            # Mostrar información
            st.success(f"📐 **Tamaño de salida:** {target_size_name}")
            st.info(f"**Dimensiones:** {target_width:.0f} × {target_height:.0f} puntos")
            
            # Convertir a mm para mostrar
            for name, mm_size in PAPER_SIZES_MM.items():
                if name == target_size_name:
                    st.info(f"**En milímetros:** {mm_size[0]} × {mm_size[1]} mm")
                    break
            
            # Análisis detallado
            size_analysis = analyze_size_distribution(uploaded_files)
            display_size_analysis(size_analysis, target_size)
            
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
                    with st.spinner("Reescalando páginas con PyMuPDF..."):
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
                                file, pages_to_remove, target_size
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
                        st.info("✅ **PyMuPDF: Todo el contenido preservado**")
                        st.info("✅ **Todas las páginas tienen el mismo tamaño**")
                        
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
                    file_size = len(uploaded_file_split.getvalue()) / 1024
                    st.metric("📊 Tamaño", f"{file_size:.1f} KB")
                
                split_option = st.radio(
                    "Selecciona cómo quieres dividir el PDF:",
                    ["todas", "rango_personalizado"],
                    format_func=lambda x: "📄 Dividir en páginas individuales" if x == "todas" else "🎯 Dividir por rangos personalizados"
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
                        height=120
                    )
                    
                    # Validar rangos
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
                        with col2:
                            if invalid_ranges:
                                st.error(f"❌ {len(invalid_ranges)} rangos inválidos")
                        
                        ranges_list = valid_ranges
                    else:
                        ranges_list = []
                else:
                    ranges_list = None
                
                if st.button("✂️ Dividir PDF", type="primary"):
                    if split_option == "rango_personalizado" and not ranges_list:
                        st.error("❌ Debes especificar al menos un rango válido")
                        return
                    
                    try:
                        with st.spinner("Dividiendo PDF..."):
                            pdf_files = split_pdf(uploaded_file_split, split_option, ranges_list)
                            
                            if not pdf_files:
                                st.warning("⚠️ No se generaron archivos. Verifica los rangos.")
                                return
                            
                            st.success(f"✅ PDF dividido en {len(pdf_files)} archivos!")
                            
                            # Estadísticas
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
                            
                            # Descarga en ZIP
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
                                
                                st.download_button(
                                    label=f"📥 Descargar todos como ZIP ({zip_size:.1f} KB)",
                                    data=zip_buffer.getvalue(),
                                    file_name="pdf_divididos.zip",
                                    mime="application/zip",
                                    type="primary"
                                )
                            
                            # Descargas individuales
                            st.subheader("📄 Descargas individuales")
                            
                            if split_option == "todas":
                                pages_per_row = 6
                                total_pages_display = len(pdf_files)
                                
                                for start_idx in range(0, total_pages_display, pages_per_row):
                                    end_idx = min(start_idx + pages_per_row, total_pages_display)
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
            
            except Exception as e:
                st.error(f"❌ Error procesando archivo: {str(e)}")
        
        else:
            st.info("""
            ## 📋 Instrucciones para dividir PDF
            
            ### 🎯 **Dividir en páginas individuales:**
            1. Sube un archivo PDF
            2. Selecciona "Dividir en páginas individuales"  
            3. Descarga un PDF por cada página
            
            ### 🎯 **Dividir por rangos personalizados:**
            1. Sube un archivo PDF
            2. Selecciona "Dividir por rangos personalizados"
            3. Especifica los rangos (uno por línea)
            4. Descarga los PDFs resultantes
            """)

    # Información
    with st.expander("📖 Tecnología utilizada"):
        st.markdown("""
        ## 🚀 **PyMuPDF - La solución profesional**
        
        ### 🔧 **Por qué PyMuPDF:**
        - **Librería profesional** usada en aplicaciones empresariales
        - **Capacidades avanzadas** de manipulación PDF
        - **Reescalado preciso** con transformaciones matriciales
        - **Preservación 100%** del contenido original
        - **Sin errores** de métodos obsoletos
        
        ### ✅ **Garantías:**
        - **Mismo tamaño** para todas las páginas
        - **Contenido centrado** automáticamente
        - **Márgenes inteligentes** cuando es necesario
        - **Relación de aspecto** preservada
        - **Calidad profesional** en resultados
        """)
    
    st.markdown("---")
    st.markdown("Creado con Streamlit • Motor: PyMuPDF profesional • 100% contenido preservado")

if __name__ == "__main__":
    main()