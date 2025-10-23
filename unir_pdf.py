import streamlit as st
import io
import zipfile
import tempfile
import os
from datetime import datetime
from collections import Counter

# Configuración debe ser PRIMERO
st.set_page_config(
    page_title="PDF Toolkit - Unir, Dividir y Reescalar PDFs",
    page_icon="📄",
    layout="wide"
)

try:
    from pypdf import PdfReader, PdfWriter
    # PdfMerger se importa de pypdf en versiones recientes
    try:
        from pypdf import PdfMerger
    except ImportError:
        # Fallback para versiones anteriores
        from pypdf import PdfMerger
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

# Función para detectar el tamaño más común
def detect_most_common_size(uploaded_files):
    """Detecta el tamaño de página más común en los PDFs cargados"""
    all_sizes = []
    
    for file in uploaded_files:
        try:
            file.seek(0)
            pdf_reader = PdfReader(file)
            
            for page in pdf_reader.pages:
                width = round(float(page.mediabox.width))
                height = round(float(page.mediabox.height))
                all_sizes.append((width, height))
                
        except Exception:
            continue
    
    if not all_sizes:
        return A4  # Tamaño por defecto
    
    # Encontrar el tamaño más común
    size_counter = Counter(all_sizes)
    most_common_size = size_counter.most_common(1)[0][0]
    
    # Buscar el tamaño estándar más cercano
    closest_standard = find_closest_standard_size(most_common_size)
    return closest_standard

def find_closest_standard_size(actual_size, tolerance=50):
    """Encuentra el tamaño estándar más cercano al tamaño actual"""
    actual_width, actual_height = actual_size
    
    for name, std_size in PAPER_SIZES.items():
        std_width, std_height = std_size
        if (abs(actual_width - std_width) <= tolerance and 
            abs(actual_height - std_height) <= tolerance):
            return std_size
    
    # Si no encuentra coincidencia, usar A4
    return A4

# Función para reescalar página PDF usando PyPDF
def resize_pdf_page(pdf_reader, page_num, target_size):
    """
    Reescala una página PDF al tamaño objetivo usando PyPDF
    """
    try:
        page = pdf_reader.pages[page_num]
        original_width = float(page.mediabox.width)
        original_height = float(page.mediabox.height)
        target_width, target_height = target_size
        
        # Calcular factor de escala manteniendo relación de aspecto
        scale_x = target_width / original_width
        scale_y = target_height / original_height
        scale = min(scale_x, scale_y)  # Mantener relación de aspecto
        
        # Crear nuevo writer y agregar página
        pdf_writer = PdfWriter()
        pdf_writer.add_page(page)
        
        # Aplicar transformación de escala
        pdf_writer.pages[0].scale(scale, scale)
        
        # Ajustar mediabox al tamaño objetivo
        pdf_writer.pages[0].mediabox.upper_right = (target_width, target_height)
        
        # Guardar en buffer
        buffer = io.BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        return PdfReader(buffer).pages[0]
            
    except Exception as e:
        st.warning(f"Error reescalando página {page_num + 1}: {e}")
        # Fallback: página original
        return pdf_reader.pages[page_num]

# Función para procesar un PDF individual
def process_single_pdf(pdf_file, pages_to_remove, target_size):
    """Procesa un PDF individual: elimina páginas y reescala"""
    try:
        pdf_reader = PdfReader(pdf_file)
        pdf_writer = PdfWriter()
        
        total_pages = len(pdf_reader.pages)
        pages_to_keep = [i for i in range(total_pages) if i not in pages_to_remove]
        
        for page_num in pages_to_keep:
            # Reescalar la página al tamaño objetivo
            resized_page = resize_pdf_page(pdf_reader, page_num, target_size)
            pdf_writer.add_page(resized_page)
        
        buffer = io.BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        return buffer, total_pages, len(pages_to_keep)
        
    except Exception as e:
        raise Exception(f"Error procesando PDF: {str(e)}")

