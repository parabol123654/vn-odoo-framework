
# Part 11 — Service Layer Design

> **Sửa đổi bởi Part 17 §8.4.** Cấu trúc `services/accounting/`,
> `inventory/`, `tax/`… ở §4 dưới đây chưa tách; mọi service kế toán hiện nằm
> trong `services/general_ledger_service.py`. Tên file đã hẹp hơn nội dung —
> nên tách khi thêm domain thứ hai.


---

# 1. Overview

Service Layer là tầng điều phối toàn bộ Use Case của hệ thống.

Trong Odoo, Service Layer không thay thế Model (`models.Model`), mà hoạt động như một lớp Application Service nằm giữa:

* Wizard
* Controller
* Scheduled Action
* REST API

và

* Domain Engine
* Repository

Service Layer không chứa Business Logic.

Service Layer chỉ điều phối luồng xử lý.

---

# 2. Objectives

Service Layer được thiết kế để:

* Chuẩn hóa Use Case.
* Không lặp code giữa Wizard và API.
* Dễ Unit Test.
* Không phụ thuộc giao diện.
* Có thể tái sử dụng.

---

# 3. Position in Architecture

```text id="tso6h6"
Wizard

Controller

Cron Job

RPC

REST API

↓

Application Service

↓

Domain Engine

↓

Repository

↓

Odoo ORM
```

Service là điểm vào của mọi nghiệp vụ.

---

# 4. Package Structure

```text id="zg95d4"
vn_core/

services/

├── base_service.py

├── accounting/

│   ├── general_ledger.py
│   ├── trial_balance.py
│   ├── balance_sheet.py
│   └── income_statement.py

├── inventory/

├── tax/

├── manufacturing/

└── assets/
```

Không đặt Service trong thư mục `models/`.

---

# 5. Service Responsibilities

Service chịu trách nhiệm:

* Validate Input DTO.
* Kiểm tra quyền truy cập.
* Khởi tạo Repository.
* Gọi Domain Engine.
* Trả ResultDTO.

Service không:

* Query ORM trực tiếp.
* Render QWeb.
* Xuất Excel.
* Tính toán nghiệp vụ.

---

# 6. Odoo Integration

Mỗi Odoo Module chỉ đóng vai trò Adapter.

Ví dụ:

```text id="zkp4uh"
Wizard

↓

GeneralLedgerService

↓

LedgerEngine

↓

Report Engine

↓

PDF
```

Wizard không chứa Business Logic.

---

# 7. Service Naming

Tên Service theo Use Case.

Ví dụ:

* GeneralLedgerService
* TrialBalanceService
* BalanceSheetService
* IncomeStatementService
* CashBookService
* StockCardService
* VATPurchaseService

Không đặt tên theo Model Odoo.

---

# 8. Input

Service luôn nhận DTO.

Ví dụ.

```text id="4m9gmn"
LedgerFilter
```

Không truyền:

* env
* context
* dictionary
* nhiều tham số rời rạc

Nếu cần Odoo Environment, Service sẽ nhận trong Constructor hoặc thông qua BaseService.

---

# 9. Output

Service luôn trả:

```text id="7dxbz6"
ResultDTO
```

Trong đó:

Data là:

* LedgerDTO
* FinancialStatementDTO
* InventoryDTO

Không trả ORM Recordset.

---

# 10. Transaction Management

Service là nơi xác định ranh giới Transaction.

Repository không được tự commit.

Engine không được commit.

Việc Commit hoặc Rollback tuân theo cơ chế Transaction của Odoo.

Không gọi `cr.commit()` trong Business Logic, trừ các trường hợp đặc biệt được thiết kế rõ ràng (ví dụ xử lý nền hoặc batch có checkpoint).

---

# 11. Validation Flow

```text id="h7h8y0"
Filter DTO

↓

Validator

↓

Permission Check

↓

Repository

↓

Engine

↓

DTO
```

Nếu Validate thất bại.

Không gọi Repository.

---

# 12. Error Handling

Service xử lý:

* ValidationException
* PermissionException
* BusinessException
* RepositoryException

Service chuyển Exception thành ResultDTO hoặc `UserError` khi được gọi từ Wizard.

Không hiển thị lỗi ORM trực tiếp cho người dùng.

---

# 13. Logging

Service là nơi ghi Audit Log.

Ví dụ.

* Report Name
* Company
* User
* Execution Time
* Parameters

Không ghi Log trong Engine.

---

# 14. Reusability

Một Service có thể được gọi từ:

* Wizard
* Scheduled Action
* REST API
* XML-RPC
* JSON-RPC
* Unit Test

Không thay đổi Business Logic.

---

# 15. Security

Service phải kiểm tra:

* Company
* User Group
* Access Rule

trước khi truy cập dữ liệu.

Không phụ thuộc vào Wizard.

---

# 16. Batch Processing

Service hỗ trợ:

* Batch Reports
* Scheduled Reports
* Background Jobs

Không thay đổi Domain Engine.

---

# 17. Dependency Rules

```text id="l31dfy"
Wizard

↓

Service

↓

Engine

↓

Repository

↓

ORM
```

Không được phép:

```text id="wztlv5"
Engine

↓

Service
```

Hoặc.

```text id="i5lm8q"
Repository

↓

Service
```

---

# 18. Odoo Module Integration

Ví dụ.

Module.

```text id="4p4zzy"
vn_account_reports
```

Wizard.

↓

Service.

↓

Engine.

↓

DTO.

↓

QWeb.

Không đặt Business Logic trong:

* Wizard
* Report AbstractModel
* Controller

---

# 19. Testing

Service Test gồm:

* Valid Filter.
* Invalid Filter.
* Permission Denied.
* Empty Dataset.
* Multi-company.
* Exception Handling.
* Performance.

Domain Engine được Mock khi cần.

---

# 20. Extension

Muốn thêm Report mới.

Chỉ cần:

* Tạo Service mới.
* Đăng ký vào Report Catalog.
* Tạo Wizard.
* Tạo Template.

Không sửa Framework.

---

# Summary

Service Layer là tầng điều phối Use Case của Framework.

Service:

* Nhận FilterDTO.
* Kiểm tra quyền.
* Gọi Repository.
* Gọi Domain Engine.
* Trả ResultDTO.

Service không chứa Business Logic và không phụ thuộc vào giao diện người dùng.

Kiến trúc này phù hợp với mô hình Addons của Odoo, cho phép Wizard, API, Cron và Report cùng sử dụng chung một luồng xử lý mà không lặp mã nguồn.
