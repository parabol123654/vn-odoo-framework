
# Part 8 — Report Catalog & Report Definition

> **Sửa đổi bởi Part 17 §4.1.** `ReportRegistry.register()` ở §7 dưới đây
> **không được dùng**: một dict toàn cục nạp lúc import bị chia sẻ giữa mọi
> database trong cùng worker process. Hiện dùng `ir.actions.report` + menu
> của Odoo như §4 mô tả.


---

# 1. Overview

Report Catalog là nơi quản lý tất cả báo cáo trong Framework.

Framework **không hardcode**:

* General Ledger
* Trial Balance
* Balance Sheet
* Cash Book
* Stock Card

Thay vào đó, mỗi báo cáo được khai báo bằng **Report Definition**.

Report Engine chỉ cần đọc Definition để biết:

* Gọi Service nào.
* Dùng Template nào.
* Render bằng Renderer nào.
* Hiển thị Wizard nào.

---

# 2. Objectives

Report Catalog phải đáp ứng:

* Không hardcode Report.
* Dễ thêm Report mới.
* Hỗ trợ nhiều Output Format.
* Hỗ trợ nhiều Template.
* Hỗ trợ phân quyền.
* Hỗ trợ Multi Company.
* Hỗ trợ Localization.

---

# 3. Architecture

```text
User
   │
   ▼
Report Catalog
   │
   ▼
Report Definition
   │
   ▼
Application Service
   │
   ▼
DTO
   │
   ▼
Renderer
```

Report Catalog không biết Business Logic.

---

# 4. Report Definition

Mỗi Report gồm các thông tin:

| Field          | Description                  |
| -------------- | ---------------------------- |
| report_code    | Mã báo cáo                   |
| report_name    | Tên báo cáo                  |
| category       | Accounting / Inventory / Tax |
| service        | Service xử lý                |
| renderer       | PDF / XLSX / CSV             |
| template       | Template sử dụng             |
| wizard         | Wizard nhập điều kiện        |
| security_group | Nhóm quyền                   |
| sequence       | Thứ tự hiển thị              |
| active         | Kích hoạt                    |

---

# 5. Example

General Ledger.

```yaml
report_code: general_ledger

report_name: General Ledger

service: GeneralLedgerService

renderer:
    - pdf
    - xlsx

template:
    pdf: general_ledger.xml
    xlsx: general_ledger.xlsx

wizard:
    GeneralLedgerWizard
```

Framework không cần biết đây là General Ledger.

---

# 6. Categories

Accounting

* General Journal
* General Ledger
* Trial Balance
* Balance Sheet
* Income Statement
* Cash Book
* Bank Book

Inventory

* Stock Card
* Stock Ledger
* Stock Valuation

Manufacturing

* Production Cost
* Material Consumption
* WIP

Tax

* VAT Purchase
* VAT Sales
* VAT Summary

Assets

* Asset Register
* Depreciation

---

# 7. Report Registration

Mỗi Report tự đăng ký vào Catalog.

Ví dụ.

```python
ReportRegistry.register(
    report_code="general_ledger",
    definition=...
)
```

Framework không sửa code trung tâm.

---

# 8. Wizard Definition

Wizard chỉ khai báo Input.

Ví dụ.

```text
Date From

Date To

Company

Journal

Account

Partner

Analytic

Target Move
```

Wizard không chứa Business Logic.

---

# 9. Filter Mapping

Wizard luôn tạo DTO.

```python
LedgerFilter
```

Ví dụ.

```text
Wizard

↓

LedgerFilter

↓

Service
```

Không truyền Dictionary.

---

# 10. Service Binding

Definition xác định Service.

Ví dụ.

```text
general_ledger

↓

GeneralLedgerService
```

```text
trial_balance

↓

TrialBalanceService
```

Không dùng if/else.

---

# 11. Renderer Binding

Definition quyết định Renderer.

Ví dụ.

```text
General Ledger

↓

PDF
```

Hoặc.

```text
General Ledger

↓

Excel
```

Không sửa Business Logic.

---

# 12. Template Binding

Ví dụ.

```text
General Ledger

↓

general_ledger.xml
```

Hoặc.

```text
General Ledger

↓

general_ledger.xlsx
```

Có thể thay Template mà không sửa Service.

---

# 13. Security

Mỗi Report khai báo:

* User Group
* Company
* Menu
* Access Rule

Framework kiểm tra trước khi gọi Service.

---

# 14. Localization

Một Report có thể có nhiều Template.

Ví dụ.

```text
general_ledger_vi.xml

general_ledger_en.xml
```

Business Logic giữ nguyên.

---

# 15. Report Parameters

Definition có thể khai báo:

```text
Require Date

Require Company

Require Journal

Allow Partner

Allow Analytic

Allow Currency
```

Wizard sinh động dựa trên Definition.

---

# 16. Output Formats

Một Report hỗ trợ nhiều định dạng.

Ví dụ.

```text
PDF

Excel

CSV

JSON
```

Không tạo nhiều Service.

---

# 17. Menu Generation

Menu có thể sinh tự động.

Ví dụ.

```text
Accounting

↓

Reports

↓

General Ledger
```

Dựa trên Category và Sequence.

---

# 18. Versioning

Definition hỗ trợ Version.

Ví dụ.

```text
TT200

TT133

IFRS
```

Cùng một Service.

Khác Template và Mapping.

---

# 19. Testing

Kiểm thử bao gồm:

* Definition hợp lệ.
* Service tồn tại.
* Renderer tồn tại.
* Template tồn tại.
* Wizard đúng Filter.
* Security đúng.

---

# 20. Extension

Để thêm Report mới chỉ cần:

1. Tạo Service.
2. Tạo Template.
3. Đăng ký Report Definition.
4. Tạo Wizard.

Không sửa Framework.

---

# Summary

Report Catalog là lớp quản lý báo cáo của Framework.

Report Catalog không biết nghiệp vụ kế toán.

Nó chỉ quản lý:

* Report Definition
* Service
* Template
* Renderer
* Security
* Menu
* Localization

Nhờ đó Framework có thể mở rộng hàng trăm báo cáo mà không làm thay đổi kiến trúc cốt lõi.