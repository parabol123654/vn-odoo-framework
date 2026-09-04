

# Part 4 — Ledger Domain Design

> **Sửa đổi bởi Part 17 §8.2.** `aggregators/` ở §13 dưới đây không tạo:
> bốn lớp aggregator sẽ giống hệt nhau và chỉ khác một tên trường, nên thay
> bằng enum `GroupBy`. `validators/`, `rules/`, `mappers/` cũng chưa tạo.
> Tên `LedgerRepository` ở §8 nay là `ILedgerRepository` (interface) và
> `OdooLedgerRepository` (hiện thực), đúng theo Part 6 §6–7.


---

# 1. Overview

Ledger Domain là Domain quan trọng nhất của toàn bộ Vietnam ERP Framework.

Mọi báo cáo kế toán VAS đều phải lấy dữ liệu từ Ledger Domain.

Ví dụ:

* General Journal
* General Ledger
* Account Ledger
* Trial Balance
* Balance Sheet
* Income Statement
* Cash Book
* Bank Book
* Partner Ledger
* Customer Aging
* Vendor Aging
* VAT Reports (một phần)

Ledger Domain chịu trách nhiệm:

* Chuẩn hóa dữ liệu kế toán
* Tính số dư đầu kỳ
* Tính phát sinh
* Tính số dư cuối kỳ
* Xác định tài khoản đối ứng
* Tổng hợp số liệu theo nhiều chiều

Ledger Domain **không render báo cáo**, **không truy cập ORM trực tiếp**, **không phụ thuộc QWeb/XLSX**.

---

# 2. Design Goals

Ledger Domain phải đáp ứng các yêu cầu sau:

* Chỉ có một thuật toán tính Opening Balance.
* Chỉ có một thuật toán Running Balance.
* Có thể tái sử dụng cho mọi báo cáo.
* Không phụ thuộc UI.
* Không phụ thuộc loại Report.
* Hỗ trợ dữ liệu lớn (1M+ account.move.line).
* Có thể Unit Test độc lập.

---

# 3. Package Structure

```text
vn_core/

domain/

ledger/

├── engine.py
├── repository.py              # Repository Interface
├── dto.py
├── filters.py
├── calculators/
│   ├── opening_balance.py
│   ├── running_balance.py
│   ├── closing_balance.py
│   └── counterpart.py
│
├── aggregators/
│   ├── account.py
│   ├── partner.py
│   ├── journal.py
│   └── analytic.py
│
├── mappers/
│
├── validators/
│
├── rules/
│
└── tests/
```

---

# 4. Responsibilities

Ledger Domain chỉ chịu trách nhiệm về dữ liệu kế toán.

Không xử lý:

* PDF
* XLSX
* HTML
* Wizard
* HTTP
* View

---

# 5. Input Model

Tất cả báo cáo phải sử dụng chung một Filter.

```python
LedgerFilter
```

```text
company_id

date_from

date_to

target_move

journal_ids

account_ids

partner_ids

analytic_account_ids

analytic_tag_ids

currency_id

posted_only

include_opening

include_closing
```

Không truyền nhiều tham số rời rạc.

Luôn truyền một DTO.

---

# 6. Output Model

Ledger Engine luôn trả về:

```python
LedgerResult
```

```text
Opening

Movements

Summary

Closing
```

Không trả ORM Recordset.

Không trả Dictionary tự do.

---

# 7. Ledger Engine

```python
LedgerEngine
```

Responsibilities

* Điều phối toàn bộ tính toán.
* Gọi Calculator.
* Gọi Aggregator.
* Trả DTO.

Không query database.

---

# 8. Repository Interface

Ledger Engine chỉ biết Interface.

```python
class LedgerRepository:

    def get_opening_lines()

    def get_move_lines()

    def get_accounts()

    def get_partners()
```

Không biết Odoo ORM.

Không biết SQL.

---

# 9. Opening Balance Calculator

Responsibilities

* Tính số dư trước ngày bắt đầu.
* Hỗ trợ Debit/Credit.
* Hỗ trợ Multi Company.
* Hỗ trợ nhiều Account.

Input

```text
Move Lines
```

Output

```text
Opening Debit

Opening Credit

Opening Balance
```

Mọi báo cáo đều dùng chung Calculator này.

---

# 10. Running Balance Calculator

Input

```text
Opening Balance

Move Lines
```

Output

```text
Line 1 Balance

Line 2 Balance

...

Line N Balance
```

