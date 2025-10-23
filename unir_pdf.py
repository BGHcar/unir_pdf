import streamlit as st

# Configuración de la página debe ser LO PRIMERO
st.set_page_config(
    page_title="PDF Toolkit - Unir, Dividir y Eliminar Páginas",
    page_icon="📄",
    layout="wide"
)

import io
import zipfile
from datetime import datetime
from collections import Counter

try:
    from pypdf import PdfMerger, PdfReader, PdfWriter
except ImportError as e:
    st.error(f"❌ Error importando pypdf: {e}")
    st.stop()

# Tamaños de papel predefinidos (ancho, alto en puntos) con tolerancia
PAPER_SIZES = {
    "A4": (595, 842),
    "A4 Horizontal": (842, 595),
    "Letter": (612, 792),
    "Letter Horizontal": (792, 612),
    "Legal": (612, 1008),
    "A3": (842, 1191),
    "A3 Horizontal": (1191, 842),
    "A5": (420, 595),
    "A5 Horizontal": (595, 420)
}

# Función para detectar el tamaño de página más común
def detect_most_common_size(uploaded_files):
    all_sizes = []
    
    for file in uploaded_files:
        try:
            file.seek(0)
            pdf_reader = PdfReader(file)
            
            for page in pdf_reader.pages:
                width = round(float(page.mediabox.width))
                height = round(float(page.mediabox.height))
                all_sizes.append((width, height))
                
        except Exception as e:
            continue
    
    if not all_sizes:
        return "A4"  # Tamaño por defecto
    
    # Contar frecuencias de tamaños
    size_counter = Counter(all_sizes)
    most_common_size = size_counter.most_common(1)[0][0]
    
    # Encontrar el nombre del tamaño más cercano
    return find_closest_paper_size(most_common_size)

# Función para encontrar el tamaño de papel más cercano
def find_closest_paper_size(actual_size, tolerance=10):
    actual_width, actual_height = actual_size
    
    for paper_name, (std_width, std_height) in PAPER_SIZES.items():
        if (abs(actual_width - std_width) <= tolerance and 
            abs(actual_height - std_height) <= tolerance):
            return paper_name
    
    # Si no encuentra coincidencia, usar el más común o A4 por defecto
    return "A4"

# Función para normalizar página
def normalize_page_size(pdf_reader, page_num, target_size):
    try:
        original_page = pdf_reader.pages[page_num]
        target_width, target_height = PAPER_SIZES[target_size]
        
        pdf_writer = PdfWriter()
        pdf_writer.add_page(original_page)
        
        # Forzar el tamaño de página
        pdf_writer.pages[0].mediabox.upper_right = (target_width, target_height)
        
        buffer = io.BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        normalized_reader = PdfReader(buffer)
        return normalized_reader.pages[0]
        
    except Exception as e:
        return pdf_reader.pages[page_num]  # Fallback a página original

# Función para procesar un PDF individual
def process_single_pdf(pdf_file, pages_to_remove, target_size):
    try:
        pdf_reader = PdfReader(pdf_file)
        pdf_writer = PdfWriter()
        
        total_pages = len(pdf_reader.pages)
        pages_to_keep = [i for i in range(total_pages) if i not in pages_to_remove]
        
        for page_num in pages_to_keep:
            normalized_page = normalize_page_size(pdf_reader, page_num, target_size)
            pdf_writer.add_page(normalized_page)
        
        buffer = io.BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        return buffer, total_pages, len(pages_to_keep)
        
    except Exception as e:
        raise Exception(f"Error procesando PDF: {str(e)}")

# Función para unir PDFs
def merge_processed_pdfs(processed_pdfs):
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

# Función para parsear páginas
def parse_pages_input(pages_input, total_pages=None):
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

# Función para analizar distribución de tamaños
def analyze_size_distribution(uploaded_files):
    size_info = {}
    
    for file in uploaded_files:
        try:
            file.seek(0)
            pdf_reader = PdfReader(file)
            file_sizes = []
            
            for page in pdf_reader.pages:
                width = round(float(page.mediabox.width))
                height = round(float(page.mediabox.height))
                paper_name = find_closest_paper_size((width, height))
                file_sizes.append(paper_name)
            
            size_info[file.name] = file_sizes
            
        except Exception as e:
            size_info[file.name] = ["Error al leer"]
    
    return size_info

