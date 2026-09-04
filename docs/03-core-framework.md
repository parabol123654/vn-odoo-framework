
# Part 3 — Core Framework Design

> **Sửa đổi bởi Part 17 §8.1.** Cây 16 thư mục con ở §2 dưới đây chưa tạo.
> `vn_core` hiện có `core/`, `dto/`, `domain/`, `infrastructure/`,
> `services/`, `models/`, `tests/`. `enums` và `exceptions` là **file** trong
> `core/`, chưa phải package — tạo sẵn package rỗng chỉ làm cây thư mục trông
> có kiến trúc mà không có nội dung.


---

# 1. Overview

`vn_core` là nền tảng của toàn bộ Vietnam ERP Framework.

Mọi Business Module đều phải phụ thuộc vào `vn_core`.

Các module như:

* vn_account
* vn_inventory
* vn_tax
* vn_reports
* vn_costing

không được tự xây dựng Service, Repository hoặc Engine riêng nếu chức năng đó đã tồn tại trong `vn_core`.

Mục tiêu của `vn_core` là:

* Tái sử dụng
* Chuẩn hóa
* Dễ kiểm thử
* Dễ nâng cấp
* Giảm lặp code

---

# 2. Directory Structure

```text
vn_core/

├── engines/
├── repositories/
├── services/
├── dto/
├── calculators/
├── mappers/
├── rules/
├── validators/
├── exceptions/
├── enums/
├── constants/
├── helpers/
├── mixins/
├── cache/
├── utils/
└── tests/
```

Mỗi package chỉ có một trách nhiệm.

---

# 3. Core Components

Framework gồm 8 thành phần chính.

| Component  | Responsibility      |
| ---------- | ------------------- |
| Engine     | Business Logic      |
| Repository | Data Access         |
| Service    | Use Case            |
| DTO        | Data Transport      |
| Calculator | Business Formula    |
| Rule       | Business Rule       |
| Validator  | Input Validation    |
| Mapper     | Data Transformation |

---

# 4. Engine

## Purpose

Engine là nơi chứa toàn bộ Business Logic.

Engine:

* Không biết UI
* Không biết Report
* Không biết QWeb
* Không biết Excel
* Không biết HTTP

Engine chỉ biết:

Input

↓

Business Logic

↓

Output

---

## Responsibilities

Ví dụ Ledger Engine.

```text
Opening Balance

Running Balance

Closing Balance

Counterpart Detection

Balance Aggregation
```

Inventory Engine.

```text
Opening Stock

Incoming

Outgoing

Ending

Inventory Value
```

Tax Engine.

```text
VAT Base

VAT Amount

VAT Summary
```

---

## Engine Rules

Engine được phép:

* Gọi Calculator
* Gọi Rule
* Gọi Repository Interface

Engine không được:

* Query ORM
* Render Report
* Return Recordset

---

# 5. Repository

## Purpose

Repository chịu trách nhiệm truy cập dữ liệu.

Repository là lớp duy nhất được phép sử dụng ORM.

---

## Responsibilities

Ví dụ:

```python
LedgerRepository

InventoryRepository

TaxRepository
```

Repository có thể:

* search
* read
* read_group
* execute SQL
* aggregate

Repository không được:

* Tính Opening Balance
* Tính VAT
* Tính Cost

---

## Repository Interface

Ví dụ.

```python
class LedgerRepository:

    def get_move_lines(...):

        pass

    def get_opening_balance(...):

        pass

    def get_accounts(...):

        pass
```

Repository chỉ trả dữ liệu.

---

# 6. Service

## Purpose

Service đại diện cho một Use Case.

Ví dụ.

```text
Generate General Ledger

Generate Trial Balance

Generate Balance Sheet

Generate Stock Card
```

Service sẽ:

* Validate Input
* Gọi Repository
* Gọi Engine
* Trả DTO

Service không chứa thuật toán.

---

# 7. DTO

## Purpose

DTO (Data Transfer Object) dùng để truyền dữ liệu giữa các Layer.

Không trả trực tiếp ORM Recordset.

Ví dụ.

