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

# Función para detectar el tamaño más común
def detect_most_common_size(uploaded_files):
    all_sizes = []
    
    for file in uploaded_files:
        try:
            file.seek(0)
            pdf_reader = PdfReader(file)
            
            for page in pdf_reader.pages:
                width = round(float(page.mediabox.width), 1)
                height = round(float(page.mediabox.height), 1)
                all_sizes.append((width, height))
                
        except Exception as e:
            continue
    
    if not all_sizes:
        return (595, 842)  # A4 por defecto
    
    # Encontrar el tamaño más común
    size_counter = Counter(all_sizes)
    most_common_size = size_counter.most_common(1)[0][0]
    
    return most_common_size

# Función para reescalar página manteniendo relación de aspecto
def resize_page(pdf_reader, page_num, target_size):
    try:
        original_page = pdf_reader.pages[page_num]
        target_width, target_height = target_size
        
        # Obtener tamaño original
        original_width = float(original_page.mediabox.width)
        original_height = float(original_page.mediabox.height)
        
        # Calcular relación de aspecto original
        original_ratio = original_width / original_height
        target_ratio = target_width / target_height
        
        # Crear nuevo writer
        pdf_writer = PdfWriter()
        
        if original_ratio > target_ratio:
            # La página original es más ancha - ajustar al ancho objetivo
            scale_factor = target_width / original_width
            new_height = original_height * scale_factor
            
            # Agregar página y ajustar tamaño
            pdf_writer.add_page(original_page)
            pdf_writer.pages[0].mediabox.upper_right = (target_width, new_height)
            
        else:
            # La página original es más alta - ajustar al alto objetivo
            scale_factor = target_height / original_height
            new_width = original_width * scale_factor
            
            # Agregar página y ajustar tamaño
            pdf_writer.add_page(original_page)
            pdf_writer.pages[0].mediabox.upper_right = (new_width, target_height)
        
        buffer = io.BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        resized_reader = PdfReader(buffer)
        return resized_reader.pages[0]
        
    except Exception as e:
        st.warning(f"Error reescalando página {page_num + 1}: {e}")
        return pdf_reader.pages[page_num]

# Función para procesar un PDF individual
def process_single_pdf(pdf_file, pages_to_remove, target_size):
    try:
        pdf_reader = PdfReader(pdf_file)
        pdf_writer = PdfWriter()
        
        total_pages = len(pdf_reader.pages)
        pages_to_keep = [i for i in range(total_pages) if i not in pages_to_remove]
        
        for page_num in pages_to_keep:
            # Reescalar la página al tamaño objetivo
            resized_page = resize_page(pdf_reader, page_num, target_size)
            pdf_writer.add_page(resized_page)
        
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

# Función para analizar tamaños
def analyze_page_sizes(uploaded_files):
    sizes_info = {}
    all_sizes = []
    
    for file in uploaded_files:
        try:
            file.seek(0)
            pdf_reader = PdfReader(file)
            file_sizes = []
            
            for page in pdf_reader.pages:
                width = round(float(page.mediabox.width), 1)
                height = round(float(page.mediabox.height), 1)
                file_sizes.append((width, height))
                all_sizes.append((width, height))
            
            sizes_info[file.name] = file_sizes
            
        except Exception as e:
            sizes_info[file.name] = [("Error", "Error")]
    
    return sizes_info, all_sizes

# Función para dividir PDF
def split_pdf(pdf_file, split_option, custom_ranges=None):
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

# Interfaz principal
def main():
    st.title("📄 PDF Toolkit - Unir y Dividir PDFs")
    st.markdown("**Todas las páginas se reescalan automáticamente al tamaño más común**")
    
    # Pestañas
    tab1, tab2 = st.tabs(["🔗 Unir y Eliminar Páginas", "✂️ Dividir PDF"])
    
    with tab1:
        st.header("Unir PDFs y Eliminar Páginas")
        
        uploaded_files = st.file_uploader(
            "Selecciona los archivos PDF a unir",
            type="pdf",
            accept_multiple_files=True,
            help="Todas las páginas se reescalarán al tamaño más común manteniendo la relación de aspecto",
            key="merge_uploader"
        )
        
        if uploaded_files:
            # Detectar tamaño más común automáticamente
            common_size = detect_most_common_size(uploaded_files)
            target_width, target_height = common_size
            
            # Mostrar información
            col1, col2 = st.columns([2, 1])
            with col1:
                st.success(f"📐 **Tamaño detectado:** {target_width} × {target_height} puntos")
                st.info("Todas las páginas se reescalarán a este tamaño manteniendo la relación de aspecto")
            
            with col2:
                # Mostrar en milímetros también (1 punto = 0.3528 mm)
                width_mm = round(target_width * 0.3528, 1)
                height_mm = round(target_height * 0.3528, 1)
                st.metric("Ancho", f"{width_mm} mm")
                st.metric("Alto", f"{height_mm} mm")
            
            # Análisis de tamaños
            with st.expander("📊 Ver análisis de tamaños"):
                sizes_info, all_sizes = analyze_page_sizes(uploaded_files)
                
                st.write("**Distribución de tamaños por archivo:**")
                for filename, sizes in sizes_info.items():
                    if sizes and sizes[0][0] != "Error":
                        size_count = Counter(sizes)
                        st.write(f"**{filename}**:")
                        for size, count in size_count.items():
                            st.write(f"  - {size[0]} × {size[1]} pts: {count} páginas")
            
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
                    with st.spinner("Reescalando páginas y uniendo PDFs..."):
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
                                file, pages_to_remove, common_size
                            )
                            
                            processed_pdfs.append(processed_pdf)
                            total_stats['original_pages'] += original_pages
                            total_stats['removed_pages'] += len(pages_to_remove)
                            total_stats['final_pages'] += final_pages
                            total_stats['processed_files'] += 1
                        
                        # Unir todos los PDFs procesados
                        final_pdf = merge_processed_pdfs(processed_pdfs)
                        
                        # Mostrar resultado
                        st.success("✅ PDFs reescalados y unidos correctamente!")
                        
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
                        
                        st.info(f"📏 **Todas las páginas reescaladas a:** {target_width} × {target_height} pts")
                        
                        # Botón de descarga
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        st.download_button(
                            label="📥 Descargar PDF Procesado",
                            data=final_pdf.getvalue(),
                            file_name=f"pdf_unido_reescalado_{timestamp}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
                        
                except Exception as e:
                    st.error(f"❌ Error al procesar los PDFs: {str(e)}")

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
        2. **Configurar cada PDF**: Para cada archivo, especifica qué páginas eliminar
        3. **Procesar**: Las páginas se reescalan automáticamente al tamaño más común
        4. **Descargar**: Obtén el PDF unido con todas las páginas del mismo tamaño

        ### ✂️ Dividir PDF:
        1. **Cargar PDF**: Selecciona un archivo PDF
        2. **Elegir modo**: Dividir en páginas individuales o por rangos personalizados
        3. **Dividir**: Descarga los archivos resultantes

        **Nota**: El reescalado mantiene la relación de aspecto original de las páginas.
        """)
    
    st.markdown("---")
    st.markdown("Creado con Streamlit y pypdf • Tus archivos se procesan localmente")

if __name__ == "__main__":
    main()