# Interfaz principal
def main():
    st.title("📄 PDF Toolkit - Unir PDFs y Eliminar Páginas")
    st.markdown("**Todas las páginas se normalizan automáticamente al tamaño más común detectado**")
    
    # Pestañas
    tab1, tab2 = st.tabs(["🔗 Unir y Eliminar Páginas", "✂️ Dividir PDF"])
    
    with tab1:
        st.header("Unir PDFs y Eliminar Páginas")
        
        uploaded_files = st.file_uploader(
            "Selecciona los archivos PDF a unir",
            type="pdf",
            accept_multiple_files=True,
            help="Todas las páginas se normalizarán automáticamente al tamaño más común",
            key="merge_uploader"
        )
        
        if uploaded_files:
            # DETECTAR TAMAÑO MÁS COMÚN AUTOMÁTICAMENTE
            optimal_size = detect_most_common_size(uploaded_files)
            
            # Mostrar información del tamaño detectado
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.success(f"📐 **Tamaño detectado automáticamente:** {optimal_size}")
                st.info("Todas las páginas se normalizarán a este tamaño")
            
            # Mostrar análisis de distribución de tamaños
            with st.expander("📊 Ver análisis de tamaños en los archivos"):
                size_distribution = analyze_size_distribution(uploaded_files)
                
                for filename, sizes in size_distribution.items():
                    if sizes and sizes[0] != "Error al leer":
                        size_count = Counter(sizes)
                        st.write(f"**{filename}**:")
                        for size_name, count in size_count.items():
                            st.write(f"  - {size_name}: {count} páginas")
                    else:
                        st.write(f"**{filename}**: Error al analizar")
            
            st.subheader("📋 Configurar páginas a eliminar por cada PDF")
            
            if 'pages_inputs' not in st.session_state:
                st.session_state.pages_inputs = {}
            
            # Procesar cada archivo
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
                                placeholder=f"Ej: 1,3,5-7 (de {total_pages} páginas totales)",
                                help=f"Eliminar páginas antes de unir. PDF tiene {total_pages} páginas."
                            )
                            st.session_state.pages_inputs[key] = pages_input
                        
                        with col2:
                            st.metric("Total páginas", total_pages)
                            
                            if pages_input:
                                pages_to_remove = parse_pages_input(pages_input, total_pages)
                                st.metric("Páginas a eliminar", len(pages_to_remove))
                                st.metric("Páginas que quedarán", total_pages - len(pages_to_remove))
                                
                                if pages_to_remove:
                                    st.info(f"Eliminar: {', '.join(map(str, sorted([p+1 for p in pages_to_remove])))}")
                            else:
                                st.metric("Páginas a eliminar", 0)
                                st.metric("Páginas que quedarán", total_pages)
                
                except Exception as e:
                    st.error(f"Error leyendo {file.name}: {str(e)}")
            
            # Botón de procesamiento
            if st.button("🔄 Procesar y Unir PDFs", type="primary", key="merge_button"):
                try:
                    with st.spinner(f"Normalizando a {optimal_size} y uniendo PDFs..."):
                        processed_pdfs = []
                        total_stats = {
                            'original_pages': 0,
                            'removed_pages': 0,
                            'final_pages': 0,
                            'processed_files': 0
                        }
                        
                        # Procesar cada PDF individualmente
                        for i, file in enumerate(uploaded_files):
                            file.seek(0)
                            
                            key = f"pages_{i}_{file.name}"
                            pages_input = st.session_state.pages_inputs.get(key, "")
                            pages_to_remove = parse_pages_input(pages_input)
                            
                            processed_pdf, original_pages, final_pages = process_single_pdf(
                                file, pages_to_remove, optimal_size
                            )
                            
                            processed_pdfs.append(processed_pdf)
                            total_stats['original_pages'] += original_pages
                            total_stats['removed_pages'] += len(pages_to_remove)
                            total_stats['final_pages'] += final_pages
                            total_stats['processed_files'] += 1
                        
                        # Unir todos los PDFs procesados
                        final_pdf = merge_processed_pdfs(processed_pdfs)
                        
                        # Mostrar resultado
                        st.success(f"✅ PDFs normalizados a {optimal_size} y unidos correctamente!")
                        
                        # Estadísticas
                        st.subheader("📊 Resumen del Procesamiento")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Archivos procesados", total_stats['processed_files'])
                        with col2:
                            st.metric("Páginas originales", total_stats['original_pages'])
                        with col3:
                            st.metric("Páginas eliminadas", total_stats['removed_pages'])
                        with col4:
                            st.metric("Páginas finales", total_stats['final_pages'])
                        
                        st.info(f"📏 **Todas las páginas normalizadas a:** {optimal_size}")
                        
                        # Botón de descarga
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        st.download_button(
                            label="📥 Descargar PDF Procesado",
                            data=final_pdf.getvalue(),
                            file_name=f"pdf_unido_normalizado_{timestamp}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
                        
                except Exception as e:
                    st.error(f"❌ Error al procesar los PDFs: {str(e)}")
    
    with tab2:
        # ... (el código de la pestaña dividir permanece igual)
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
                    "Cómo quieres dividir el PDF:",
                    ["todas", "rango_personalizado"],
                    format_func=lambda x: "Dividir en páginas individuales" if x == "todas" else "Dividir por rangos personalizados",
                    key="split_option"
                )
                
                if split_option == "rango_personalizado":
                    st.subheader("Configurar rangos de división")
                    ranges_input = st.text_area(
                        "Especifica los rangos de páginas (uno por línea):",
                        placeholder="Ejemplo:\n1-3\n4-5\n6\n7-10",
                        help="Cada línea será un PDF separado. Usa formato: 1-3, 4, 5-7, etc.",
                        key="ranges_input"
                    )
                    ranges_list = [r.strip() for r in ranges_input.split('\n') if r.strip()] if ranges_input else []
                else:
                    ranges_list = None
                
                if st.button("✂️ Dividir PDF", type="primary", key="split_button"):
                    with st.spinner("Dividiendo PDF..."):
                        pdf_files = split_pdf(uploaded_file_split, split_option, ranges_list)
                        
                        if not pdf_files:
                            st.warning("No se generaron archivos. Verifica los rangos especificados.")
                            return
                        
                        st.success(f"✅ PDF dividido en {len(pdf_files)} archivos!")
                        
                        # Para muchas páginas, ofrecer ZIP
                        if len(pdf_files) > 5:
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
                                label="📦 Descargar todos como ZIP",
                                data=zip_buffer.getvalue(),
                                file_name="pdf_divididos.zip",
                                mime="application/zip"
                            )
                        
                        # Descargar individualmente
                        st.subheader("Descargar archivos individualmente:")
                        cols = st.columns(2)
                        for i, pdf_buffer in enumerate(pdf_files):
                            with cols[i % 2]:
                                if split_option == "todas":
                                    st.download_button(
                                        label=f"📄 Página {i+1}",
                                        data=pdf_buffer.getvalue(),
                                        file_name=f"pagina_{i+1}.pdf",
                                        mime="application/pdf",
                                        key=f"page_{i}"
                                    )
                                else:
                                    range_name = ranges_list[i] if i < len(ranges_list) else f"rango_{i+1}"
                                    st.download_button(
                                        label=f"📄 Rango: {range_name}",
                                        data=pdf_buffer.getvalue(),
                                        file_name=f"rango_{range_name}.pdf",
                                        mime="application/pdf",
                                        key=f"range_{i}"
                                    )
            
            except Exception as e:
                st.error(f"Error procesando archivo: {str(e)}")

    # Instrucciones
    with st.expander("📖 Instrucciones de uso"):
        st.markdown("""
        ### 🔗 Unir y Eliminar Páginas:
        1. **Cargar PDFs**: Selecciona múltiples archivos PDF
        2. **Configurar cada PDF**: Para cada archivo, especifica qué páginas eliminar ANTES de unir
        3. **Formato de páginas**: Usa:
           - Páginas individuales: `1,3,5`
           - Rangos: `2-4`
           - Combinación: `1,3,5-7`
        4. **Procesar**: Los PDFs se procesan individualmente y luego se unen

        ### ✂️ Dividir PDF:
        1. **Cargar PDF**: Selecciona un archivo PDF
        2. **Elegir modo**:
           - **Páginas individuales**: Crea un PDF por cada página
           - **Rangos personalizados**: Divide en grupos específicos de páginas
        3. **Especificar rangos** (si aplica): Un rango por línea, ej: `1-3`, `4`, `5-7`
        4. **Dividir**: Descarga los archivos resultantes

        **Nota**: Todos los procesamientos se hacen en memoria, tus archivos están seguros.
        """)
    
    # Pie de página
    st.markdown("---")
    st.markdown("Creado con Streamlit y pypdf • Tus archivos se procesan localmente")

if __name__ == "__main__":
    main()