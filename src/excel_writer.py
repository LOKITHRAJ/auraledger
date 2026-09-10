import logging
from pathlib import Path
from typing import List, Dict, Any

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger("AuraLedger")


class ExcelWriter:
    """
    Handles generation of the final classified Excel workbook.
    Applies professional corporate accounting styling using openpyxl.
    """

    def __init__(self, output_path: str = None) -> None:
        if output_path is not None:
            self.output_path = Path(output_path)
        else:
            from config.settings import OUTPUT_FILE
            self.output_path = Path(OUTPUT_FILE)

    def write_classified_excel(self, transactions: List[Dict[str, Any]]) -> None:
        """
        Writes the transaction list to the output Excel file with styling.
        Appends Category and Audit Description columns.
        """
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating output Excel workbook at: {self.output_path}")

        # Create workbook and sheet
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Classified Transactions"

        # Ensure gridlines are visible
        ws.views.sheetView[0].showGridLines = True

        # Columns definition
        headers = [
            "Date",
            "Narration",
            "Reference",
            "Debit",
            "Credit",
            "Balance",
            "Category",
            "Nature",
            "Description",
            "Confidence"
        ]

        # Define Styles
        font_family = "Segoe UI"
        
        # Header Styling
        header_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")  # Dark Navy Blue
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Data Styling
        data_font = Font(name=font_family, size=10)
        
        # Highlight fill for the AI classified columns (soft pastel blue/gray)
        ai_highlight_fill = PatternFill(start_color="F2F7FA", end_color="F2F7FA", fill_type="solid")
        
        # Alignments
        left_align = Alignment(horizontal="left", vertical="center")
        center_align = Alignment(horizontal="center", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")

        # Borders
        thin_side = Side(border_style="thin", color="D3D3D3")
        thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        # Write Headers
        ws.row_dimensions[1].height = 28
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # Write Data
        for row_idx, txn in enumerate(transactions, 2):
            ws.row_dimensions[row_idx].height = 20

            # 1. Date
            c_date = ws.cell(row=row_idx, column=1, value=txn.get("date", ""))
            c_date.alignment = center_align

            # 2. Narration
            c_narr = ws.cell(row=row_idx, column=2, value=txn.get("narration", ""))
            c_narr.alignment = left_align

            # 3. Reference
            c_ref = ws.cell(row=row_idx, column=3, value=txn.get("reference", ""))
            c_ref.alignment = center_align

            # 4. Debit (Write None/Blank if 0.0 for clean ledger appearance)
            debit_val = txn.get("debit", 0.0)
            c_deb = ws.cell(row=row_idx, column=4, value=debit_val if debit_val != 0.0 else None)
            c_deb.number_format = "#,##0.00"
            c_deb.alignment = right_align

            # 5. Credit (Write None/Blank if 0.0)
            credit_val = txn.get("credit", 0.0)
            c_cred = ws.cell(row=row_idx, column=5, value=credit_val if credit_val != 0.0 else None)
            c_cred.number_format = "#,##0.00"
            c_cred.alignment = right_align

            # 6. Balance
            c_bal = ws.cell(row=row_idx, column=6, value=txn.get("balance", 0.0))
            c_bal.number_format = "#,##0.00"
            c_bal.alignment = right_align

            # 7. Category (AI)
            c_cat = ws.cell(row=row_idx, column=7, value=txn.get("category", ""))
            c_cat.fill = ai_highlight_fill
            c_cat.font = Font(name=font_family, size=10, bold=True, color="1F4E79")
            c_cat.alignment = left_align

            # 8. Nature (AI)
            c_nat = ws.cell(row=row_idx, column=8, value=txn.get("nature", ""))
            c_nat.fill = ai_highlight_fill
            c_nat.font = Font(name=font_family, size=10, bold=True, color="1F4E79")
            c_nat.alignment = left_align

            # 9. Description (AI)
            c_desc = ws.cell(row=row_idx, column=9, value=txn.get("description", ""))
            c_desc.fill = ai_highlight_fill
            c_desc.alignment = left_align

            # 10. Confidence (AI)
            conf_val = txn.get("confidence", 0)
            c_conf = ws.cell(row=row_idx, column=10, value=f"{conf_val}%" if conf_val is not None else "")
            c_conf.fill = ai_highlight_fill
            c_conf.font = Font(name=font_family, size=10, color="1F4E79")
            c_conf.alignment = center_align

            # Apply font and border to all cells in the row
            for col_idx in range(1, 11):
                cell = ws.cell(row=row_idx, column=col_idx)
                if col_idx not in (7, 8, 9, 10):  # AI fields keep custom fonts
                    cell.font = data_font
                cell.border = thin_border

        # Auto-fit columns with sensible padding and wrapping
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            
            # Check length of values in each cell
            for cell in col:
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)

            # Apply widths
            if col_letter == "B":  # Narration
                ws.column_dimensions[col_letter].width = min(max(max_len + 3, 20), 55)
                # Enable text wrapping for long narrations
                for cell in col[1:]:
                    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            elif col_letter == "I":  # Description
                ws.column_dimensions[col_letter].width = min(max(max_len + 3, 20), 65)
                for cell in col[1:]:
                    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            else:
                ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        # Save workbook
        wb.save(self.output_path)
        logger.info(f"Successfully wrote {len(transactions)} rows to {self.output_path}")
