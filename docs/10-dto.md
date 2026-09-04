
# Part 10 — DTO (Data Transfer Object) Design

> **Làm rõ bởi Part 17 §4.2.** §18 dưới đây ghi "không dùng Tuple"; ý là
> không trả tuple trần không tên trường. DTO hiện dùng `typing.NamedTuple` —
> có tên trường, bất biến, và trên Python 3.8 là lựa chọn stdlib duy nhất vừa
> bất biến vừa tiết kiệm bộ nhớ.


---

# 1. Overview

DTO (Data Transfer Object) là chuẩn trao đổi dữ liệu giữa các Layer của Framework.

DTO là ranh giới giữa:

* Repository
* Domain
* Service
* Report Engine

Mọi dữ liệu truyền giữa các Layer đều phải sử dụng DTO.

Không sử dụng:

* ORM Recordset
* Dictionary không có cấu trúc
* Tuple
* List không định nghĩa kiểu dữ liệu

---

# 2. Objectives

DTO được thiết kế nhằm:

* Chuẩn hóa dữ liệu.
* Giảm phụ thuộc vào ORM.
* Dễ Unit Test.
* Dễ Serialize.
* Dễ Cache.
* Dễ mở rộng.

---

# 3. DTO Principles

DTO chỉ chứa dữ liệu.

DTO không chứa:

* Business Logic
* SQL
* ORM
* Validation
* Calculation

DTO phải là đối tượng thuần dữ liệu.

---

# 4. Package Structure

```text
vn_core/

dto/

├── common.py
├── ledger.py
├── inventory.py
├── manufacturing.py
├── tax.py
├── financial_statement.py
├── report.py
└── filters.py
```

---

# 5. DTO Categories

Framework chia DTO thành bốn nhóm.

Input DTO

↓

Engine DTO

↓

Output DTO

↓

Report DTO

Mỗi nhóm có trách nhiệm riêng.

---

# 6. Filter DTO

Mọi Report đều nhận Filter DTO.

Ví dụ:

```text
LedgerFilter

InventoryFilter

TaxFilter

AssetFilter
```

Filter không sử dụng Dictionary.

---

# 7. Ledger DTO

Ledger gồm hai cấp.

LedgerDTO

↓

LedgerLineDTO

LedgerDTO chứa:

* Opening
* Lines
* Summary
* Closing

LedgerLineDTO chứa:

* Date
* Journal
* Move
* Account
* Partner
* Label
* Debit
* Credit
* Balance
* Counterpart

---

# 8. Financial Statement DTO

FinancialStatementDTO gồm:

* Company
* Fiscal Year
* Currency
* Report Name
* Report Version
* Lines

FinancialStatementLineDTO gồm:

* Line Code
* Line Name
* Amount
* Level
* Parent
* Sequence

---

# 9. Inventory DTO

InventoryDTO gồm:

* Opening Quantity
* Incoming
* Outgoing
* Ending Quantity
* Ending Value

StockCardLineDTO gồm:

* Date
* Reference
* Warehouse
* Product
* Quantity
* Unit Cost
* Total Cost
* Balance

---

# 10. Tax DTO

TaxDTO gồm:

* Tax Code
* Tax Name
* Tax Base
* Tax Amount
* Invoice Count
* Period

Không chứa ORM Record.

---

# 11. Manufacturing DTO

ManufacturingDTO gồm:

* Production Order
* Product
* Quantity
* Material Cost
* Labor Cost
* Overhead Cost
* Total Cost

---

# 12. Common DTO

Framework có CommonDTO.

Ví dụ:

* CompanyDTO
* PartnerDTO
* CurrencyDTO
* AccountDTO
* JournalDTO
* ProductDTO

Không lặp lại giữa các Domain.

---

# 13. Result DTO

Mọi Service trả về ResultDTO.

ResultDTO gồm:

* Success
* Data
* Messages
* Warnings
* Errors
* Execution Time

Không trả trực tiếp dữ liệu thô.

---

# 14. Report DTO

Report Engine nhận ReportDTO.

ReportDTO gồm:

* Metadata
* Header
* Body
* Footer
* Summary

Renderer không cần biết Domain.

---

# 15. Metadata

Mọi ReportDTO phải có Metadata.

Ví dụ:

* Company
* User
* Printed At
* Fiscal Year
* Currency
* Report Name
* Version

Không tính lại ở Renderer.

---

# 16. Serialization

DTO phải hỗ trợ:

* JSON
* XML
* CSV
* Pickle (nếu cần Cache)

Không phụ thuộc Odoo ORM.

---

# 17. Immutability

Khuyến khích DTO bất biến.

Sau khi tạo DTO:

Không sửa dữ liệu.

Nếu cần thay đổi:

Tạo DTO mới.

Điều này giúp:

* Dễ Debug.
* Dễ Cache.
* Dễ Unit Test.

---

# 18. Naming Convention

Tên DTO luôn kết thúc bằng:

DTO

Ví dụ:

* LedgerDTO
* LedgerLineDTO
* MoveLineDTO
* BalanceSheetDTO
* TaxDTO

Không dùng:

Data

Info

Object

Model

---

# 19. Dependency Rules

Repository

↓

DTO

↓

Engine

↓

Service

↓

Report

DTO không import Repository.

DTO không import Engine.

DTO không import Odoo.

---

# 20. Testing

DTO cần kiểm thử:

* Serialization.
* Equality.
* Empty Data.
* Large Dataset.
* Optional Fields.

Không kiểm thử Business Logic.

---

# Summary

DTO là chuẩn trao đổi dữ liệu của toàn bộ Framework.

Mọi Layer chỉ giao tiếp thông qua DTO.

Nhờ đó:

* Không phụ thuộc ORM.
* Dễ kiểm thử.
* Dễ Cache.
* Dễ Serialize.
* Dễ mở rộng.
* Dễ nâng cấp giữa các phiên bản Odoo.