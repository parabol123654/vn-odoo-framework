# Part 2 — Layered Architecture & Package Structure

> **Sửa đổi bởi Part 16 và Part 17 §8.1.** Cấu trúc `shared/` nằm ngoài
> `addons/` ở §2 dưới đây **không dùng** — Odoo chỉ nạp thứ nằm trong
> `addons_path`; Part 16 chốt layout thay thế. Các package `commands/`,
> `queries/`, `orm/`, `sql/`, `cache/`, `queue/` cũng chưa tạo, có chủ ý.


---

# 1. Objectives

Phần này định nghĩa kiến trúc source code của toàn bộ Framework.

Mục tiêu:

* Phân tách rõ trách nhiệm của từng layer.
* Tránh phụ thuộc chéo (Circular Dependency).
* Giúp dễ Unit Test.
* Dễ nâng cấp Odoo.
* Dễ thay đổi datasource.
* Có thể tái sử dụng Business Logic.

Mọi module trong Framework phải tuân theo tài liệu này.

---

# 2. Overall Package Structure

```text
odoo-vn-framework/

├── docs/
│
├── shared/
│   ├── core/
│   ├── application/
│   ├── domain/
│   └── infrastructure/
│
├── addons/
│   ├── l10n_vn/
│   ├── l10n_vn_reports/
│   ├── l10n_vn_tax/
│   ├── l10n_vn_inventory/
│   ├── l10n_vn_costing/
│   ├── l10n_vn_assets/
│   ├── l10n_vn_bank/
│   └── l10n_vn_einvoice/
│
└── tests/
```

Framework được chia thành hai phần:

