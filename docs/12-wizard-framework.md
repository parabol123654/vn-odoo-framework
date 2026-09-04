
# Part 12 — Wizard Framework Design

> **Khác tên gọi — xem Part 17 §8.5.** Module là `l10n_vn_vas_reports` chứ không
> phải `vn_reports` (Part 16 §3: nó chứa biểu mẫu đặc thù Việt Nam). Lớp cơ
> sở là AbstractModel `vn.report.wizard.mixin` chứ không phải lớp Python
> `BaseReportWizard`, để mỗi wizard `_inherit` và kế thừa trường theo đúng cơ
> chế Odoo.


---

# 1. Overview

Trong Odoo, Wizard là điểm tương tác giữa người dùng và Business Service.

Wizard có nhiệm vụ:

* Thu thập điều kiện báo cáo.
* Validate dữ liệu đầu vào cơ bản.
* Tạo FilterDTO.
* Gọi Application Service.
* Trả về Action để render Report.

Wizard **không thực hiện Business Logic**.

Wizard **không truy vấn dữ liệu kế toán**.

Wizard **không tính toán báo cáo**.

---

# 2. Objectives

Wizard Framework được thiết kế nhằm:

* Chuẩn hóa toàn bộ Wizard.
* Tái sử dụng UI.
* Không lặp code.
* Dễ mở rộng.
* Tuân thủ chuẩn Odoo TransientModel.

---

# 3. Odoo Architecture

Framework sử dụng đúng kiến trúc của Odoo.

```text
User

↓

Menu

↓

Wizard (TransientModel)

↓

Application Service

↓

Domain Engine

↓

Report Engine

↓

ir.actions.report

↓

PDF / XLSX / CSV
```

Wizard không gọi Repository.

Wizard không gọi ORM trực tiếp để lấy dữ liệu báo cáo.

---

# 4. Package Structure

```text
vn_reports/

wizard/

├── base_report_wizard.py

├── general_ledger.py

├── trial_balance.py

├── balance_sheet.py

├── income_statement.py

├── cash_book.py

├── bank_book.py

├── stock_card.py

└── vat_report.py
```

Tất cả Wizard kế thừa từ BaseReportWizard.

---

# 5. Base Wizard

BaseReportWizard chuẩn hóa các chức năng dùng chung.

Bao gồm:

* Company
* Date Range
* Export Format
* Report Language
* Validation
* Execute Report

Không chứa nghiệp vụ kế toán.

---

# 6. Common Fields

Mọi Wizard báo cáo kế toán nên sử dụng chung các trường sau khi phù hợp:

| Field          | Description      |
| -------------- | ---------------- |
| company_id     | Công ty          |
| date_from      | Từ ngày          |
| date_to        | Đến ngày         |
| fiscal_year_id | Năm tài chính    |
| target_move    | Posted / All     |
| export_format  | PDF / XLSX / CSV |
| language       | Ngôn ngữ báo cáo |

Không phải Report nào cũng dùng tất cả Field.

---

# 7. Accounting Fields

Đối với báo cáo kế toán.

Có thể sử dụng.

* journal_ids
* account_ids
* partner_ids
* analytic_account_ids
* analytic_tag_ids
* currency_id

Field chỉ phục vụ Filter.

---

# 8. Inventory Fields

Đối với kho.

Ví dụ.

* warehouse_ids
* location_ids
* product_ids
* category_ids
* lot_ids

Không dùng Field kế toán.

---

# 9. Manufacturing Fields

Ví dụ.

* production_ids
* workcenter_ids
* bom_ids
* product_ids

---

# 10. Wizard Flow

```text
Open Wizard

↓

User Input

↓

Basic Validation

↓

Create FilterDTO

↓

Application Service

↓

ResultDTO

↓

Report Engine

↓

ir.actions.report
```

Business Logic không nằm trong Wizard.

---

# 11. Validation

Wizard chỉ kiểm tra:

* Date From <= Date To
* Company bắt buộc
* Export Format hợp lệ
* Required Fields