# Función para unir PDFs
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

# Función para dividir PDF
def split_pdf(pdf_file, split_option, custom_ranges=None):
    """Divide un PDF en múltiples archivos"""
    try:
        pdf_reader = PdfReader(pdf_file)
        total_pages = len(pdf_reader.pages)
        pdf_files = []
        
        if split_option == "todas":
            # Una página por PDF
            for page_num in range(total_pages):
                pdf_writer = PdfWriter()
                pdf_writer.add_page(pdf_reader.pages[page_num])
                
                buffer = io.BytesIO()
                pdf_writer.write(buffer)
                buffer.seek(0)
                pdf_files.append(buffer)
        
        elif split_option == "rango_personalizado" and custom_ranges:
            # Rangos personalizados
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

# Función para analizar tamaños de páginas
def analyze_page_sizes(uploaded_files):
    """Analiza y muestra información sobre los tamaños de página"""
    sizes_info = {}
    all_sizes = []
    
    for file in uploaded_files:
        try:
            file.seek(0)
            pdf_reader = PdfReader(file)
            file_sizes = []
            
            for page in pdf_reader.pages:
                width = round(float(page.mediabox.width))
                height = round(float(page.mediabox.height))
                file_sizes.append((width, height))
                all_sizes.append((width, height))
            
            sizes_info[file.name] = file_sizes
            
        except Exception as e:
            sizes_info[file.name] = [("Error", "Error")]
    
    return sizes_info, all_sizes

