from flask import Blueprint, render_template, send_file, abort, flash, redirect, url_for, make_response
from auth import require_roles, get_current_user
from database import db_cursor
import io
import traceback
import xml.sax.saxutils as saxutils
from datetime import datetime

# Document Generation Libraries
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from docx import Document
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

admin_bp = Blueprint('admin_bp', __name__)

@admin_bp.route('/data-dictionary')
@require_roles('admin')
def data_dictionary():
    user = get_current_user()
    
    with db_cursor() as (conn, cur):
        # Fetch all public base tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        
        data_dict = []
        for table in tables:
            tname = table['table_name']
            
            # Fetch column details for each table
            cur.execute("""
                SELECT 
                    column_name, 
                    data_type, 
                    is_nullable, 
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = %s 
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """, (tname,))
            columns = cur.fetchall()
            
            data_dict.append({
                'table_name': tname,
                'columns': columns
            })
            
    return render_template('admin/data_dictionary.html', 
                          user=user, 
                          data_dict=data_dict)

@admin_bp.route('/export/<table_name>/<fmt>')
@require_roles('admin')
def export_table(table_name, fmt):
    print(f"DEBUG: Exporting table '{table_name}' in format '{fmt}'")
    try:
        with db_cursor() as (conn, cur):
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position;
            """, (table_name,))
            columns = cur.fetchall()
            
        if not columns:
            print(f"DEBUG: No columns found for table '{table_name}'")
            flash(f"No metadata found for table: {table_name}", "warning")
            return redirect(url_for('admin_bp.data_dictionary'))

        output = io.BytesIO()
        safe_table_name = "".join([c if c.isalnum() else "_" for c in table_name])
        filename = f"{safe_table_name}_schema"
        mimetype = 'application/octet-stream'

        if fmt == 'pdf':
            mimetype = 'application/pdf'
            doc = SimpleDocTemplate(output, 
                                  pagesize=landscape(letter), 
                                  leftMargin=0.5*inch, 
                                  rightMargin=0.5*inch, 
                                  topMargin=0.5*inch, 
                                  bottomMargin=0.5*inch)
            elements = []
            styles = getSampleStyleSheet()
            cell_style = ParagraphStyle(name='CellStyle', parent=styles['Normal'], fontSize=8, leading=10, wordWrap='CJK')
            
            elements.append(Paragraph(f"Data Dictionary: {table_name.upper()}", styles['Title']))
            elements.append(Spacer(1, 12))
            
            headers = ['Column', 'Type', 'Null', 'Default', 'Max Len']
            data = [[Paragraph(f"<b>{h}</b>", cell_style) for h in headers]]
            
            for col in columns:
                data.append([
                    Paragraph(saxutils.escape(str(col['column_name'])), cell_style),
                    Paragraph(saxutils.escape(str(col['data_type'])), cell_style),
                    Paragraph(saxutils.escape(str(col['is_nullable'])), cell_style),
                    Paragraph(saxutils.escape(str(col['column_default']) if col['column_default'] else '-'), cell_style),
                    Paragraph(saxutils.escape(str(col['character_maximum_length']) if col['character_maximum_length'] else '-'), cell_style)
                ])
                
            col_widths = [1.5*inch, 1.5*inch, 0.8*inch, 5.0*inch, 1.2*inch]
            t = Table(data, colWidths=col_widths, hAlign='LEFT', repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4169E1')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]))
            elements.append(t)
            doc.build(elements)

        elif fmt == 'docx':
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            doc = Document()
            doc.add_heading(f'Data Dictionary: {table_name}', 0)
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            hdr_cells = table.rows[0].cells
            for i, h in enumerate(['Column Name', 'Data Type', 'Nullable', 'Default', 'Max Length']):
                hdr_cells[i].text = h
            
            for col in columns:
                row_cells = table.add_row().cells
                row_cells[0].text = str(col['column_name'])
                row_cells[1].text = str(col['data_type'])
                row_cells[2].text = str(col['is_nullable'])
                row_cells[3].text = str(col['column_default']) if col['column_default'] else '-'
                row_cells[4].text = str(col['character_maximum_length']) if col['character_maximum_length'] else '-'
            doc.save(output)

        elif fmt == 'pptx':
            mimetype = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            slide.shapes.title.text = f"Data Dictionary: {table_name}"
            left, top, width, height = Inches(0.5), Inches(1.5), Inches(9.0), Inches(0.8)
            table_shape = slide.shapes.add_table(len(columns) + 1, 5, left, top, width, height)
            table = table_shape.table
            
            headers = ['Column', 'Type', 'Null', 'Default', 'Max Len']
            for i, h in enumerate(headers):
                cell = table.cell(0, i)
                cell.text = h
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(65, 105, 225)
            
            for r, col in enumerate(columns):
                table.cell(r+1, 0).text = str(col['column_name'])
                table.cell(r+1, 1).text = str(col['data_type'])
                table.cell(r+1, 2).text = str(col['is_nullable'])
                table.cell(r+1, 3).text = str(col['column_default']) if col['column_default'] else '-'
                table.cell(r+1, 4).text = str(col['character_maximum_length']) if col['character_maximum_length'] else '-'
            prs.save(output)

        else:
            abort(400)

        # Build Hardened Response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = mimetype
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}.{fmt}"'
        print(f"DEBUG: Successfully generated {fmt} for {table_name}")
        return response
            
    except Exception as e:
        print(f"CRITICAL: Export failed for {table_name} ({fmt}): {str(e)}")
        traceback.print_exc()
        flash(f"System error during export: {str(e)}", "error")
        return redirect(url_for('admin_bp.data_dictionary'))

@admin_bp.route('/export-all/<fmt>')
@require_roles('admin')
def export_all_tables(fmt):
    print(f"DEBUG: Exporting ALL tables in format '{fmt}'")
    try:
        with db_cursor() as (conn, cur):
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            table_names = [row['table_name'] for row in cur.fetchall()]
            
            all_metadata = []
            for tname in table_names:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """, (tname,))
                all_metadata.append({'table_name': tname, 'columns': cur.fetchall()})

        if not all_metadata:
            flash("No tables found to export.", "warning")
            return redirect(url_for('admin_bp.data_dictionary'))

        output = io.BytesIO()
        filename = "full_database_dictionary"
        mimetype = 'application/octet-stream'
        
        if fmt == 'pdf':
            mimetype = 'application/pdf'
            doc = SimpleDocTemplate(output, 
                                  pagesize=landscape(letter), 
                                  leftMargin=0.5*inch, 
                                  rightMargin=0.5*inch, 
                                  topMargin=0.5*inch, 
                                  bottomMargin=0.5*inch)
            elements = []
            styles = getSampleStyleSheet()
            cell_style = ParagraphStyle(name='CellStyle', parent=styles['Normal'], fontSize=8, leading=10, wordWrap='CJK')
            
            elements.append(Paragraph("System Data Dictionary - Full Report", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M %p')}", styles['Normal']))
            elements.append(Spacer(1, 24))
            
            for i, table in enumerate(all_metadata):
                if i > 0: elements.append(PageBreak())
                elements.append(Paragraph(f"Table: {table['table_name'].upper()}", styles['Heading2']))
                elements.append(Spacer(1, 10))
                
                headers = ['Column', 'Type', 'Null', 'Default', 'Max Len']
                data = [[Paragraph(f"<b>{h}</b>", cell_style) for h in headers]]
                for col in table['columns']:
                    data.append([
                        Paragraph(saxutils.escape(str(col['column_name'])), cell_style),
                        Paragraph(saxutils.escape(str(col['data_type'])), cell_style),
                        Paragraph(saxutils.escape(str(col['is_nullable'])), cell_style),
                        Paragraph(saxutils.escape(str(col['column_default']) if col['column_default'] else '-'), cell_style),
                        Paragraph(saxutils.escape(str(col['character_maximum_length']) if col['character_maximum_length'] else '-'), cell_style)
                    ])
                
                t = Table(data, colWidths=[1.5*inch, 1.5*inch, 0.8*inch, 5.0*inch, 1.2*inch], repeatRows=1)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4169E1')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 20))
            doc.build(elements)

        elif fmt == 'docx':
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            doc = Document()
            doc.add_heading('System Data Dictionary - Full Report', 0)
            for i, table in enumerate(all_metadata):
                if i > 0: doc.add_page_break()
                doc.add_heading(f"Table: {table['table_name']}", level=1)
                t = doc.add_table(rows=1, cols=5)
                t.style = 'Table Grid'
                hdr_cells = t.rows[0].cells
                for idx, h in enumerate(['Column', 'Type', 'Null', 'Default', 'Max Len']):
                    hdr_cells[idx].text = h
                for col in table['columns']:
                    row_cells = t.add_row().cells
                    row_cells[0].text = str(col['column_name'])
                    row_cells[1].text = str(col['data_type'])
                    row_cells[2].text = str(col['is_nullable'])
                    row_cells[3].text = str(col['column_default']) if col['column_default'] else '-'
                    row_cells[4].text = str(col['character_maximum_length']) if col['character_maximum_length'] else '-'
            doc.save(output)

        elif fmt == 'pptx':
            mimetype = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            prs = Presentation()
            for table in all_metadata:
                slide = prs.slides.add_slide(prs.slide_layouts[5])
                slide.shapes.title.text = f"Schema: {table['table_name']}"
                left, top, width, height = Inches(0.5), Inches(1.5), Inches(9.0), Inches(0.8)
                t_shape = slide.shapes.add_table(len(table['columns']) + 1, 5, left, top, width, height)
                t = t_shape.table
                for idx, h in enumerate(['Column', 'Type', 'Null', 'Default', 'Max Len']):
                    cell = t.cell(0, idx)
                    cell.text = h
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(65, 105, 225)
                for r, col in enumerate(table['columns']):
                    t.cell(r+1, 0).text = str(col['column_name'])
                    t.cell(r+1, 1).text = str(col['data_type'])
                    t.cell(r+1, 2).text = str(col['is_nullable'])
                    t.cell(r+1, 3).text = str(col['column_default']) if col['column_default'] else '-'
                    t.cell(r+1, 4).text = str(col['character_maximum_length']) if col['character_maximum_length'] else '-'
            prs.save(output)

        else:
            abort(400)

        # Build Hardened Response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = mimetype
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}.{fmt}"'
        print(f"DEBUG: Successfully generated Bulk {fmt}")
        return response
            
    except Exception as e:
        print(f"CRITICAL: Bulk export failed ({fmt}): {str(e)}")
        traceback.print_exc()
        flash(f"Bulk export failed: {str(e)}", "error")
        return redirect(url_for('admin_bp.data_dictionary'))
