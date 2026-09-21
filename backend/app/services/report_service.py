from io import BytesIO
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.models.exam_schedule import ExamSchedule
from app.models.exam_session import ExamSession
from app.models.violation_log import ViolationLog
from app.schemas.report_schema import ExamScheduleStatistics, StudentResultItem

class ReportService:
    @staticmethod
    def get_schedule_statistics(db: Session, schedule_id: int) -> ExamScheduleStatistics:
        schedule = db.query(ExamSchedule).options(
            joinedload(ExamSchedule.exam),
            joinedload(ExamSchedule.sessions).joinedload(ExamSession.student),
            joinedload(ExamSchedule.sessions).joinedload(ExamSession.violation_logs)
        ).filter(ExamSchedule.id == schedule_id).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Không tìm thấy ca thi")

        candidates = []
        scores = []
        for s in schedule.sessions:
            v_count = len(s.violation_logs)
            f_score = float(s.final_score) if s.final_score is not None else None
            if f_score is not None:
                scores.append(f_score)

            candidates.append(StudentResultItem(
                session_id=s.id,
                student_id=s.student.id,
                student_name=s.student.full_name,
                student_code=s.student.student_code,
                email=s.student.email,
                started_at=s.started_at,
                submitted_at=s.submitted_at,
                submit_type=s.submit_type,
                status=s.status,
                final_score=f_score,
                total_score=float(schedule.exam.total_score),
                risk_score=s.risk_score,
                tab_switch_count=s.tab_switch_count,
                fullscreen_exit_count=s.fullscreen_exit_count,
                violation_count=v_count
            ))

        total_cand = len(candidates)
        submitted = len([c for c in candidates if c.status == "SUBMITTED"])
        in_prog = len([c for c in candidates if c.status == "IN_PROGRESS"])
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        max_score = max(scores) if scores else 0.0
        min_score = min(scores) if scores else 0.0

        return ExamScheduleStatistics(
            schedule_id=schedule.id,
            room_code=schedule.room_code,
            exam_title=schedule.exam.title,
            total_candidates=total_cand,
            submitted_count=submitted,
            in_progress_count=in_prog,
            average_score=avg_score,
            highest_score=max_score,
            lowest_score=min_score,
            candidates=candidates
        )

    @staticmethod
    def export_excel(db: Session, schedule_id: int) -> BytesIO:
        stats = ReportService.get_schedule_statistics(db, schedule_id)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "KetQuaThi"

        # Headers
        headers = [
            "STT", "Mã SV", "Họ và Tên", "Email", "Trạng Thái",
            "Điểm Số", "Điểm Rủi Ro", "Chuyển Tab", "Thoát Fullscreen",
            "Tổng Vi Phạm", "Hình Thức Nộp", "Thời Gian Nộp"
        ]
        
        # Title row
        ws.merge_cells("A1:L1")
        ws["A1"] = f"BÁO CÁO KẾT QUẢ THI - PHÒNG: {stats.room_code} ({stats.exam_title})"
        ws["A1"].font = Font(size=14, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 30

        # Stats summary row
        ws.merge_cells("A2:L2")
        ws["A2"] = f"Tổng thí sinh: {stats.total_candidates} | Đã nộp: {stats.submitted_count} | Điểm TB: {stats.average_score} | Điểm cao nhất: {stats.highest_score}"
        ws["A2"].font = Font(size=10, italic=True)
        ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

        # Table Header Row
        ws.append([]) # Row 3 empty
        ws.append(headers) # Row 4
        
        header_fill = PatternFill(start_color="F4F4F5", end_color="F4F4F5", fill_type="solid")
        header_font = Font(bold=True, color="18181B")
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=4, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        # Rows
        thin_border = Border(
            left=Side(style='thin', color='E4E4E7'),
            right=Side(style='thin', color='E4E4E7'),
            top=Side(style='thin', color='E4E4E7'),
            bottom=Side(style='thin', color='E4E4E7')
        )

        for idx, cand in enumerate(stats.candidates, start=1):
            sub_time_str = cand.submitted_at.strftime("%H:%M:%S %d/%m/%Y") if cand.submitted_at else "Chưa nộp"
            score_display = cand.final_score if cand.final_score is not None else "N/A"
            row_data = [
                idx,
                cand.student_code or "N/A",
                cand.student_name,
                cand.email,
                cand.status,
                score_display,
                cand.risk_score,
                cand.tab_switch_count,
                cand.fullscreen_exit_count,
                cand.violation_count,
                cand.submit_type or "N/A",
                sub_time_str
            ]
            ws.append(row_data)
            row_idx = 4 + idx
            for c_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=row_idx, column=c_idx)
                cell.border = thin_border
                if c_idx in [1, 2, 5, 6, 7, 8, 9, 10, 11]:
                    cell.alignment = Alignment(horizontal="center")

        # Column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 10)

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def export_pdf(db: Session, schedule_id: int) -> BytesIO:
        stats = ReportService.get_schedule_statistics(db, schedule_id)
        
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#2563EB"),
            alignment=1
        )
        sub_style = ParagraphStyle(
            'DocSub',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            alignment=1,
            textColor=colors.HexColor("#52525B")
        )

        elements.append(Paragraph(f"BÁO CÁO KẾT QUẢ THI", title_style))
        elements.append(Paragraph(f"Phòng thi: <b>{stats.room_code}</b> | Đề thi: {stats.exam_title}", sub_style))
        elements.append(Paragraph(f"Thời gian xuất báo cáo: {datetime.now().strftime('%d/%m/%Y %H:%M')}", sub_style))
        elements.append(Spacer(1, 15))

        # Table data
        table_data = [
            ["STT", "MSSV", "Họ Tên", "Điểm", "Rủi ro", "Chuyển Tab", "Thoát FS", "Trạng Thái"]
        ]
        for idx, cand in enumerate(stats.candidates, start=1):
            score_text = str(cand.final_score) if cand.final_score is not None else "--"
            table_data.append([
                str(idx),
                cand.student_code or "N/A",
                cand.student_name,
                score_text,
                str(cand.risk_score),
                str(cand.tab_switch_count),
                str(cand.fullscreen_exit_count),
                cand.status
            ])

        col_widths = [30, 70, 150, 45, 45, 65, 65, 65]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2563EB")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E4E4E7")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ]))
        elements.append(t)

        doc.build(elements)
        output.seek(0)
        return output
