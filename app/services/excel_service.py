import io
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from app.models import CustomerInDB

def generate_customers_excel(customers: list[CustomerInDB]) -> io.BytesIO:
    """
    Generate a beautifully formatted Excel spreadsheet containing customer records.
    Returns an in-memory BytesIO buffer.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Customers Data"

    # Define styles
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid") # Dark Blue
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    stripe_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid") # Light Slate
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    thin_border_side = Side(border_style="thin", color="CBD5E1")
    cell_border = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thin_border_side,
        bottom=thin_border_side
    )

    data_font = Font(name="Calibri", size=10, color="0F172A")
    phone_font = Font(name="Calibri", size=10, bold=True, color="1E3A8A")

    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")

    # Headers definition
    headers = [
        "S.No",
        "Customer ID",
        "Date & Time (UTC)",
        "Phone (Required)",
        "Name",
        "Email",
        "Source (From)",
        "Address",
        "Landmark",
        "City",
        "State",
        "Pincode",
        "Profile / Notes",
    ]

    ws.append(headers)

    # Style Header Row
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = cell_border
    ws.row_dimensions[1].height = 28

    # Populate Data Rows
    for idx, customer in enumerate(customers, start=1):
        created_str = (
            customer.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if customer.created_at
            else "N/A"
        )
        row = [
            idx,
            customer.id,
            created_str,
            str(customer.phone or ""),
            str(customer.name or ""),
            str(customer.email or ""),
            str(customer.from_source or "Customer"),
            str(customer.address or ""),
            str(customer.landmark or ""),
            str(customer.city or ""),
            str(customer.state or ""),
            str(customer.pincode or ""),
            str(customer.profile or ""),
        ]
        ws.append(row)

        row_num = idx + 1
        is_stripe = (idx % 2 == 0)
        current_fill = stripe_fill if is_stripe else white_fill

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.fill = current_fill
            cell.border = cell_border
            cell.font = phone_font if col_idx == 4 else data_font
            
            # Alignments: S.No, ID, Date, Phone, Pincode -> centered; others left
            if col_idx in [1, 2, 3, 4, 12]:
                cell.alignment = center_align
            else:
                cell.alignment = left_align

        ws.row_dimensions[row_num].height = 20

    # Auto-adjust Column Widths with minimum & maximum caps
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val = str(cell.value or "")
            if len(val) > max_len:
                max_len = len(val)
        # Cap between 12 and 45 characters
        ws.column_dimensions[col_letter].width = max(12, min(max_len + 4, 45))

    # Freeze Header Row
    ws.freeze_panes = "A2"

    # Save to in-memory buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