Không kiểm tra:

* Opening Balance
* Closed Period
* Accounting Rules

Các kiểm tra nghiệp vụ thuộc Service hoặc Domain.

---

# 12. Filter Mapping

Wizard luôn tạo DTO.

Ví dụ.

```text
GeneralLedgerWizard

↓

LedgerFilter
```

Không truyền Dictionary.

Không truyền Recordset.

---

# 13. Export Format

Framework chuẩn hóa.

```text
PDF

Excel

CSV

JSON
```

Wizard không biết Renderer.

Wizard chỉ truyền lựa chọn cho Report Engine.

---

# 14. Odoo Actions

Wizard trả về chuẩn Odoo.

Ví dụ.

* ir.actions.report
* ir.actions.act_window
* ir.actions.client
* ir.actions.act_url

Không render PDF trực tiếp trong Wizard.

---

# 15. Security

Wizard sử dụng:

* Access Rights
* Record Rules
* Groups

Không tự kiểm tra SQL Permission.

Không bypass Security của Odoo.

---

# 16. Localization

Mọi Wizard phải hỗ trợ:

* i18n
* vi.po
* en.po

Bao gồm:

* Menu
* Labels
* Help
* Error Message
* Button
* Selection Values

Không hardcode chuỗi hiển thị.

---

# 17. Reusability

Một Wizard chỉ phục vụ một Use Case.

Ví dụ.

GeneralLedgerWizard

↓

GeneralLedgerService

Không dùng một Wizard cho nhiều nghiệp vụ khác nhau.

Nếu có nhiều báo cáo dùng cùng Filter, kế thừa từ BaseReportWizard thay vì sao chép mã.

---

# 18. Performance

Wizard không:

* Đọc account.move.line.
* Chạy SQL.
* Tính toán dữ liệu.

Wizard chỉ xử lý dữ liệu đầu vào.

---

# 19. Testing

Wizard Test bao gồm:

* Required Fields.
* Invalid Date Range.
* Default Values.
* FilterDTO Mapping.
* Action Returned.
* Multi-company.
* Multi-language.

Không kiểm thử Business Logic.

---

# 20. Odoo UI Standards

Wizard phải tuân theo UX của Odoo.

* Sử dụng Form View.
* Button theo chuẩn Odoo.
* Không dùng JavaScript tùy chỉnh nếu không cần thiết.
* Tận dụng widget mặc định.
* Hỗ trợ chế độ Desktop và Web.

---

# 21. Dependency Rules

```text
Menu

↓

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

```text
Wizard

↓

Repository
```

Hoặc.

```text
Wizard

↓

Engine
```

Wizard luôn đi qua Service.

---

# 22. Extension

Muốn thêm Report mới.

Chỉ cần:

* Tạo Wizard mới.
* Kế thừa BaseReportWizard.
* Khai báo Report Definition.
* Gọi Service tương ứng.

Không sửa Wizard Framework.

---

# 23. Integration with Odoo

Wizard Framework được triển khai hoàn toàn bằng:

* models.TransientModel
* XML Form View
* ir.actions.act_window
* ir.actions.report
* Security Groups
* Access Rights

Không yêu cầu sửa Core Odoo.

Không yêu cầu Module Patch.

---

# Summary

Wizard Framework là tầng giao tiếp giữa người dùng và Application Service.

Wizard chỉ có bốn nhiệm vụ:

* Thu thập dữ liệu đầu vào.
* Kiểm tra hợp lệ cơ bản.
* Chuyển đổi thành FilterDTO.
* Gọi Service và trả về Action của Odoo.

Toàn bộ Business Logic, truy vấn dữ liệu và tính toán báo cáo đều được tách sang các tầng phía dưới.

Nhờ đó:

* Wizard ngắn gọn.
* Dễ bảo trì.
* Dễ kiểm thử.
* Tuân thủ chuẩn phát triển của Odoo.
* Có thể tái sử dụng cho nhiều module và nhiều loại báo cáo.