# Interfaz principal
def main():
    st.title("📄 PDF Toolkit - Unir, Dividir y Reescalar PDFs")
    st.markdown("**Todas las páginas se reescalan automáticamente al tamaño más común**")
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Opción para elegir entre detección automática o manual
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
            target_size = None  # Se detectará automáticamente
        
        st.info("""
        **Reescalado inteligente:**
        - Detecta el tamaño más común
        - Mantiene la relación de aspecto
        - Preserva todo el contenido
        """)
    
    # Pestañas principales
    tab1, tab2 = st.tabs(["🔗 Unir y Reescalar PDFs", "✂️ Dividir PDF"])
    
    with tab1:
        st.header("Unir PDFs y Reescalar Páginas")
        
        uploaded_files = st.file_uploader(
            "Selecciona los archivos PDF a unir",
            type="pdf",
            accept_multiple_files=True,
            help="Todas las páginas se reescalarán al tamaño más común detectado",
            key="merge_uploader"
        )
        
        if uploaded_files:
            # Detectar tamaño objetivo
            if target_size is None:
                detected_size = detect_most_common_size(uploaded_files)
                target_size_name = [k for k, v in PAPER_SIZES.items() if v == detected_size][0]
                target_size = detected_size
            else:
                target_size_name = [k for k, v in PAPER_SIZES.items() if v == target_size][0]
            
            target_width, target_height = target_size
            
            # Mostrar información del tamaño
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.success(f"📐 **Tamaño de salida:** {target_size_name}")
                st.info(f"Dimensiones: {target_width} × {target_height} puntos")
                
                # Mostrar en milímetros también
                width_mm = round(target_width * 0.3528, 1)
                height_mm = round(target_height * 0.3528, 1)
                st.caption(f"({width_mm} × {height_mm} mm)")
            
            # Análisis de tamaños originales
            with st.expander("📊 Análisis de tamaños originales"):
                sizes_info, all_sizes = analyze_page_sizes(uploaded_files)
                
                for filename, sizes in sizes_info.items():
                    if sizes and sizes[0][0] != "Error":
                        size_count = Counter(sizes)
                        st.write(f"**{filename}**:")
                        for size, count in size_count.items():
                            size_name = [k for k, v in PAPER_SIZES.items() 
                                       if abs(v[0]-size[0]) < 10 and abs(v[1]-size[1]) < 10]
                            display_name = size_name[0] if size_name else f"{size[0]}×{size[1]}"
                            st.write(f"  - {display_name}: {count} páginas")
            
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
                    with st.spinner("Reescalando páginas y uniendo PDFs..."):
                        processed_pdfs = []
                        total_stats = {
                            'original_pages': 0,
                            'removed_pages': 0,
                            'final_pages': 0,
                            'processed_files': 0
                        }
                        
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
                
                st.info(f"📄 **{uploaded_file_split.name}** - {total_pages} páginas")
                
                split_option = st.radio(
                    "Modo de división:",
                    ["todas", "rango_personalizado"],
                    format_func=lambda x: "Páginas individuales" if x == "todas" else "Rangos personalizados"
                )
                
                if split_option == "rango_personalizado":
                    ranges_input = st.text_area(
                        "Rangos (uno por línea):",
                        placeholder="1-3\n4-5\n6\n7-10",
                        help="Cada línea crea un PDF separado"
                    )
                    ranges_list = [r.strip() for r in ranges_input.split('\n') if r.strip()] if ranges_input else []
                else:
                    ranges_list = None
                
                if st.button("✂️ Dividir PDF", type="primary"):
                    with st.spinner("Dividiendo PDF..."):
                        pdf_files = split_pdf(uploaded_file_split, split_option, ranges_list)
                        
                        if not pdf_files:
                            st.warning("No se generaron archivos. Verifica los rangos.")
                            return
                        
                        st.success(f"✅ PDF dividido en {len(pdf_files)} archivos")
                        
                        # Descarga múltiple
                        if len(pdf_files) > 1:
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                                for i, pdf_buffer in enumerate(pdf_files):
                                    if split_option == "todas":
                                        zip_file.writestr(f"pagina_{i+1}.pdf", pdf_buffer.getvalue())
                                    else:
                                        range_name = ranges_list[i] if i < len(ranges_list) else f"rango_{i+1}"
                                        zip_file.writestr(f"rango_{range_name}.pdf", pdf_buffer.getvalue())
                            zip_buffer.seek(0)
                            
                            st.download_button(
                                label="📦 Descargar ZIP",
                                data=zip_buffer.getvalue(),
                                file_name="pdf_divididos.zip",
                                mime="application/zip"
                            )
                        
                        # Descargas individuales
                        st.subheader("Descargas individuales:")
                        cols = st.columns(2)
                        for i, pdf_buffer in enumerate(pdf_files):
                            with cols[i % 2]:
                                if split_option == "todas":
                                    st.download_button(
                                        label=f"📄 Página {i+1}",
                                        data=pdf_buffer.getvalue(),
                                        file_name=f"pagina_{i+1}.pdf",
                                        mime="application/pdf"
                                    )
                                else:
                                    range_name = ranges_list[i] if i < len(ranges_list) else f"rango_{i+1}"
                                    st.download_button(
                                        label=f"📄 {range_name}",
                                        data=pdf_buffer.getvalue(),
                                        file_name=f"rango_{range_name}.pdf",
                                        mime="application/pdf"
                                    )
            
            except Exception as e:
                st.error(f"Error dividiendo PDF: {str(e)}")

    # Información
    with st.expander("📖 Instrucciones"):
        st.markdown("""
        ### 🔗 Unir y Reescalar:
        1. **Sube PDFs** - Múltiples archivos con diferentes tamaños
        2. **Configura eliminación** - Especifica páginas a eliminar por archivo
        3. **Procesa** - Todas las páginas se reescalan automáticamente
        4. **Descarga** - PDF unificado con tamaño consistente

        ### ✂️ Dividir:
        1. **Sube PDF** - Un archivo para dividir
        2. **Elige modo** - Páginas individuales o rangos personalizados
        3. **Divide** - Descarga los resultados

        **Nota:** El reescalado mantiene la relación de aspecto y preserva todo el contenido.
        """)
    
    st.markdown("---")
    st.markdown("Creado con Streamlit • Procesamiento 100% en navegador")

if __name__ == "__main__":
    main()