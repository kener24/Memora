from io import BytesIO

import xlsxwriter
from django.utils import timezone


def build_cash_movements_excel(rows, totals, filters_text, generated_at):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    workbook.set_properties({"title": "Movimientos de caja - Memora", "company": "Memora"})
    sheet = workbook.add_worksheet("Movimientos")
    navy, blue, pale, red, white = "#17243B", "#2563EB", "#E8F0FE", "#B42318", "#FFFFFF"
    title = workbook.add_format({"bold": True, "font_size": 18, "font_color": white, "bg_color": navy})
    subtitle = workbook.add_format({"font_color": "#475467", "italic": True})
    header = workbook.add_format({
        "bold": True, "font_color": white, "bg_color": blue,
        "text_wrap": True, "valign": "vcenter",
    })
    label = workbook.add_format({"bold": True, "bg_color": pale})
    money = workbook.add_format({"num_format": 'L #,##0.00;[Red]-L #,##0.00', "bottom": 1, "bottom_color": "#D0D5DD"})
    date = workbook.add_format({"num_format": "dd/mm/yyyy hh:mm", "bottom": 1, "bottom_color": "#D0D5DD"})
    text_format = workbook.add_format({"bottom": 1, "bottom_color": "#D0D5DD", "valign": "top"})
    voided = workbook.add_format({"font_color": red, "bottom": 1, "bottom_color": "#D0D5DD"})
    sheet.merge_range("A1:O1", "MEMORA · REPORTE DE MOVIMIENTOS DE CAJA", title)
    sheet.write("A2", f"Generado: {generated_at:%d/%m/%Y %H:%M}", subtitle)
    sheet.merge_range("C2:O2", f"Filtros: {filters_text or 'Sin filtros adicionales'}", subtitle)
    summary = [
        ("Total entradas", totals["total_in"]), ("Total salidas", totals["total_out"]),
        ("Neto financiero", totals["net"]), ("Entradas efectivo", totals["cash_in"]),
        ("Salidas efectivo", totals["cash_out"]), ("Neto efectivo", totals["cash_net"]),
    ]
    for index, (name, value) in enumerate(summary):
        column = (index % 3) * 2
        row = 3 + (index // 3)
        sheet.write(row, column, name, label)
        sheet.write_number(row, column + 1, float(value), money)
    columns = [
        ("Fecha/hora", "created_at", 19, "date"), ("Movimiento", "movement_number", 16, "text"),
        ("Caja", "register", 22, "text"), ("Sesión", "session", 16, "text"),
        ("Sucursal", "branch", 20, "text"), ("Tipo", "type", 22, "text"),
        ("Dirección", "direction", 12, "text"), ("Categoría", "category", 24, "text"),
        ("Método", "method", 16, "text"), ("Monto", "amount", 16, "money"),
        ("Referencia", "reference", 20, "text"), ("Usuario", "user", 24, "text"),
        ("Estado", "status", 14, "status"), ("Origen", "source", 22, "text"),
        ("Descripción", "description", 38, "text"),
    ]
    header_row = 6
    for col, (name, _, width, _) in enumerate(columns):
        sheet.write(header_row, col, name, header)
        sheet.set_column(col, col, width)
    sheet.set_row(header_row, 30)
    for row_index, item in enumerate(rows, start=header_row + 1):
        flat = {
            "created_at": timezone.localtime(item.created_at).replace(tzinfo=None),
            "movement_number": item.movement_number,
            "register": f"{item.cash_session.cash_register.code} · {item.cash_session.cash_register.name}",
            "session": item.cash_session.session_number, "branch": item.branch.name,
            "type": item.get_movement_type_display(), "direction": item.get_direction_display(),
            "category": item.get_category_display(), "method": item.get_payment_method_display(),
            "amount": item.amount, "reference": item.reference,
            "user": item.created_by.get_full_name().strip() or item.created_by.username,
            "status": item.get_status_display(),
            "source": item.payment.payment_number if item.payment_id else (
                item.settlement_reception.reception_number if item.settlement_reception_id else "Manual"
            ),
            "description": item.description,
        }
        for col, (_, key, _, kind) in enumerate(columns):
            value = flat[key]
            if kind == "date":
                sheet.write_datetime(row_index, col, value, date)
            elif kind == "money":
                sheet.write_number(row_index, col, float(value), money)
            else:
                sheet.write(row_index, col, value, voided if kind == "status" and item.status == "voided" else text_format)
    last_row = max(header_row + 1, header_row + len(rows))
    sheet.autofilter(header_row, 0, last_row, len(columns) - 1)
    sheet.freeze_panes(header_row + 1, 5)
    sheet.set_landscape()
    sheet.fit_to_pages(1, 0)
    sheet.set_margins(0.25, 0.25, 0.5, 0.5)
    sheet.set_footer("Memora · Página &P de &N")
    workbook.close()
    return output.getvalue()