Thuật toán:

```text
Balance(n)

=

Balance(n-1)

+

Debit

-

Credit
```

Không được viết lại ở bất kỳ Report nào.

---

# 11. Closing Balance Calculator

Formula

```text
Closing

=

Opening

+

Debit

-

Credit
```

Không phụ thuộc Report.

---

# 12. Counterpart Calculator

Một trong những phần khó nhất.

Input

```text
Journal Entry
```

Output

```text
Counterpart Accounts
```

Ví dụ.

Journal Entry

```text
111

511

33311
```

Counterpart của dòng 111

↓

```text
511

33311
```

Counterpart của 511

↓

```text
111
```

Calculator này dùng chung cho:

* General Ledger
* Cash Book
* Bank Book
* Partner Ledger

---

# 13. Aggregators

Aggregator chịu trách nhiệm Group dữ liệu.

Ví dụ.

## Account Aggregator

Group theo

```text
account_id
```

## Partner Aggregator

Group theo

```text
partner_id
```

## Journal Aggregator

Group theo

```text
journal_id
```

## Analytic Aggregator

Group theo

```text
analytic_account_id
```

Engine không tự Group.

---

# 14. Ledger DTO

```python
LedgerDTO
```

```text
opening

lines

closing

total_debit

total_credit

ending_balance
```

Mỗi Line.

```python
LedgerLineDTO
```

```text
date

move_name

journal

account

partner

label

debit

credit

balance

counterpart
```

---

# 15. Service Flow

```text
User

↓

Wizard

↓

GeneralLedgerService

↓

LedgerRepository

↓

LedgerEngine

↓

LedgerDTO

↓

Report Renderer
```

Service không tính toán.

---

# 16. Supported Report Types

Ledger Domain hỗ trợ.

General Journal

```text
Group

↓

Journal
```

General Ledger

```text
Group

↓

Account
```

Partner Ledger

```text
Group

↓

Partner
```

Cash Book

```text
Filter

↓

111
```

Bank Book

```text
Filter

↓

112
```

Trial Balance

```text
Aggregate

↓

Account
```

Balance Sheet

```text
Aggregate

↓

Mapping
```

Income Statement

```text
Aggregate

↓

Mapping
```

Engine giống nhau.

Chỉ khác Aggregator và Mapping.

---

# 17. Performance Strategy

Không đọc toàn bộ account.move.line.

Repository phải:

* Filter trước.
* Chỉ lấy Field cần thiết.
* Dùng read_group khi phù hợp.
* Dùng SQL Aggregate khi cần.

Engine không quan tâm dữ liệu lấy bằng ORM hay SQL.

---

# 18. Extension Points

Có thể mở rộng.

Ví dụ.

```python
LedgerEngine
```

↓

Custom

```python
VietnamLedgerEngine
```

Hoặc.

Thêm.

```text
Foreign Currency Calculator

Consolidation Calculator

Cash Flow Calculator
```

Không sửa Engine hiện tại.

---

# 19. Unit Testing

Các Calculator phải test độc lập.

Ví dụ.

Opening Balance.

Cases.

* Debit only
* Credit only
* Mixed
* Zero balance
* Previous fiscal year
* Multi Company
* Closed Period
* Draft Entries

Running Balance.

Cases.

* Positive
* Negative
* Zero
* Large Dataset

Counterpart.

Cases.

* 2 lines
* 3 lines
* VAT Entry
* Foreign Currency Entry

---

# 20. Future Enhancements

Ledger Domain được thiết kế để hỗ trợ thêm:

* Multi Currency Ledger
* Consolidated Ledger
* Branch Accounting
* Segment Reporting
* Cost Center Reporting
* IFRS Mapping
* VAS Mapping

Các tính năng mới sẽ được bổ sung bằng Calculator hoặc Aggregator mới, không thay đổi Engine.

---

# Summary

Ledger Domain là nền tảng của toàn bộ hệ thống kế toán.

Mọi báo cáo VAS phải sử dụng cùng:

* LedgerFilter
* LedgerRepository
* LedgerEngine
* Calculators
* Aggregators
* LedgerDTO

Nhờ đó:

* Chỉ tồn tại một cách tính số dư.
* Mọi báo cáo luôn nhất quán.
* Business Logic không bị lặp.
* Dễ kiểm thử.
* Dễ tối ưu hiệu năng.
* Dễ mở rộng cho các phiên bản Odoo trong tương lai.