* **shared/** → Business Framework
* **addons/** → Odoo Modules

Business Framework không phụ thuộc vào module cụ thể.

---

# 3. Architecture Layers

Framework gồm bốn tầng.

```text
Presentation
        │
Application
        │
Domain
        │
Infrastructure
```

Dependency chỉ đi từ trên xuống dưới.

---

# 4. Layer Responsibilities

## 4.1 Presentation Layer

Ví dụ:

```text
wizard/
controllers/
reports/
```

Chịu trách nhiệm:

* Nhận input từ người dùng
* Validate dữ liệu cơ bản
* Gọi Application Service
* Render PDF
* Render Excel
* Render HTML

Không được:

* Query database
* Tính Opening Balance
* Tính VAT
* Tính Cost

Presentation phải "ngu".

---

## 4.2 Application Layer

Application Layer mô tả Use Case.

Ví dụ:

```text
Generate General Ledger

Generate Balance Sheet

Generate Inventory Report

Generate Cost Report
```

Application Service:

* Validate nghiệp vụ
* Gọi Engine
* Ghép dữ liệu
* Trả kết quả cho Report

Application Service không được chứa thuật toán kế toán.

---

## 4.3 Domain Layer

Đây là trái tim của Framework.

Bao gồm:

```text
Ledger

Inventory

Tax

Manufacturing

Asset

Payroll
```

Mỗi Domain chứa:

* Business Rules
* Algorithms
* Calculations
* Validation

Ví dụ:

Ledger Domain

```text
Opening Balance

Running Balance

Closing Balance

Counterpart Detection

Ledger Aggregation
```

Inventory Domain

```text
Opening Qty

Incoming

Outgoing

Average Cost

FIFO

Inventory Balance
```

---

## 4.4 Infrastructure Layer

Infrastructure chỉ làm việc với dữ liệu.

Ví dụ:

```text
ORM

SQL

Cache

Queue

Filesystem

External API
```

Không được chứa:

* Business Rules
* Accounting Logic
* Inventory Logic

---

# 5. Dependency Rule

Đây là quy tắc quan trọng nhất.

```text
Presentation

↓

Application

↓

Domain

↓

Infrastructure
```

Không được phép:

```text
Infrastructure

↓

Application
```

Hoặc

```text
Repository

↓

Engine
```

---

# 6. Import Rules

Cho phép:

```text
Presentation
    import Application

Application
    import Domain

Application
    import Infrastructure

Domain
    import Core

Infrastructure
    import Core
```

Không cho phép:

```text
Domain
    import Wizard

Repository
    import Report

Engine
    import Controller
```

Nếu xuất hiện dependency ngược thì phải refactor.

---

# 7. Core Package

```text
shared/core/
```

Đây là package thấp nhất.

Bao gồm:

```text
constants.py

exceptions.py

enums.py

types.py

validators.py

helpers.py
```

Core không được import bất kỳ package nào phía trên.

---

# 8. Domain Package

Ví dụ:

```text
shared/domain/

ledger/

inventory/

tax/

manufacturing/

assets/
```

Mỗi Domain gồm:

```text
engine.py

models.py

rules.py

calculators.py

validators.py
```

Ví dụ:

```text
ledger/

    engine.py

    balance.py

    counterpart.py

    opening.py

    running.py

    validator.py
```

Không được viết toàn bộ vào một file.

---

# 9. Application Package

```text
shared/application/
```

Chứa:

```text
services/

dto/

commands/

queries/
```

Ví dụ:

```text
services/

    general_ledger_service.py

    balance_sheet_service.py

    cashbook_service.py
```

Service chỉ điều phối.

Ví dụ:

```text
Validate Input

↓

Call Ledger Engine

↓

Return DTO
```

---

# 10. Infrastructure Package

```text
shared/infrastructure/
```

Bao gồm:

```text
repositories/

orm/

sql/

cache/

queue/
```

Repository là nơi duy nhất truy cập database.

Ví dụ:

```text
LedgerRepository

InventoryRepository

TaxRepository
```

---

# 11. Odoo Addons

Business Framework không phải Odoo Module.

Odoo Module chỉ là Adapter.

Ví dụ:

```text
l10n_vn_reports/

wizard/

report/

security/

views/

data/
```

Wizard:

```python
result = GeneralLedgerService.generate(params)
```

Report:

```python
render(result)
```

Không làm gì khác.

---

# 12. Engine Pattern

Mỗi Domain có một Engine.

Ví dụ:

```text
LedgerEngine

InventoryEngine

TaxEngine

CostEngine
```

Engine chỉ biết:

Input

↓

Business Logic

↓

Output

Engine không biết:

* PDF
* Excel
* QWeb
* Wizard
* HTTP

---

# 13. Repository Pattern

Repository chỉ có nhiệm vụ:

```text
Load

Search

Aggregate

Insert

Update
```

Ví dụ:

```python
LedgerRepository.get_move_lines()

LedgerRepository.get_opening_balance()

LedgerRepository.get_counterpart()
```

Không được:

```python
calculate_opening()

calculate_tax()
```

Đó là việc của Engine.

---

# 14. Service Pattern

Application Service điều phối toàn bộ Use Case.

Ví dụ:

```text
Generate General Ledger

↓

Validate Date

↓

Call Repository

↓

Call Ledger Engine

↓

Create DTO

↓

Return Report Data
```

Service không được chứa SQL.

---

# 15. DTO (Data Transfer Object)

Không trả trực tiếp Recordset.

Sai:

```python
return move_lines
```

Đúng:

```python
return GeneralLedgerDTO(
    opening=...,
    lines=...,
    closing=...
)
```

Điều này giúp:

* Dễ test
* Dễ cache
* Không phụ thuộc ORM

---

# 16. Mapping Layer

Financial Statements không được hardcode.

Sai:

```python
if account.code == "111":
```

Đúng:

```text
Balance Sheet

↓

Mapping

↓

Account Codes

↓

Ledger Engine
```

Mọi mapping phải nằm trong database hoặc file cấu hình.

---

# 17. Report Flow

Ví dụ Generate General Ledger.

```text
User

↓

Wizard

↓

GeneralLedgerService

↓

LedgerRepository

↓

account.move.line

↓

LedgerEngine

↓

GeneralLedgerDTO

↓

QWeb Report

↓

PDF
```

Nếu export Excel:

```text
User

↓

Wizard

↓

Service

↓

Engine

↓

DTO

↓

XLSX Report
```

Business Logic hoàn toàn giống nhau.

---

# 18. Error Handling

Mỗi layer chỉ xử lý lỗi thuộc phạm vi của mình.

Presentation:

* Hiển thị lỗi.

Application:

* Validate input.

Domain:

* Business Exception.

Infrastructure:

* Database Exception.

Không throw Exception trực tiếp từ ORM lên UI.

---

# 19. Testing Strategy

Có thể test từng layer riêng.

Presentation

→ UI Test

Application

→ Integration Test

Domain

→ Unit Test

Infrastructure

→ Repository Test

Business Logic được test mà không cần Odoo Report.

---

# 20. Architecture Rules

Mọi Pull Request phải đảm bảo:

✅ Không có Business Logic trong Report.

✅ Không có SQL trong Wizard.

✅ Không có ORM trong Engine.

✅ Không có Calculation trong Repository.

✅ Không Hardcode Account Code.

✅ Không Duplicate Algorithm.

Nếu vi phạm bất kỳ quy tắc nào, Pull Request phải được refactor trước khi merge.

---

# Summary

Part 2 định nghĩa cấu trúc source code của toàn bộ Framework.

Các nguyên tắc quan trọng nhất là:

* Domain là trung tâm của hệ thống.
* Odoo Addons chỉ đóng vai trò Adapter.
* Presentation chỉ hiển thị dữ liệu.
* Application điều phối Use Case.
* Domain thực hiện toàn bộ Business Logic.
* Infrastructure chịu trách nhiệm truy cập dữ liệu.
* Mọi báo cáo đều dùng chung Engine và Repository.

Kiến trúc này giúp Framework có khả năng mở rộng lâu dài, dễ kiểm thử và giảm đáng kể việc lặp code khi triển khai hàng chục báo cáo kế toán VAS.