```python
GeneralLedgerDTO

Opening Balance

Lines

Closing Balance
```

Inventory.

```python
StockCardDTO

Opening Qty

Incoming

Outgoing

Ending Qty
```

DTO phải:

* Immutable (nếu có thể)
* Serializable
* Không chứa Business Logic

---

# 8. Calculator

Calculator thực hiện các phép tính độc lập.

Ví dụ.

```text
OpeningBalanceCalculator

RunningBalanceCalculator

VATCalculator

AverageCostCalculator

FIFOCalculator
```

Calculator không truy cập database.

Calculator chỉ nhận dữ liệu.

---

# 9. Rule

Rule mô tả quy tắc nghiệp vụ.

Ví dụ.

```text
CanPostJournalRule

CanClosePeriodRule

VATValidationRule

InventoryValidationRule
```

Rule trả về:

```python
True

False

Exception
```

Rule không query database.

---

# 10. Validator

Validator dùng để kiểm tra Input.

Ví dụ.

```text
DateRangeValidator

CompanyValidator

AccountValidator

WarehouseValidator
```

Validator không tính toán.

Validator chỉ kiểm tra.

---

# 11. Mapper

Mapper chuyển đổi dữ liệu.

Ví dụ.

```text
ORM Record

↓

DTO
```

Hoặc.

```text
Account

↓

Balance Sheet Item
```

Mapper không chứa Business Logic.

---

# 12. Exception

Mọi Exception phải kế thừa.

```python
VNFrameworkException
```

Ví dụ.

```text
ValidationException

RepositoryException

BusinessException

ReportException
```

Không throw Exception trực tiếp từ ORM.

---

# 13. Helper

Helper chứa các hàm dùng chung.

Ví dụ.

```text
Date Helper

Currency Helper

Excel Helper

Number Helper
```

Helper không được chứa Business Logic.

---

# 14. Cache

Các Report lớn có thể cache.

Ví dụ.

```text
Trial Balance

Balance Sheet

Inventory Valuation
```

Cache chỉ áp dụng cho dữ liệu đã tính toán.

Không cache ORM Record.

---

# 15. Mixins

Mixins chỉ chứa hành vi dùng chung.

Ví dụ.

```text
LoggingMixin

ExportMixin

CompanyMixin

DateRangeMixin
```

Không chứa Business Logic.

---

# 16. Result Object

Mọi Service nên trả về Result Object.

Ví dụ.

```python
Result

success

data

message

errors
```

Không trả tuple.

Không trả dictionary không có cấu trúc.

---

# 17. Dependency Graph

```text
Presentation

↓

Application Service

↓

Engine

↓

Calculator

↓

Repository Interface

↓

Repository

↓

ORM

↓

PostgreSQL
```

Calculator không biết Repository.

Repository không biết Engine.

Engine không biết Report.

---

# 18. Naming Convention

Engine.

```text
LedgerEngine

InventoryEngine
```

Repository.

```text
LedgerRepository

TaxRepository
```

Service.

```text
GeneralLedgerService

TrialBalanceService
```

DTO.

```text
GeneralLedgerDTO

TrialBalanceDTO
```

Calculator.

```text
RunningBalanceCalculator
```

Rule.

```text
PeriodCloseRule
```

Validator.

```text
DateRangeValidator
```

---

# 19. Package Dependency

```text
Presentation

↓

Services

↓

Engines

↓

Calculators

↓

Repository Interface

↓

Repository

↓

ORM
```

Không có Dependency ngược.

---

# 20. Summary

`vn_core` là trái tim của toàn bộ Framework.

Mọi Business Logic phải được đặt trong:

* Engine
* Calculator
* Rule

Mọi Data Access phải nằm trong Repository.

Mọi Use Case phải đi qua Service.

Mọi dữ liệu trao đổi giữa các Layer phải sử dụng DTO.

Kiến trúc này đảm bảo:

* Không lặp code.
* Dễ Unit Test.
* Dễ mở rộng.
* Dễ tối ưu hiệu năng.
* Dễ nâng cấp giữa các phiên bản Odoo.
