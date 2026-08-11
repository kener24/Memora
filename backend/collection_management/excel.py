from io import BytesIO

import xlsxwriter


def build_portfolio_excel(rows, totals, filters_text, generated_at):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    workbook.set_properties({"title": "Cartera y morosidad - Memora", "company": "Memora"})
    sheet = workbook.add_worksheet("Cartera")
    navy, blue, pale, red, white = "#17243B", "#2563EB", "#E8F0FE", "#B42318", "#FFFFFF"
    title = workbook.add_format({"bold": True, "font_size": 18, "font_color": white, "bg_color": navy})
    subtitle = workbook.add_format({"font_color": "#475467", "italic": True})
    header = workbook.add_format({
        "bold": True, "font_color": white, "bg_color": blue, "border": 1,
        "text_wrap": True, "valign": "vcenter",
    })
    label = workbook.add_format({"bold": True, "bg_color": pale, "border": 1})
    money = workbook.add_format({"num_format": 'L #,##0.00;[Red]-L #,##0.00', "border": 1})
    integer = workbook.add_format({"num_format": "0", "border": 1})
    date = workbook.add_format({"num_format": "dd/mm/yyyy", "border": 1})
    text_format = workbook.add_format({"border": 1, "valign": "top"})
    critical = workbook.add_format({"bg_color": "#FEE4E2", "font_color": red, "border": 1})

    sheet.merge_range("A1:R1", "MEMORA · REPORTE DE CARTERA Y MOROSIDAD", title)
    sheet.write("A2", f"Generado: {generated_at:%d/%m/%Y %H:%M}", subtitle)
    sheet.merge_range("C2:R2", f"Filtros: {filters_text or 'Sin filtros adicionales'}", subtitle)
    summary = [
        ("Contratos", totals["contracts"]), ("Clientes", totals["customers"]),
        ("Cartera pendiente", float(totals["pending"])), ("Cartera vencida", float(totals["overdue"])),
        ("Cartera por vencer", float(totals["upcoming"])), ("Cuotas vencidas", totals["overdue_installments"]),
    ]
    for index, (name, value) in enumerate(summary):
        column = (index % 3) * 2
        row = 3 + (index // 3)
        sheet.write(row, column, name, label)
        sheet.write_number(row, column + 1, value, money if "Cartera" in name else integer)

    columns = [
        ("Contrato", "contract_number", 16), ("Cliente", "customer_name", 26), ("Identidad", "identity", 17),
        ("Teléfono", "phone", 16), ("Sucursal", "branch", 18), ("Plan", "plan", 24),
        ("Precio total", "total_price", 16), ("Pagado", "total_paid", 16), ("Saldo", "balance", 16),
        ("Vencido", "overdue_amount", 16), ("Por vencer", "upcoming_amount", 16),
        ("Cuotas vencidas", "overdue_installments", 13), ("Días mora", "days_overdue", 12),
        ("Vencimiento más antiguo", "oldest_overdue_date", 17), ("Próxima cuota", "next_due_date", 15),
        ("Estado", "collection_status_label", 18), ("Prioridad", "priority_label", 13),
        ("Último pago", "last_payment_text", 22),
    ]
    header_row = 6
    for col, (name, _, width) in enumerate(columns):
        sheet.write(header_row, col, name, header)
        sheet.set_column(col, col, width)
    sheet.set_row(header_row, 32)

    for row_index, row in enumerate(rows, header_row + 1):
        flat = dict(row)
        flat["branch"] = row["branch"]["name"]
        flat["plan"] = row["plan"]["name"]
        last = row.get("last_payment")
        flat["last_payment_text"] = f'{last["number"]} · L {last["amount"]}' if last else "Sin pagos"
        for col, (_, key, _) in enumerate(columns):
            value = flat.get(key)
            if key in {"total_price", "total_paid", "balance", "overdue_amount", "upcoming_amount"}:
                sheet.write_number(row_index, col, float(value), money)
            elif key in {"overdue_installments", "days_overdue"}:
                sheet.write_number(row_index, col, int(value or 0), integer)
            elif key in {"oldest_overdue_date", "next_due_date"} and value:
                sheet.write_datetime(row_index, col, value, date)
            elif key in {"contract_number", "identity", "phone"}:
                sheet.write_string(row_index, col, str(value or ""), text_format)
            else:
                sheet.write(row_index, col, value or "", critical if key == "priority_label" and row["priority"] == "critical" else text_format)

    last_row = max(header_row + 1, header_row + len(rows))
    sheet.autofilter(header_row, 0, last_row, len(columns) - 1)
    sheet.freeze_panes(header_row + 1, 2)
    sheet.set_landscape()
    sheet.fit_to_pages(1, 0)
    sheet.set_margins(0.25, 0.25, 0.5, 0.5)
    sheet.set_footer("Memora · Página &P de &N")
    workbook.close()
    return output.getvalue()
