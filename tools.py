from datetime import datetime
from datetime import datetime, timedelta
from datetime import datetime, timedelta, date
from typing import Any, Dict
from typing import Any, Dict, Optional
import json
import random

class Tools:
    @staticmethod
    def list_customer_accounts_apply(
        data: Dict[str, Any],
        account_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        account_type: Optional[str] = None,
        status: Optional[str] = None,
        balance_min: Optional[int] = None,
        balance_max: Optional[int] = None
    ) -> str:
        accounts = data.get('accounts', {})
        results = []

        for aid, acc in accounts.items():
            # Filter by account_id (exact)
            if account_id is not None:
                try:
                    if int(aid) != account_id:
                        continue
                except (ValueError, TypeError):
                    continue

            # Filter by customer_id (exact)
            if customer_id is not None and acc.get('customer_id') != customer_id:
                continue

            # Filter by branch_id (exact)
            if branch_id is not None and acc.get('branch_id') != branch_id:
                continue

            # Filter by account_type (exact, case-insensitive)
            if account_type and acc.get('type', '').lower() != account_type.lower():
                continue

            # Filter by status (exact, case-insensitive)
            if status and acc.get('status', '').lower() != status.lower():
                continue

            # Filter by balance_min (exact integer comparison)
            if balance_min is not None:
                try:
                    if int(acc.get('balance', 0)) < balance_min:
                        continue
                except (TypeError, ValueError):
                    continue

            # Filter by balance_max (exact integer comparison)
            if balance_max is not None:
                try:
                    if int(acc.get('balance', 0)) > balance_max:
                        continue
                except (TypeError, ValueError):
                    continue

            results.append(acc)

        return json.dumps(results)

    @staticmethod
    def list_card_transactions_apply(
        data: Dict[str, Any],
        card_id: Optional[int] = None,
        type: Optional[str] = None,
        channel: Optional[str] = None,
        amount_min: Optional[int] = None,
        amount_max: Optional[int] = None,
        occurred_from: Optional[str] = None,
        occurred_to: Optional[str] = None,
        merchant: Optional[str] = None,
        card_tx_status: Optional[str] = None
    ) -> str:
        transactions = data.get('transactions', {})
        results = []

        merchant_lower = merchant.lower() if merchant else None

        # Parse occurred_from/to ISO strings into datetimes
        occ_from_dt: Optional[datetime] = None
        occ_to_dt: Optional[datetime] = None
        if occurred_from:
            try:
                occ_from_dt = datetime.fromisoformat(occurred_from)
            except ValueError:
                return "Error: 'occurred_from' must be an ISO datetime string"
        if occurred_to:
            try:
                occ_to_dt = datetime.fromisoformat(occurred_to)
            except ValueError:
                return "Error: 'occurred_to' must be an ISO datetime string"

        def parse_date(t: Dict[str, Any]) -> datetime:
            occ = t.get('occurred_at')
            if isinstance(occ, str):
                try:
                    return datetime.fromisoformat(occ)
                except ValueError:
                    pass
            if isinstance(occ, datetime):
                return occ
            return datetime.min

        for txn in transactions.values():
            # Filter by card_id (exact)
            if card_id is not None and txn.get('card_id') != card_id:
                continue

            # Filter by type (exact)
            if type and txn.get('type') != type:
                continue

            # Filter by channel (exact)
            if channel and txn.get('channel') != channel:
                continue

            # Filter by amount range
            amt = txn.get('amount')
            if amount_min is not None and amt < amount_min:
                continue
            if amount_max is not None and amt > amount_max:
                continue

            # Filter by occurred_at range
            occ_dt = parse_date(txn)
            if occ_from_dt and occ_dt < occ_from_dt:
                continue
            if occ_to_dt and occ_dt > occ_to_dt:
                continue

            # Partial, case-insensitive match on merchant
            if merchant_lower and merchant_lower not in txn.get('merchant', '').lower():
                continue

            # Filter by card_tx_status (exact)
            if card_tx_status and txn.get('card_tx_status') != card_tx_status:
                continue

            results.append(txn)

        return json.dumps(results)

    @staticmethod
    def make_payment_apply(
        data: Dict[str, Any],
        account_id: int,
        beneficiary_id: int,
        product_type: str,
        amount: int,
        channel: str
    ) -> str:
        accounts = data.get('accounts', {})
        beneficiaries = data.get('beneficiaries', {})
        loans = data.get('loans', {})
        cards = data.get('cards', {})
        transactions = data.get('transactions', {})

        # Validate product_type
        if not isinstance(product_type, str):
            return "Error: 'product_type' must be a string"
        pt = product_type.upper()
        if pt not in {"LOAN", "CARD"}:
            return "Error: 'product_type' must be 'LOAN' or 'CARD'"

        # Validate account_id
        if not isinstance(account_id, int):
            return "Error: 'account_id' must be an integer"
        acct_key = None
        for aid in accounts:
            try:
                if int(aid) == account_id:
                    acct_key = aid
                    break
            except (ValueError, TypeError):
                continue
        if acct_key is None:
            return f"Error: Account '{account_id}' not found"
        account = accounts[acct_key]

        # Validate beneficiary_id
        ben = beneficiaries.get(str(beneficiary_id))
        if not ben:
            return f"Error: Beneficiary '{beneficiary_id}' not found"

        # Check beneficiary type matches product_type
        if pt == "LOAN":
            if ben.get('beneficiary_type') != 'LOAN_ACCOUNT':
                return "Error: Beneficiary is not a loan account"
            # find corresponding loan
            loan_acct_num = ben.get('account_number')
            loan_match = next((ln for ln in loans.values()
                               if ln.get('loan_account_number') == loan_acct_num), None)
            if not loan_match:
                return f"Error: No loan found for beneficiary account '{loan_acct_num}'"
            card_id = None
        else:  # CARD
            if ben.get('beneficiary_type') != 'CARD':
                return "Error: Beneficiary is not a card"
            # find corresponding card
            card_num = ben.get('account_number')
            card_key = next((cid for cid, c in cards.items()
                             if c.get('card_number') == card_num), None)
            if card_key is None:
                return f"Error: No card found for beneficiary account '{card_num}'"
            card_id = int(card_key)

        # Validate amount
        if not isinstance(amount, int) or amount <= 0:
            return "Error: 'amount' must be a positive integer"

        # Validate channel
        if not isinstance(channel, str):
            return "Error: 'channel' must be a string"

        # Check sufficient funds
        current_balance = account.get('balance', 0)
        if amount > current_balance:
            return "Error: Insufficient funds"

        # Deduct from account
        account['balance'] = current_balance - amount
        account['updated_at'] = datetime.now().isoformat()

        # Generate transaction_id
        existing_ids = [int(tid) for tid in transactions.keys() if tid.isdigit()]
        new_txn_id = str(max(existing_ids) + 1) if existing_ids else "1"
        now = datetime.now().isoformat()

        # Build transaction
        txn = {
            "transaction_id": int(new_txn_id),
            "account_id": account_id,
            "type": "PAYMENT",
            "channel": channel,
            "amount": amount,
            "occurred_at": now,
            "beneficiary_id": beneficiary_id,
            "card_id": card_id,
            "merchant": None,
            "card_tx_status": None,
            "created_at": now
        }
        transactions[new_txn_id] = txn

        msg = "Loan payment successful" if pt == "LOAN" else "Card payment successful"
        return json.dumps({
            "message": msg,
            "transaction": txn
        }, default=str)

    @staticmethod
    def get_loan_amortization_schedule_apply(
        data: Dict[str, Any],
        loan_id: int
    ) -> str:
        loans = data.get('loans', {})
        # Find the loan record
        loan: Optional[Dict[str, Any]] = None
        for lid, ln in loans.items():
            try:
                if int(lid) == loan_id:
                    loan = ln
                    break
            except (ValueError, TypeError):
                continue

        if not loan:
            return f"Error: Loan '{loan_id}' not found"

        # Extract loan parameters
        principal = loan.get('principal_amount', 0)
        annual_rate = loan.get('interest_rate', 0)
        tenure = loan.get('tenure', 0)
        start_date_str = loan.get('start_date')

        # Parse start date
        try:
            period_start = datetime.fromisoformat(start_date_str)
        except Exception:
            return f"Error: Invalid start_date '{start_date_str}' for loan '{loan_id}'"

        # Monthly interest rate
        monthly_rate = annual_rate / 100 / 12
        n = tenure if tenure > 0 else 1

        # Calculate fixed monthly payment
        if monthly_rate > 0:
            payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** (-n))
        else:
            payment = principal / n

        # Build the amortization schedule
        schedule = []
        balance = principal

        for _ in range(n):
            interest = balance * monthly_rate
            principal_paid = payment - interest
            # Avoid negative balance in last period
            if principal_paid > balance:
                principal_paid = balance
                payment = principal_paid + interest
            balance -= principal_paid

            # Compute period_end as last day before next month
            year = period_start.year + (period_start.month // 12)
            month = period_start.month % 12 + 1
            first_next_month = period_start.replace(year=year, month=month, day=1)
            period_end = first_next_month - timedelta(days=1)

            schedule.append({
                "period_start": period_start.strftime("%Y-%m-%d"),
                "period_end": period_end.strftime("%Y-%m-%d"),
                "scheduled_amount": round(payment, 2),
                "principal": round(principal_paid, 2),
                "interest": round(interest, 2),
                "balance": round(balance, 2)
            })

            # Advance to next period
            period_start = first_next_month

        return json.dumps(schedule)

    @staticmethod
    def generate_card_statement_apply(
        data: Dict[str, Any],
        card_id: int
    ) -> str:
        cards = data.get('cards', {})
        transactions = data.get('transactions', {})
        statements = data.get('card_statements', {})

        # Validate card_id
        if not isinstance(card_id, int):
            return "Error: 'card_id' must be an integer"
        card = None
        for cid, c in cards.items():
            try:
                if int(cid) == card_id:
                    card = c
                    break
            except (ValueError, TypeError):
                continue
        if card is None:
            return f"Error: Card '{card_id}' not found"

        # Determine period_start and period_end
        card_statements = [s for s in statements.values() if s.get('card_id') == card_id]
        if card_statements:
            prev_end = max(
                datetime.fromisoformat(s['period_end']).date()
                for s in card_statements
            )
        else:
            # first period starts at issue date
            try:
                prev_end = datetime.fromisoformat(card['issued_date']).date() - timedelta(days=1)
            except Exception:
                return "Error: card.issued_date is invalid"

        period_start = prev_end + timedelta(days=1)
        period_end = period_start + timedelta(days=29)  # 30-day billing cycle
        payment_due_date = period_end + timedelta(days=10)

        # Collect relevant transactions and mark them billed
        total_due = 0.0
        for txn in transactions.values():
            if txn.get('card_id') == card_id:
                # parse occurred_at
                occ = txn.get('occurred_at')
                try:
                    occ_dt = datetime.fromisoformat(occ).date() if isinstance(occ, str) else occ.date()
                except Exception:
                    continue
                if period_start <= occ_dt <= period_end:
                    total_due += txn.get('amount', 0)
                    # mark as billed
                    txn['card_tx_status'] = 'BILLED'

        total_due = round(total_due, 2)
        minimum_due = round(total_due * 0.10, 2)  # e.g., 10% minimum payment

        # Generate new statement_id
        existing_ids = [int(sid) for sid in statements.keys() if sid.isdigit()]
        new_sid = str(max(existing_ids) + 1) if existing_ids else "1"
        now_str = datetime.now().isoformat()

        stmt = {
            "statement_id": int(new_sid),
            "card_id": card_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "total_due": total_due,
            "minimum_due": minimum_due,
            "payment_due_date": payment_due_date.isoformat(),
            "late_fee_amount": 0.00,
            "penalty_rate_id": None,
            "status": "OPEN",
            "created_at": now_str
        }

        statements[new_sid] = stmt

        return json.dumps({
            "message": "Card statement generated successfully",
            "statement": stmt
        }, default=str)

    @staticmethod
    def get_bank_by_name_apply(
        data: Dict[str, Any],
        name: str
    ) -> str:
        banks = data.get('banks', {})
        name_lower = name.lower()

        # Partial, case-insensitive match on bank name
        for bank in banks.values():
            bank_name = bank.get('name', '')
            if name_lower in bank_name.lower():
                return json.dumps(bank)

        return f"Error: Bank matching '{name}' not found"

    @staticmethod
    def list_customer_cards_apply(
        data: Dict[str, Any],
        card_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        type: Optional[str] = None,
        status: Optional[str] = None,
        balance_min: Optional[int] = None,
        balance_max: Optional[int] = None,
        credit_limit_min: Optional[int] = None,
        credit_limit_max: Optional[int] = None
    ) -> str:
        cards = data.get('cards', {})
        results = []

        for cid, card in cards.items():
            # Filter by card_id (exact)
            if card_id is not None:
                try:
                    if int(cid) != card_id:
                        continue
                except (ValueError, TypeError):
                    continue

            # Filter by customer_id (exact)
            if customer_id is not None and card.get('customer_id') != customer_id:
                continue

            # Filter by type (exact, case-insensitive)
            if type and card.get('type', '').lower() != type.lower():
                continue

            # Filter by status (exact, case-insensitive)
            if status and card.get('status', '').lower() != status.lower():
                continue

            # Filter by balance range
            bal = card.get('balance', 0)
            if balance_min is not None and bal < balance_min:
                continue
            if balance_max is not None and bal > balance_max:
                continue

            # Filter by credit limit range
            limit = card.get('credit_limit', 0)
            if credit_limit_min is not None and limit < credit_limit_min:
                continue
            if credit_limit_max is not None and limit > credit_limit_max:
                continue

            results.append(card)

        return json.dumps(results)

    @staticmethod
    def make_card_purchase_apply(
        data: Dict[str, Any],
        card_id: int,
        amount: int,
        merchant: str,
        channel: Optional[str] = 'POS'
    ) -> str:
        cards = data.get('cards', {})
        transactions = data.get('transactions', {})

        # Validate card_id
        if not isinstance(card_id, int):
            return "Error: 'card_id' must be an integer"
        # Locate card
        card_key = None
        for cid in cards:
            try:
                if int(cid) == card_id:
                    card_key = cid
                    break
            except (ValueError, TypeError):
                continue
        if card_key is None:
            return f"Error: Card '{card_id}' not found"

        # Validate amount
        if not isinstance(amount, int) or amount <= 0:
            return "Error: 'amount' must be a positive integer"

        # Validate merchant
        if not isinstance(merchant, str) or not merchant:
            return "Error: 'merchant' must be a non-empty string"

        # Validate channel
        if channel is not None and not isinstance(channel, str):
            return "Error: 'channel' must be a string"
        valid_channels = {"BRANCH", "ATM", "ONLINE", "MOBILE", "POS"}
        if channel not in valid_channels:
            return f"Error: 'channel' must be one of: {', '.join(valid_channels)}"

        # Enforce credit limit for CREDIT/PREPAID cards
        card = cards[card_key]
        ctype = card.get('type')
        if ctype in {'CREDIT', 'PREPAID'}:
            current_balance = card.get('balance', 0)
            credit_limit = card.get('credit_limit', 0)
            if current_balance + amount > credit_limit:
                return "Error: Credit limit exceeded"
            # update card balance (outstanding)
            card['balance'] = current_balance + amount
            card['updated_at'] = datetime.now().isoformat()

        # Generate new transaction_id
        existing_ids = [int(tid) for tid in transactions.keys() if tid.isdigit()]
        new_txn_id = str(max(existing_ids) + 1) if existing_ids else "1"
        now = datetime.now().isoformat()

        # Create transaction record
        txn = {
            "transaction_id": int(new_txn_id),
            "account_id": None,
            "type": "CARD_PURCHASE",
            "channel": channel,
            "amount": amount,
            "occurred_at": now,
            "beneficiary_id": None,
            "card_id": card_id,
            "merchant": merchant,
            "card_tx_status": "UNBILLED",
            "created_at": now
        }
        transactions[new_txn_id] = txn

        return json.dumps({
            "message": "Card purchase recorded",
            "transaction": txn
        }, default=str)

    @staticmethod
    def get_account_summary_apply(
        data: Dict[str, Any],
        account_id: int,
        recent_txns_count: Optional[int] = 3
    ) -> str:
        # account_id is required and must be int or int-like string
        try:
            acct_id = int(account_id)
        except (ValueError, TypeError):
            return "Error: 'account_id' must be an integer"

        # ensure recent_txns_count is an integer
        try:
            count = int(recent_txns_count)
        except (ValueError, TypeError):
            return "Error: 'recent_txns_count' must be an integer"

        accounts = data.get('accounts', {})
        transactions = data.get('transactions', {})

        # Fetch the account
        account = None
        for aid, acc in accounts.items():
            try:
                if int(aid) == acct_id:
                    account = acc
                    break
            except (ValueError, TypeError):
                continue

        if not account:
            return f"Error: Account '{acct_id}' not found"

        balance = account.get('balance')
        status = account.get('status')

        # Collect and sort transactions for this account
        filtered_txns = [
            txn for txn in transactions.values()
            if txn.get('account_id') == acct_id
        ]

        # Parse occurred_at and sort descending
        def parse_date(t: Dict[str, Any]) -> datetime:
            occurred = t.get('occurred_at')
            if isinstance(occurred, str):
                try:
                    return datetime.fromisoformat(occurred)
                except ValueError:
                    pass
            if isinstance(occurred, datetime):
                return occurred
            return datetime.min

        filtered_txns.sort(key=parse_date, reverse=True)
        recent_txns = filtered_txns[:count]

        summary = {
            "balance": balance,
            "status": status,
            "recent_txns": recent_txns
        }
        return json.dumps(summary, default=str)

    @staticmethod
    def issue_card_apply(
        data: Dict[str, Any],
        customer_id: int,
        card_type: str,
        credit_limit: int,
        expiry_date: str
    ) -> str:
        customers = data.get('customers', {})
        cards = data.get('cards', {})

        # Validate customer_id
        if not isinstance(customer_id, int):
            return "Error: 'customer_id' must be an integer"
        if str(customer_id) not in customers:
            return f"Error: Customer '{customer_id}' not found"

        # Validate card_type
        if not isinstance(card_type, str):
            return "Error: 'card_type' must be a string"
        valid_types = {"DEBIT", "CREDIT", "PREPAID"}
        if card_type not in valid_types:
            return f"Error: 'card_type' must be one of: {', '.join(valid_types)}"

        # Validate credit_limit
        if not isinstance(credit_limit, int) or credit_limit < 0:
            return "Error: 'credit_limit' must be a non-negative integer"

        # Validate expiry_date format
        try:
            exp = datetime.fromisoformat(expiry_date).date()
            expiry_str = exp.isoformat()
        except Exception:
            return "Error: 'expiry_date' must be a string in YYYY-MM-DD format"

        # Generate new card_id
        existing_ids = [int(cid) for cid in cards.keys() if cid.isdigit()]
        new_id = str(max(existing_ids) + 1) if existing_ids else "1"

        # Generate card_number
        card_number = f"CARD{new_id}"

        now = datetime.now()
        issued_date = now.date().isoformat()
        now_str = now.isoformat()

        # Create card record
        card = {
            "card_id": int(new_id),
            "customer_id": customer_id,
            "type": card_type,
            "card_number": card_number,
            "expiry_date": expiry_str,
            "issued_date": issued_date,
            "status": "ACTIVE",
            "balance": 0.00,
            "credit_limit": credit_limit,
            "created_at": now_str,
            "updated_at": now_str
        }

        cards[new_id] = card

        return json.dumps({
            "message": "Card issued successfully",
            "card": card
        }, default=str)

    @staticmethod
    def list_card_statements_apply(
        data: Dict[str, Any],
        card_id: Optional[int] = None,
        period_start_from: Optional[str] = None,
        period_end_to: Optional[str] = None,
        status: Optional[str] = None,
        total_due_min: Optional[int] = None,
        total_due_max: Optional[int] = None
    ) -> str:
        statements = data.get('card_statements', {})
        results = []

        def parse_date_str(d: Optional[str]) -> Optional[datetime.date]:
            if not d:
                return None
            try:
                return datetime.fromisoformat(d).date()
            except Exception:
                return None

        ps_filter = parse_date_str(period_start_from)
        pe_filter = parse_date_str(period_end_to)

        for sid, stmt in statements.items():
            # Filter by card_id (exact)
            if card_id is not None and stmt.get('card_id') != card_id:
                continue

            # Filter by period_start_from (inclusive)
            ps = parse_date_str(stmt.get('period_start'))
            if ps_filter and (ps is None or ps < ps_filter):
                continue

            # Filter by period_end_to (inclusive)
            pe = parse_date_str(stmt.get('period_end'))
            if pe_filter and (pe is None or pe > pe_filter):
                continue

            # Filter by status (exact, case-insensitive)
            if status and stmt.get('status', '').lower() != status.lower():
                continue

            # Filter by total_due range
            total_due = stmt.get('total_due', 0)
            if total_due_min is not None and total_due < total_due_min:
                continue
            if total_due_max is not None and total_due > total_due_max:
                continue

            results.append(stmt)

        return json.dumps(results)

    @staticmethod
    def update_card_apply(
        data: Dict[str, Any],
        card_id: int,
        credit_limit: Optional[int] = None,
        status: Optional[str] = None,
        expiry_date: Optional[str] = None
    ) -> str:
        cards = data.get('cards', {})

        # Validate card_id
        if not isinstance(card_id, int):
            return "Error: 'card_id' must be an integer"

        # Locate card
        card_key = None
        for cid in cards:
            try:
                if int(cid) == card_id:
                    card_key = cid
                    break
            except (ValueError, TypeError):
                continue
        if card_key is None:
            return f"Error: Card '{card_id}' not found"
        card = cards[card_key]

        # Update credit_limit if provided
        if credit_limit is not None:
            if not isinstance(credit_limit, int) or credit_limit < 0:
                return "Error: 'credit_limit' must be a non-negative integer"
            card['credit_limit'] = credit_limit

        # Update status if provided
        if status is not None:
            if not isinstance(status, str):
                return "Error: 'status' must be a string"
            valid_statuses = {"ACTIVE", "BLOCKED", "EXPIRED"}
            if status not in valid_statuses:
                return f"Error: 'status' must be one of: {', '.join(valid_statuses)}"
            card['status'] = status

        # Update expiry_date if provided
        if expiry_date is not None:
            if not isinstance(expiry_date, str):
                return "Error: 'expiry_date' must be a string in YYYY-MM-DD format"
            try:
                exp = datetime.fromisoformat(expiry_date).date()
                card['expiry_date'] = exp.isoformat()
            except Exception:
                return "Error: 'expiry_date' must be a string in YYYY-MM-DD format"

        # Update timestamp
        card['updated_at'] = datetime.now().isoformat()

        return json.dumps(card, default=str)

    @staticmethod
    def list_branches_apply(
        data: Dict[str, Any],
        branch_id: Optional[int] = None,
        bank_id: Optional[int] = None,
        name: Optional[str] = None,
        address: Optional[str] = None,
        swift_code: Optional[str] = None,
        contact_number: Optional[str] = None
    ) -> str:
        branches = data.get('branches', {})
        results = []

        name_lower = name.lower() if name else None
        address_lower = address.lower() if address else None
        swift_lower = swift_code.lower() if swift_code else None

        for bid, branch in branches.items():
            # Filter by branch_id (exact)
            if branch_id is not None:
                try:
                    if int(bid) != branch_id:
                        continue
                except (ValueError, TypeError):
                    continue

            # Filter by bank_id (exact)
            if bank_id is not None and branch.get('bank_id') != bank_id:
                continue

            # Partial, case-insensitive match on name
            if name_lower and name_lower not in branch.get('name', '').lower():
                continue

            # Partial, case-insensitive match on address
            if address_lower and address_lower not in branch.get('address', '').lower():
                continue

            # Exact, case-insensitive match on SWIFT code
            if swift_lower and branch.get('swift_code', '').lower() != swift_lower:
                continue

            # Exact match on contact number
            if contact_number and branch.get('contact_number') != contact_number:
                continue

            results.append(branch)

        return json.dumps(results)

    @staticmethod
    def add_beneficiary_apply(
        data: Dict[str, Any],
        customer_id: int,
        name: str,
        beneficiary_type: str,
        account_number: str,
        swift_code: Optional[str] = None
    ) -> str:
        customers = data.get('customers', {})
        beneficiaries = data.get('beneficiaries', {})

        # Validate customer_id
        if not isinstance(customer_id, int):
            return "Error: 'customer_id' must be an integer"
        if str(customer_id) not in customers:
            return f"Error: Customer '{customer_id}' not found"

        # Validate name
        if not isinstance(name, str) or not name:
            return "Error: 'name' must be a non-empty string"

        # Validate beneficiary_type
        if not isinstance(beneficiary_type, str):
            return "Error: 'beneficiary_type' must be a string"

        # If bank account, require SWIFT code
        if beneficiary_type == 'BANK_ACCOUNT':
            if not isinstance(swift_code, str) or not swift_code.strip():
                return "Error: 'swift_code' is required when beneficiary_type is 'BANK_ACCOUNT'"

        # Validate account_number
        if not isinstance(account_number, str) or not account_number:
            return "Error: 'account_number' must be a non-empty string"

        # Validate swift_code type if provided
        if swift_code is not None and not isinstance(swift_code, str):
            return "Error: 'swift_code' must be a string"

        # Generate new beneficiary_id
        existing_ids = [int(bid) for bid in beneficiaries.keys() if bid.isdigit()]
        new_id = str(max(existing_ids) + 1) if existing_ids else "1"

        now_str = datetime.now().isoformat()

        beneficiary = {
            "beneficiary_id": int(new_id),
            "customer_id": customer_id,
            "name": name,
            "swift_code": swift_code,
            "beneficiary_type": beneficiary_type,
            "account_number": account_number,
            "added_at": now_str
        }

        beneficiaries[new_id] = beneficiary

        return json.dumps({
            "message": "Beneficiary added successfully",
            "beneficiary": beneficiary
        }, default=str)

    @staticmethod
    def list_account_transactions_apply(
        data: Dict[str, Any],
        transaction_id: Optional[int] = None,
        account_id: Optional[int] = None,
        type: Optional[str] = None,
        channel: Optional[str] = None,
        amount_min: Optional[int] = None,
        amount_max: Optional[int] = None,
        occurred_from: Optional[str] = None,
        occurred_to: Optional[str] = None,
        beneficiary_id: Optional[int] = None,
        card_id: Optional[int] = None,
        merchant: Optional[str] = None,
        card_tx_status: Optional[str] = None
    ) -> str:
        transactions = data.get('transactions', {})
        results = []

        merchant_lower = merchant.lower() if merchant else None

        # Parse occurred_from/to ISO strings into datetimes
        occ_from_dt: Optional[datetime] = None
        occ_to_dt: Optional[datetime] = None
        if occurred_from:
            try:
                occ_from_dt = datetime.fromisoformat(occurred_from)
            except ValueError:
                return "Error: 'occurred_from' must be an ISO datetime string"
        if occurred_to:
            try:
                occ_to_dt = datetime.fromisoformat(occurred_to)
            except ValueError:
                return "Error: 'occurred_to' must be an ISO datetime string"

        def parse_date(t: Dict[str, Any]) -> datetime:
            occ = t.get('occurred_at')
            if isinstance(occ, str):
                try:
                    return datetime.fromisoformat(occ)
                except ValueError:
                    pass
            if isinstance(occ, datetime):
                return occ
            return datetime.min

        for txn in transactions.values():
            if transaction_id is not None and txn.get('transaction_id') != transaction_id:
                continue
            if account_id is not None and txn.get('account_id') != account_id:
                continue
            if type and txn.get('type') != type:
                continue
            if channel and txn.get('channel') != channel:
                continue

            amt = txn.get('amount')
            if amount_min is not None and amt < amount_min:
                continue
            if amount_max is not None and amt > amount_max:
                continue

            occ_dt = parse_date(txn)
            if occ_from_dt and occ_dt < occ_from_dt:
                continue
            if occ_to_dt and occ_dt > occ_to_dt:
                continue

            if beneficiary_id is not None and txn.get('beneficiary_id') != beneficiary_id:
                continue
            if card_id is not None and txn.get('card_id') != card_id:
                continue

            if merchant_lower and merchant_lower not in txn.get('merchant', '').lower():
                continue
            if card_tx_status and txn.get('card_tx_status') != card_tx_status:
                continue

            results.append(txn)

        return json.dumps(results)

    @staticmethod
    def transfer_to_other_bank_account_apply(
        data: Dict[str, Any],
        from_account_id: int,
        beneficiary_id: int,
        amount: int
    ) -> str:
        accounts = data.get('accounts', {})
        beneficiaries = data.get('beneficiaries', {})
        transactions = data.get('transactions', {})

        # Validate from_account_id
        if not isinstance(from_account_id, int):
            return "Error: 'from_account_id' must be an integer"

        # Locate source account
        source_key = None
        for aid in accounts:
            try:
                if int(aid) == from_account_id:
                    source_key = aid
                    break
            except (ValueError, TypeError):
                continue
        if source_key is None:
            return f"Error: Account '{from_account_id}' not found"
        source_account = accounts[source_key]

        # Validate beneficiary_id
        ben = beneficiaries.get(str(beneficiary_id))
        if not ben:
            return f"Error: Beneficiary '{beneficiary_id}' not found"
        if ben.get('beneficiary_type') != 'BANK_ACCOUNT':
            return "Error: Beneficiary is not a bank account"

        # Validate amount
        if not isinstance(amount, int) or amount <= 0:
            return "Error: 'amount' must be a positive integer"

        # Check sufficient funds
        current_balance = source_account.get('balance', 0)
        if amount > current_balance:
            return "Error: Insufficient funds"

        # Deduct from source account balance
        source_account['balance'] = current_balance - amount
        source_account['updated_at'] = datetime.now().isoformat()

        # Generate new transaction_id
        existing_ids = [int(tid) for tid in transactions.keys() if tid.isdigit()]
        new_txn_id = str(max(existing_ids) + 1) if existing_ids else "1"
        now = datetime.now().isoformat()

        # Create transaction record
        txn = {
            "transaction_id": int(new_txn_id),
            "account_id": from_account_id,
            "type": "TRANSFER",
            "channel": "ONLINE",
            "amount": amount,
            "occurred_at": now,
            "beneficiary_id": beneficiary_id,
            "card_id": None,
            "merchant": None,
            "card_tx_status": None,
            "created_at": now
        }
        transactions[new_txn_id] = txn

        return json.dumps({
            "message": "Transfer to other bank account successful",
            "transaction": txn
        }, default=str)

    @staticmethod
    def create_loan_apply(
        data: Dict[str, Any],
        customer_id: int,
        branch_id: int,
        loan_type: str,
        principal_amount: int,
        interest_rate: int,
        tenure_months: int,
        start_date: str
    ) -> str:
        customers = data.get('customers', {})
        branches = data.get('branches', {})
        loans = data.get('loans', {})

        # Validate customer_id
        if not isinstance(customer_id, int):
            return "Error: 'customer_id' must be an integer"
        if str(customer_id) not in customers:
            return f"Error: Customer '{customer_id}' not found"

        # Validate branch_id
        if not isinstance(branch_id, int):
            return "Error: 'branch_id' must be an integer"
        if str(branch_id) not in branches:
            return f"Error: Branch '{branch_id}' not found"

        # Validate loan_type
        if not isinstance(loan_type, str):
            return "Error: 'loan_type' must be a string"

        # Validate principal_amount
        if not isinstance(principal_amount, int) or principal_amount <= 0:
            return "Error: 'principal_amount' must be a positive integer"

        # Validate interest_rate
        if not isinstance(interest_rate, int) or interest_rate < 0:
            return "Error: 'interest_rate' must be a non-negative integer"

        # Validate tenure_months
        if not isinstance(tenure_months, int) or tenure_months <= 0:
            return "Error: 'tenure_months' must be a positive integer"

        # Validate start_date
        try:
            parsed_start = datetime.fromisoformat(start_date).date()
            start_date_str = parsed_start.isoformat()
        except Exception:
            return "Error: 'start_date' must be a string in YYYY-MM-DD format"

        # Generate new loan_id
        existing_ids = [int(lid) for lid in loans.keys() if lid.isdigit()]
        new_id = str(max(existing_ids) + 1) if existing_ids else "1"

        now_str = datetime.now().isoformat()
        loan_account_number = f"LOAN{new_id}"

        loan = {
            "loan_id": int(new_id),
            "customer_id": customer_id,
            "branch_id": branch_id,
            "loan_account_number": loan_account_number,
            "type": loan_type,
            "principal_amount": principal_amount,
            "interest_rate": interest_rate,
            "tenure": tenure_months,
            "start_date": start_date_str,
            "end_date": None,
            "status": "ACTIVE",
            "created_at": now_str
        }

        loans[new_id] = loan

        return json.dumps({
            "message": "Loan created successfully",
            "loan": loan
        }, default=str)

    @staticmethod
    def create_customer_apply(
        data: Dict[str, Any],
        first_name: str,
        last_name: str,
        dob: str,
        email: str,
        phone: str,
        address: str
    ) -> str:
        customers = data.get('customers', {})

        # Validate and normalize date of birth (string input)
        try:
            parsed_dob = datetime.fromisoformat(dob).date()
            dob_str = parsed_dob.isoformat()
        except Exception:
            return "Error: 'dob' must be a string in YYYY-MM-DD format"

        # Generate new customer ID
        existing_ids = [int(cid) for cid in customers.keys() if cid.isdigit()]
        new_id = str(max(existing_ids) + 1) if existing_ids else "1"

        now_str = datetime.now().isoformat()

        # Create customer record
        customer = {
            "customer_id": int(new_id),
            "first_name": first_name,
            "last_name": last_name,
            "dob": dob_str,
            "email": email,
            "phone": phone,
            "address": address,
            "status": "ACTIVE",
            "created_at": now_str,
            "updated_at": now_str
        }

        customers[new_id] = customer

        return json.dumps({
            "message": "Customer created successfully",
            "customer": customer
        }, default=str)

    @staticmethod
    def list_loan_statements_apply(
        data: Dict[str, Any],
        loan_id: Optional[int] = None,
        period_start_from: Optional[str] = None,
        period_end_to: Optional[str] = None,
        status: Optional[str] = None,
        scheduled_min: Optional[int] = None,
        scheduled_max: Optional[int] = None
    ) -> str:
        statements = data.get('loan_statements', {})
        results = []

        def parse_date_str(d: Optional[str]) -> Optional[datetime.date]:
            if not d:
                return None
            try:
                return datetime.fromisoformat(d).date()
            except Exception:
                return None

        ps_filter = parse_date_str(period_start_from)
        pe_filter = parse_date_str(period_end_to)

        for sid, stmt in statements.items():
            # Filter by loan_id (exact)
            if loan_id is not None and stmt.get('loan_id') != loan_id:
                continue

            # Filter by period_start_from (inclusive)
            ps = parse_date_str(stmt.get('period_start'))
            if ps_filter and (ps is None or ps < ps_filter):
                continue

            # Filter by period_end_to (inclusive)
            pe = parse_date_str(stmt.get('period_end'))
            if pe_filter and (pe is None or pe > pe_filter):
                continue

            # Filter by status (exact, case-insensitive)
            if status and stmt.get('status', '').lower() != status.lower():
                continue

            # Filter by scheduled amount range
            sched_amt = stmt.get('scheduled_amount', 0)
            if scheduled_min is not None and sched_amt < scheduled_min:
                continue
            if scheduled_max is not None and sched_amt > scheduled_max:
                continue

            results.append(stmt)

        return json.dumps(results)

    @staticmethod
    def update_loan_status_apply(
        data: Dict[str, Any],
        loan_id: int,
        status: str
    ) -> str:
        loans = data.get('loans', {})

        # Validate loan_id
        if not isinstance(loan_id, int):
            return "Error: 'loan_id' must be an integer"

        # Locate loan
        loan_key = None
        for lid in loans:
            try:
                if int(lid) == loan_id:
                    loan_key = lid
                    break
            except (ValueError, TypeError):
                continue
        if loan_key is None:
            return f"Error: Loan '{loan_id}' not found"

        # Validate status
        if not isinstance(status, str):
            return "Error: 'status' must be a string"
        valid_statuses = {"ACTIVE", "CLOSED", "DEFAULTED"}
        if status not in valid_statuses:
            return f"Error: 'status' must be one of: {', '.join(valid_statuses)}"

        # Update loan status
        loan = loans[loan_key]
        loan['status'] = status

        # Optionally set end_date when closing
        if status == "CLOSED":
            loan['end_date'] = datetime.now().date().isoformat()

        return json.dumps(loan, default=str)

    @staticmethod
    def deposit_to_account_apply(
        data: Dict[str, Any],
        account_id: int,
        amount: int,
        channel: str
    ) -> str:
        accounts = data.get('accounts', {})
        transactions = data.get('transactions', {})

        # Validate account_id
        if not isinstance(account_id, int):
            return "Error: 'account_id' must be an integer"

        # Locate account
        acct_key = None
        for aid in accounts:
            try:
                if int(aid) == account_id:
                    acct_key = aid
                    break
            except (ValueError, TypeError):
                continue
        if acct_key is None:
            return f"Error: Account '{account_id}' not found"

        # Validate amount
        if not isinstance(amount, int):
            return "Error: 'amount' must be an integer"

        # Validate channel
        if not isinstance(channel, str):
            return "Error: 'channel' must be a string"

        # Update account balance
        account = accounts[acct_key]
        new_balance = account.get('balance', 0) + amount
        account['balance'] = new_balance
        account['updated_at'] = datetime.now().isoformat()

        # Generate new transaction_id
        existing_ids = [int(tid) for tid in transactions.keys() if tid.isdigit()]
        new_txn_id = str(max(existing_ids) + 1) if existing_ids else "1"

        now = datetime.now().isoformat()

        # Create transaction record
        txn = {
            "transaction_id": int(new_txn_id),
            "account_id": account_id,
            "type": "DEPOSIT",
            "channel": channel,
            "amount": amount,
            "occurred_at": now,
            "beneficiary_id": None,
            "card_id": None,
            "merchant": None,
            "card_tx_status": None,
            "created_at": now
        }
        transactions[new_txn_id] = txn

        return json.dumps({
            "message": "Deposit successful",
            "transaction": txn
        }, default=str)

    @staticmethod
    def generate_loan_statement_apply(
        data: Dict[str, Any],
        loan_id: int
    ) -> str:
        loans = data.get('loans', {})
        statements = data.get('loan_statements', {})
        transactions = data.get('transactions', {})
        penalty_rates = data.get('penalty_rates', {})

        # Validate loan_id
        if not isinstance(loan_id, int):
            return "Error: 'loan_id' must be an integer"
        loan = next((ln for lid, ln in loans.items()
                     if str(ln.get('loan_id')) == str(loan_id)), None)
        if loan is None:
            return f"Error: Loan '{loan_id}' not found"

        # Determine period_start and period_end
        # Find latest statement for this loan
        loan_statements = [s for s in statements.values() if s.get('loan_id') == loan_id]
        if loan_statements:
            # latest period_end
            prev_end = max(
                datetime.fromisoformat(s['period_end']).date()
                for s in loan_statements
            )
        else:
            # first period starts at loan start_date
            try:
                prev_end = datetime.fromisoformat(loan.get('start_date')).date() - timedelta(days=1)
            except Exception:
                return "Error: loan.start_date invalid"

        period_start = prev_end + timedelta(days=1)
        period_end = period_start + timedelta(days=29)  # 30-day period
        due_date = period_end + timedelta(days=10)

        # Calculate scheduled amount
        P = loan.get('principal_amount', 0)
        annual_rate = loan.get('interest_rate', 0)
        n = loan.get('tenure', 1)
        r = annual_rate / 100 / 12
        if r > 0:
            sched = P * r * (1 + r)**n / ((1 + r)**n - 1)
        else:
            sched = P / n
        sched = round(sched, 2)

        # Prepare new statement
        existing_ids = [int(sid) for sid in statements.keys() if sid.isdigit()]
        new_sid = str(max(existing_ids) + 1) if existing_ids else "1"
        now = datetime.now().isoformat()

        stmt = {
            "statement_id": int(new_sid),
            "loan_id": loan_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "due_date": due_date.isoformat(),
            "scheduled_amount": sched,
            "late_fee_amount": 0.00,
            "penalty_rate_id": None,
            "status": "PENDING",
            "created_at": now
        }

        # Check for transactions in period before due_date
        paid = any(
            t for t in transactions.values()
            if t.get('loan_id') == loan_id and
               period_start <= datetime.fromisoformat(t.get('occurred_at')).date() <= due_date
        )

        today = datetime.now().date()
        if due_date < today and not paid:
            # calculate days overdue
            days_overdue = (today - due_date).days
            # find penalty rate
            pr = next((pr for pr in penalty_rates.values()
                       if pr.get('product_type') == 'LOAN'
                       and pr.get('product_subtype') == loan.get('type')
                       and days_overdue >= pr.get('days_overdue_from', 0)
                       and (pr.get('days_overdue_to') is None or days_overdue <= pr.get('days_overdue_to'))),
                      None)
            if pr:
                stmt['late_fee_amount'] = round(sched * pr['rate'] / 100, 2)
                stmt['penalty_rate_id'] = pr['penalty_rate_id']

        statements[new_sid] = stmt

        return json.dumps({
            "message": "Loan statement generated",
            "statement": stmt
        }, default=str)

    @staticmethod
    def update_account_apply(
        data: Dict[str, Any],
        account_id: int,
        branch_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        account_type: Optional[str] = None,
        balance: Optional[int] = None,
        opened_date: Optional[str] = None,
        status: Optional[str] = None
    ) -> str:
        accounts = data.get('accounts', {})

        # Validate account_id
        try:
            aid = int(account_id)
        except (ValueError, TypeError):
            return "Error: 'account_id' must be an integer"

        # Locate the account
        account_key = None
        for key in accounts:
            try:
                if int(key) == aid:
                    account_key = key
                    break
            except:
                continue
        if account_key is None:
            return f"Error: Account '{aid}' not found"

        account = accounts[account_key]

        # Apply updates
        if branch_id is not None:
            if not isinstance(branch_id, int):
                return "Error: 'branch_id' must be an integer"
            account['branch_id'] = branch_id

        if customer_id is not None:
            if not isinstance(customer_id, int):
                return "Error: 'customer_id' must be an integer"
            account['customer_id'] = customer_id

        if account_type is not None:
            if not isinstance(account_type, str):
                return "Error: 'account_type' must be a string"
            account['type'] = account_type

        if balance is not None:
            if not isinstance(balance, int):
                return "Error: 'balance' must be an integer"
            account['balance'] = balance

        if opened_date is not None:
            try:
                dt = datetime.fromisoformat(opened_date).date()
                account['opened_date'] = dt.isoformat()
            except Exception:
                return "Error: 'opened_date' must be a string in YYYY-MM-DD format"

        if status is not None:
            if not isinstance(status, str):
                return "Error: 'status' must be a string"
            account['status'] = status

        # Update timestamp
        account['updated_at'] = datetime.now().isoformat()

        return json.dumps(account, default=str)

    @staticmethod
    def list_customers_apply(
        data: Dict[str, Any],
        customer_id: Optional[int] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        status: Optional[str] = None
    ) -> str:
        customers = data.get('customers', {})
        results = []

        # prepare lowercase filters for partial match on names
        first_lower = first_name.lower() if first_name else None
        last_lower = last_name.lower() if last_name else None
        email_lower = email.lower() if email else None

        for cid, cust in customers.items():
            # Filter by customer_id (exact)
            if customer_id is not None:
                try:
                    if int(cid) != customer_id:
                        continue
                except (ValueError, TypeError):
                    continue

            # Partial, case-insensitive match on first_name
            if first_lower and first_lower not in cust.get('first_name', '').lower():
                continue

            # Partial, case-insensitive match on last_name
            if last_lower and last_lower not in cust.get('last_name', '').lower():
                continue

            # Exact, case-insensitive match on email
            if email_lower and cust.get('email', '').lower() != email_lower:
                continue

            # Exact match on phone
            if phone and cust.get('phone') != phone:
                continue

            # Exact match on status
            if status and cust.get('status') != status:
                continue

            results.append(cust)

        return json.dumps(results)

    @staticmethod
    def withdraw_from_account_apply(
        data: Dict[str, Any],
        account_id: int,
        amount: int,
        channel: str
    ) -> str:
        accounts = data.get('accounts', {})
        transactions = data.get('transactions', {})
        print("Account ID:", type(account_id))
        print("Amount:", amount)
        print("Channel:", channel)

        # Validate account_id
        if not isinstance(account_id, int):
            return "Error: 'account_id' must be an integer"

        # Locate account
        acct_key = None
        for aid in accounts:
            try:
                if int(aid) == account_id:
                    acct_key = aid
                    break
            except (ValueError, TypeError):
                continue
        if acct_key is None:
            return f"Error: Account '{account_id}' not found"

        # Validate amount
        if not isinstance(amount, int) or amount <= 0:
            return "Error: 'amount' must be a positive integer"

        # Validate channel
        if not isinstance(channel, str):
            return "Error: 'channel' must be a string"

        # Check sufficient funds
        account = accounts[acct_key]
        current_balance = account.get('balance', 0)
        if amount > current_balance:
            return "Error: Insufficient funds"

        # Update account balance
        new_balance = current_balance - amount
        account['balance'] = new_balance
        account['updated_at'] = datetime.now().isoformat()

        # Generate new transaction_id
        existing_ids = [int(tid) for tid in transactions.keys() if tid.isdigit()]
        new_txn_id = str(max(existing_ids) + 1) if existing_ids else "1"

        now = datetime.now().isoformat()

        # Create transaction record
        txn = {
            "transaction_id": int(new_txn_id),
            "account_id": account_id,
            "type": "WITHDRAWAL",
            "channel": channel,
            "amount": amount,
            "occurred_at": now,
            "beneficiary_id": None,
            "card_id": None,
            "merchant": None,
            "card_tx_status": None,
            "created_at": now
        }
        transactions[new_txn_id] = txn

        return json.dumps({
            "message": "Withdrawal successful",
            "transaction": txn
        }, default=str)

    @staticmethod
    def create_account_apply(
        data: Dict[str, Any],
        branch_id: int,
        customer_id: int,
        account_type: str,
        initial_deposit: int
    ) -> str:
        accounts = data.get('accounts', {})

        # Validate inputs
        if not isinstance(branch_id, int):
            return "Error: 'branch_id' must be an integer"
        if not isinstance(customer_id, int):
            return "Error: 'customer_id' must be an integer"
        if not isinstance(account_type, str):
            return "Error: 'account_type' must be a string"
        if not isinstance(initial_deposit, int):
            return "Error: 'initial_deposit' must be an integer"

        # Generate new account_id
        existing_ids = [int(aid) for aid in accounts.keys() if aid.isdigit()]
        new_id = str(max(existing_ids) + 1) if existing_ids else "1"

        now = datetime.now()
        opened_date = now.date().isoformat()
        now_str = now.isoformat()

        # Generate account_number
        account_number = f"ACCT{new_id}"

        account = {
            "account_id": int(new_id),
            "branch_id": branch_id,
            "customer_id": customer_id,
            "account_number": account_number,
            "type": account_type,
            "balance": float(initial_deposit),
            "opened_date": opened_date,
            "status": "OPEN",
            "created_at": now_str,
            "updated_at": now_str
        }

        accounts[new_id] = account

        return json.dumps({
            "message": "Account created successfully",
            "account": account
        }, default=str)

    @staticmethod
    def list_penalty_rates_apply(
        data: Dict[str, Any],
        product_type: Optional[str] = None,
        product_subtype: Optional[str] = None,
        overdue_days: Optional[int] = None
    ) -> str:
        penalty_rates = data.get('penalty_rates', {})
        results = []

        for pr_id, rate in penalty_rates.items():
            # Filter by product_type (exact)
            if product_type and rate.get('product_type') != product_type:
                continue

            # Filter by product_subtype (exact)
            if product_subtype and rate.get('product_subtype') != product_subtype:
                continue

            # If overdue_days provided, it must fall within the rate's range
            if overdue_days is not None:
                from_days = rate.get('days_overdue_from', 0)
                to_days = rate.get('days_overdue_to')
                if overdue_days < from_days:
                    continue
                if to_days is not None and overdue_days > to_days:
                    continue

            results.append(rate)

        return json.dumps(results)

    @staticmethod
    def list_customer_loans_apply(
        data: Dict[str, Any],
        loan_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        loan_type: Optional[str] = None,
        status: Optional[str] = None,
        principal_min: Optional[int] = None,
        principal_max: Optional[int] = None,
        interest_min: Optional[int] = None,
        interest_max: Optional[int] = None
    ) -> str:
        loans = data.get('loans', {})
        results = []

        for lid, ln in loans.items():
            # Filter by loan_id (exact)
            if loan_id is not None:
                try:
                    if int(lid) != loan_id:
                        continue
                except (ValueError, TypeError):
                    continue

            # Filter by customer_id (exact)
            if customer_id is not None and ln.get('customer_id') != customer_id:
                continue

            # Filter by branch_id (exact)
            if branch_id is not None and ln.get('branch_id') != branch_id:
                continue

            # Filter by loan_type (exact, case-insensitive)
            if loan_type and ln.get('type', '').lower() != loan_type.lower():
                continue

            # Filter by status (exact, case-insensitive)
            if status and ln.get('status', '').lower() != status.lower():
                continue

            # Filter by principal range
            principal = ln.get('principal_amount', 0)
            if principal_min is not None and principal < principal_min:
                continue
            if principal_max is not None and principal > principal_max:
                continue

            # Filter by interest rate range
            interest = ln.get('interest_rate', 0)
            if interest_min is not None and interest < interest_min:
                continue
            if interest_max is not None and interest > interest_max:
                continue

            results.append(ln)

        return json.dumps(results)

    @staticmethod
    def list_employees_apply(
        data: Dict[str, Any],
        employee_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        status: Optional[str] = None
    ) -> str:
        employees = data.get('employees', {})
        results = []

        # prepare lowercase filters for partial match on names
        first_lower = first_name.lower() if first_name else None
        last_lower = last_name.lower() if last_name else None
        email_lower = email.lower() if email else None

        for eid, emp in employees.items():
            # Filter by employee_id (exact)
            if employee_id is not None:
                try:
                    if int(eid) != employee_id:
                        continue
                except (ValueError, TypeError):
                    continue

            # Filter by branch_id (exact)
            if branch_id is not None and emp.get('branch_id') != branch_id:
                continue

            # Partial, case-insensitive match on first_name
            if first_lower and first_lower not in emp.get('first_name', '').lower():
                continue

            # Partial, case-insensitive match on last_name
            if last_lower and last_lower not in emp.get('last_name', '').lower():
                continue

            # Exact match on role
            if role and emp.get('role') != role:
                continue

            # Exact, case-insensitive match on email
            if email_lower and emp.get('email', '').lower() != email_lower:
                continue

            # Exact match on phone
            if phone and emp.get('phone') != phone:
                continue

            # Exact match on status
            if status and emp.get('status') != status:
                continue

            results.append(emp)

        return json.dumps(results)

    @staticmethod
    def list_beneficiaries_apply(
        data: Dict[str, Any],
        customer_id: Optional[int] = None,
        name: Optional[str] = None,
        swift_code: Optional[str] = None,
        beneficiary_type: Optional[str] = None,
        account_number: Optional[str] = None
    ) -> str:
        beneficiaries = data.get('beneficiaries', {})
        results = []

        # prepare lowercase filter for partial match on name
        name_lower = name.lower() if name else None
        swift_lower = swift_code.lower() if swift_code else None

        for bid, ben in beneficiaries.items():
            # Filter by customer_id (exact)
            if customer_id is not None and ben.get('customer_id') != customer_id:
                continue

            # Partial, case-insensitive match on name
            if name_lower and name_lower not in ben.get('name', '').lower():
                continue

            # Exact, case-insensitive match on SWIFT code
            if swift_lower and ben.get('swift_code', '').lower() != swift_lower:
                continue

            # Exact match on beneficiary_type
            if beneficiary_type and ben.get('beneficiary_type') != beneficiary_type:
                continue

            # Exact match on account_number
            if account_number and ben.get('account_number') != account_number:
                continue

            results.append(ben)

        return json.dumps(results)

