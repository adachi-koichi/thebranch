"""Accounting department services for invoices, expenses, and reporting"""

import logging
import json
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List, Dict
from calendar import monthrange

from workflow.exceptions import ValidationError

if TYPE_CHECKING:
    from workflow.repositories.accounting_repository import AccountingRepository

logger = logging.getLogger(__name__)


class AccountingService:
    """
    会計部管理サービス。

    責務：
    - 請求書CRUD・承認フロー管理
    - 経費申請CRUD・承認フロー管理
    - 月次集計処理
    - レポート生成
    """

    def __init__(self, accounting_repo: 'AccountingRepository') -> None:
        self.accounting_repo = accounting_repo

    # ──────────────────────────────────────────────
    # Invoice Methods
    # ──────────────────────────────────────────────

    def create_invoice(
        self,
        department_id: int,
        invoice_number: str,
        vendor_name: str,
        invoice_date: str,
        due_date: str,
        amount_jpy: float,
        tax_amount_jpy: float = 0.0,
        description: Optional[str] = None,
        vendor_id: Optional[int] = None,
    ) -> int:
        """Create new invoice"""
        if not invoice_number or not vendor_name:
            raise ValidationError("invoice_number and vendor_name are required")
        if amount_jpy < 0:
            raise ValidationError("amount_jpy must be non-negative")

        invoice_id = self.accounting_repo.add_invoice(
            department_id=department_id,
            invoice_number=invoice_number,
            vendor_name=vendor_name,
            invoice_date=invoice_date,
            due_date=due_date,
            amount_jpy=amount_jpy,
            tax_amount_jpy=tax_amount_jpy,
            description=description,
            vendor_id=vendor_id,
        )

        logger.info(
            f"Invoice created: dept_id={department_id}, "
            f"invoice_number={invoice_number}, amount={amount_jpy}"
        )
        return invoice_id

    def get_invoice(self, invoice_id: int) -> Optional[Dict]:
        """Get invoice with items"""
        invoice = self.accounting_repo.get_invoice(invoice_id)
        if not invoice:
            return None

        items = self.accounting_repo.get_invoice_items(invoice_id)
        invoice['items'] = items
        return invoice

    def get_invoices(
        self, department_id: int, status: Optional[str] = None
    ) -> List[Dict]:
        """Get invoices for department"""
        return self.accounting_repo.get_invoices_by_department(department_id, status)

    def add_invoice_item(
        self,
        invoice_id: int,
        item_description: str,
        quantity: float,
        unit_price_jpy: float,
        line_amount_jpy: float,
    ) -> int:
        """Add line item to invoice"""
        if quantity <= 0 or unit_price_jpy < 0:
            raise ValidationError("Invalid quantity or unit_price")

        item_id = self.accounting_repo.add_invoice_item(
            invoice_id=invoice_id,
            item_description=item_description,
            quantity=quantity,
            unit_price_jpy=unit_price_jpy,
            line_amount_jpy=line_amount_jpy,
        )
        logger.info(f"Invoice item added: invoice_id={invoice_id}, item_id={item_id}")
        return item_id

    def approve_invoice(self, invoice_id: int, approver_id: int) -> None:
        """Approve invoice"""
        invoice = self.accounting_repo.get_invoice(invoice_id)
        if not invoice:
            raise ValidationError(f"Invoice {invoice_id} not found")

        self.accounting_repo.approve_invoice(invoice_id, approver_id)
        self.accounting_repo.update_invoice_status(invoice_id, "approved", "approved")

        logger.info(f"Invoice approved: invoice_id={invoice_id}, approver_id={approver_id}")

    def update_invoice_status(
        self, invoice_id: int, status: str, approval_status: Optional[str] = None
    ) -> None:
        """Update invoice status"""
        valid_statuses = ['pending', 'approved', 'rejected', 'paid']
        if status not in valid_statuses:
            raise ValidationError(f"Invalid status: {status}")

        self.accounting_repo.update_invoice_status(invoice_id, status, approval_status)
        logger.info(f"Invoice status updated: invoice_id={invoice_id}, status={status}")

    # ──────────────────────────────────────────────
    # Expense Methods
    # ──────────────────────────────────────────────

    def create_expense_submission(
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
        """Create new expense submission"""
        if not submission_number or not employee_name:
            raise ValidationError("submission_number and employee_name are required")
        if total_amount_jpy < 0:
            raise ValidationError("total_amount_jpy must be non-negative")

        submission_id = self.accounting_repo.add_expense_submission(
            department_id=department_id,
            submission_number=submission_number,
            employee_name=employee_name,
            submission_date=submission_date,
            period_start=period_start,
            period_end=period_end,
            total_amount_jpy=total_amount_jpy,
            description=description,
            employee_id=employee_id,
        )

        logger.info(
            f"Expense submission created: dept_id={department_id}, "
            f"submission_number={submission_number}, amount={total_amount_jpy}"
        )
        return submission_id

    def get_expense_submission(self, submission_id: int) -> Optional[Dict]:
        """Get expense submission with items"""
        submission = self.accounting_repo.get_expense_submission(submission_id)
        if not submission:
            return None

        items = self.accounting_repo.get_expense_items(submission_id)
        submission['items'] = items
        return submission

    def get_expense_submissions(
        self, department_id: int, status: Optional[str] = None
    ) -> List[Dict]:
        """Get expense submissions for department"""
        return self.accounting_repo.get_expense_submissions_by_department(
            department_id, status
        )

    def add_expense_item(
        self,
        submission_id: int,
        expense_category: str,
        expense_date: str,
        description: str,
        amount_jpy: float,
        receipt_file_path: Optional[str] = None,
    ) -> int:
        """Add line item to expense submission"""
        valid_categories = ['travel', 'meals', 'supplies', 'accommodation', 'other']
        if expense_category not in valid_categories:
            raise ValidationError(f"Invalid expense_category: {expense_category}")
        if amount_jpy <= 0:
            raise ValidationError("amount_jpy must be positive")

        item_id = self.accounting_repo.add_expense_item(
            submission_id=submission_id,
            expense_category=expense_category,
            expense_date=expense_date,
            description=description,
            amount_jpy=amount_jpy,
            receipt_file_path=receipt_file_path,
        )
        logger.info(
            f"Expense item added: submission_id={submission_id}, "
            f"category={expense_category}, amount={amount_jpy}"
        )
        return item_id

    def approve_expense_submission(self, submission_id: int, approver_id: int) -> None:
        """Approve expense submission"""
        submission = self.accounting_repo.get_expense_submission(submission_id)
        if not submission:
            raise ValidationError(f"Expense submission {submission_id} not found")

        self.accounting_repo.approve_expense_submission(submission_id, approver_id)

        logger.info(
            f"Expense submission approved: submission_id={submission_id}, "
            f"approver_id={approver_id}"
        )

    # ──────────────────────────────────────────────
    # Monthly Report Methods
    # ──────────────────────────────────────────────

    def generate_monthly_report(
        self, department_id: int, year: int, month: int
    ) -> Dict:
        """Generate monthly accounting report"""
        last_day = monthrange(year, month)[1]
        period_start = f"{year}-{month:02d}-01"
        period_end = f"{year}-{month:02d}-{last_day}"

        # Get all invoices and expenses for the month
        invoices = self.accounting_repo.get_invoices_by_department(department_id)
        expenses = self.accounting_repo.get_expense_submissions_by_department(
            department_id
        )

        # Calculate totals
        invoice_total = 0.0
        approved_invoices = 0
        pending_invoices = 0

        for inv in invoices:
            if period_start <= inv['invoice_date'] <= period_end:
                invoice_total += inv['total_amount_jpy']
                if inv['approval_status'] == 'approved':
                    approved_invoices += inv['total_amount_jpy']
                else:
                    pending_invoices += inv['total_amount_jpy']

        expense_total = 0.0
        approved_expenses = 0
        pending_expenses = 0

        for exp in expenses:
            if period_start <= exp['period_start'] <= period_end:
                expense_total += exp['total_amount_jpy']
                if exp['approval_status'] == 'approved':
                    approved_expenses += exp['total_amount_jpy']
                else:
                    pending_expenses += exp['total_amount_jpy']

        total_approved = approved_invoices + approved_expenses
        total_pending = pending_invoices + pending_expenses

        return {
            'department_id': department_id,
            'year': year,
            'month': month,
            'period_start': period_start,
            'period_end': period_end,
            'total_invoiced_jpy': invoice_total,
            'total_expenses_jpy': expense_total,
            'total_approved_jpy': total_approved,
            'pending_approval_jpy': total_pending,
            'invoice_count': len([i for i in invoices if period_start <= i['invoice_date'] <= period_end]),
            'expense_count': len([e for e in expenses if period_start <= e['period_start'] <= period_end]),
        }

    def get_pending_approvals(self, department_id: int) -> Dict:
        """Get all pending approvals for department"""
        invoices = self.accounting_repo.get_invoices_by_department(
            department_id, status='pending'
        )
        expenses = self.accounting_repo.get_expense_submissions_by_department(
            department_id, status='pending'
        )

        pending_invoice_total = sum(inv['total_amount_jpy'] for inv in invoices)
        pending_expense_total = sum(exp['total_amount_jpy'] for exp in expenses)

        return {
            'pending_invoices': len(invoices),
            'pending_invoices_amount': pending_invoice_total,
            'pending_expenses': len(expenses),
            'pending_expenses_amount': pending_expense_total,
            'total_pending_amount': pending_invoice_total + pending_expense_total,
        }

    def get_expense_summary_by_category(
        self, department_id: int, year: int, month: int
    ) -> Dict:
        """Get expense summary grouped by category"""
        last_day = monthrange(year, month)[1]
        period_start = f"{year}-{month:02d}-01"
        period_end = f"{year}-{month:02d}-{last_day}"

        expenses = self.accounting_repo.get_expense_submissions_by_department(
            department_id
        )

        category_totals = {}
        for exp in expenses:
            if period_start <= exp['period_start'] <= period_end:
                items = self.accounting_repo.get_expense_items(exp['id'])
                for item in items:
                    category = item['expense_category']
                    amount = item['amount_jpy']
                    category_totals[category] = category_totals.get(category, 0) + amount

        return {
            'year': year,
            'month': month,
            'category_breakdown': category_totals,
            'top_category': max(category_totals, key=category_totals.get)
            if category_totals else None,
        }
