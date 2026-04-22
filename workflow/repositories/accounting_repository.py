from datetime import datetime
from typing import Optional, List
from workflow.repositories.base import BaseRepository


class AccountingRepository(BaseRepository):
    """Data access for accounting department"""

    def add_invoice(
        self,
        department_id: int,
        invoice_number: str,
        vendor_name: str,
        invoice_date: str,
        due_date: str,
        amount_jpy: float,
        tax_amount_jpy: float = 0,
        description: Optional[str] = None,
        vendor_id: Optional[int] = None,
    ) -> int:
        """Insert invoice, return invoices.id"""
        now = datetime.now().isoformat()
        total_amount_jpy = amount_jpy + tax_amount_jpy
        query = '''
            INSERT INTO invoices
            (department_id, invoice_number, vendor_id, vendor_name, invoice_date,
             due_date, amount_jpy, tax_amount_jpy, total_amount_jpy, description,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        invoice_id = self.execute_insert(
            query,
            (
                department_id, invoice_number, vendor_id, vendor_name, invoice_date,
                due_date, amount_jpy, tax_amount_jpy, total_amount_jpy, description,
                now, now
            )
        )
        return invoice_id

    def get_invoice(self, invoice_id: int) -> Optional[dict]:
        """Get invoice by ID"""
        query = 'SELECT * FROM invoices WHERE id = ?'
        row = self.execute_one(query, (invoice_id,))
        return dict(row) if row else None

    def get_invoices_by_department(
        self, department_id: int, status: Optional[str] = None
    ) -> List[dict]:
        """Get invoices for department, optionally filtered by status"""
        if status:
            query = '''
                SELECT * FROM invoices
                WHERE department_id = ? AND status = ?
                ORDER BY created_at DESC
            '''
            rows = self.execute_all(query, (department_id, status))
        else:
            query = '''
                SELECT * FROM invoices
                WHERE department_id = ?
                ORDER BY created_at DESC
            '''
            rows = self.execute_all(query, (department_id,))
        return [dict(row) for row in rows]

    def update_invoice_status(
        self, invoice_id: int, status: str, approval_status: Optional[str] = None
    ) -> None:
        """Update invoice status"""
        now = datetime.now().isoformat()
        if approval_status:
            query = '''
                UPDATE invoices
                SET status = ?, approval_status = ?, updated_at = ?
                WHERE id = ?
            '''
            self.execute_update(query, (status, approval_status, now, invoice_id))
        else:
            query = '''
                UPDATE invoices
                SET status = ?, updated_at = ?
                WHERE id = ?
            '''
            self.execute_update(query, (status, now, invoice_id))

    def approve_invoice(
        self, invoice_id: int, approver_id: int
    ) -> None:
        """Mark invoice as approved"""
        now = datetime.now().isoformat()
        query = '''
            UPDATE invoices
            SET approval_status = 'approved', approver_id = ?, approved_at = ?,
                updated_at = ?
            WHERE id = ?
        '''
        self.execute_update(query, (approver_id, now, now, invoice_id))

    def add_expense_submission(
        self,
        department_id: int,
        submission_number: str,
        employee_name: str,
        submission_date: str,
        period_start: str,
        period_end: str,
        total_amount_jpy: float,
        description: Optional[str] = None,
        employee_id: Optional[int] = None,
    ) -> int:
        """Insert expense submission, return expense_submissions.id"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO expense_submissions
            (department_id, submission_number, employee_id, employee_name,
             submission_date, period_start, period_end, total_amount_jpy,
             description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        submission_id = self.execute_insert(
            query,
            (
                department_id, submission_number, employee_id, employee_name,
                submission_date, period_start, period_end, total_amount_jpy,
                description, now, now
            )
        )
        return submission_id

    def get_expense_submission(self, submission_id: int) -> Optional[dict]:
        """Get expense submission by ID"""
        query = 'SELECT * FROM expense_submissions WHERE id = ?'
        row = self.execute_one(query, (submission_id,))
        return dict(row) if row else None

    def get_expense_submissions_by_department(
        self, department_id: int, status: Optional[str] = None
    ) -> List[dict]:
        """Get expense submissions for department"""
        if status:
            query = '''
                SELECT * FROM expense_submissions
                WHERE department_id = ? AND status = ?
                ORDER BY created_at DESC
            '''
            rows = self.execute_all(query, (department_id, status))
        else:
            query = '''
                SELECT * FROM expense_submissions
                WHERE department_id = ?
                ORDER BY created_at DESC
            '''
            rows = self.execute_all(query, (department_id,))
        return [dict(row) for row in rows]

    def approve_expense_submission(
        self, submission_id: int, approver_id: int
    ) -> None:
        """Mark expense submission as approved"""
        now = datetime.now().isoformat()
        query = '''
            UPDATE expense_submissions
            SET approval_status = 'approved', approver_id = ?, approved_at = ?,
                updated_at = ?
            WHERE id = ?
        '''
        self.execute_update(query, (approver_id, now, now, submission_id))

    def add_invoice_item(
        self,
        invoice_id: int,
        item_description: str,
        quantity: float,
        unit_price_jpy: float,
        line_amount_jpy: float,
    ) -> int:
        """Insert invoice line item"""
        query = '''
            INSERT INTO invoice_items
            (invoice_id, item_description, quantity, unit_price_jpy, line_amount_jpy)
            VALUES (?, ?, ?, ?, ?)
        '''
        item_id = self.execute_insert(
            query,
            (invoice_id, item_description, quantity, unit_price_jpy, line_amount_jpy)
        )
        return item_id

    def get_invoice_items(self, invoice_id: int) -> List[dict]:
        """Get items for invoice"""
        query = 'SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id'
        rows = self.execute_all(query, (invoice_id,))
        return [dict(row) for row in rows]

    def add_expense_item(
        self,
        submission_id: int,
        expense_category: str,
        expense_date: str,
        description: str,
        amount_jpy: float,
        receipt_file_path: Optional[str] = None,
    ) -> int:
        """Insert expense line item"""
        query = '''
            INSERT INTO expense_items
            (submission_id, expense_category, expense_date, description, amount_jpy,
             receipt_file_path)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        item_id = self.execute_insert(
            query,
            (submission_id, expense_category, expense_date, description, amount_jpy,
             receipt_file_path)
        )
        return item_id

    def get_expense_items(self, submission_id: int) -> List[dict]:
        """Get items for expense submission"""
        query = 'SELECT * FROM expense_items WHERE submission_id = ? ORDER BY id'
        rows = self.execute_all(query, (submission_id,))
        return [dict(row) for row in rows]

    def add_monthly_report(
        self,
        department_id: int,
        year: int,
        month: int,
        total_invoices_amount: float,
        total_invoices_count: int,
        total_expenses_amount: float,
        total_expenses_count: int,
        total_approved_amount: float,
        total_pending_amount: float,
        generated_by_agent_id: Optional[int] = None,
    ) -> int:
        """Insert monthly report"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO monthly_reports
            (department_id, year, month, total_invoices_amount, total_invoices_count,
             total_expenses_amount, total_expenses_count, total_approved_amount,
             total_pending_amount, generated_at, generated_by_agent_id,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        report_id = self.execute_insert(
            query,
            (
                department_id, year, month, total_invoices_amount, total_invoices_count,
                total_expenses_amount, total_expenses_count, total_approved_amount,
                total_pending_amount, now, generated_by_agent_id, now, now
            )
        )
        return report_id

    def get_monthly_report(
        self, department_id: int, year: int, month: int
    ) -> Optional[dict]:
        """Get monthly report"""
        query = '''
            SELECT * FROM monthly_reports
            WHERE department_id = ? AND year = ? AND month = ?
        '''
        row = self.execute_one(query, (department_id, year, month))
        return dict(row) if row else None
