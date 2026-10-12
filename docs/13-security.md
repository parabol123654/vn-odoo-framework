
# Part 13 — Security & Access Control Design

> **Đã hiện thực đúng như mô tả.** Xem Part 17 §8 để biết trạng thái chung.


---

# 1. Overview

Security là một phần của Framework, không phải của từng Report.

Framework phải tận dụng toàn bộ cơ chế bảo mật chuẩn của Odoo.

Bao gồm:

* Groups
* Access Rights
* Record Rules
* Multi Company
* ir.rule

Không xây dựng một hệ thống phân quyền riêng.

---

# 2. Objectives

Security Framework được thiết kế nhằm:

* Tuân thủ chuẩn Odoo.
* Không bypass ORM Security.
* Hỗ trợ Multi Company.
* Hỗ trợ phân quyền theo Report.
* Hỗ trợ Audit.
* Dễ mở rộng.

---

# 3. Security Architecture

```text id="w9l6qe"
User

↓

Security Group

↓

Wizard

↓

Application Service

↓

Repository

↓

Odoo ORM

↓

Database
```

Security được kiểm tra ở nhiều tầng.

---

# 4. Odoo Standard

Framework sử dụng:

* ir.model.access.csv
* security.xml
* ir.rule

Không sửa Authentication.

Không sửa Login.

Không sửa Session.

---

# 5. Security Layers

Framework chia Security thành các lớp.

Layer 1

Authentication

↓

Layer 2

Access Rights

↓

Layer 3

Record Rules

↓

Layer 4

Business Permission

↓

Layer 5

Report Permission

---

# 6. User Groups

Ví dụ.

Accounting

```text id="ktpw54"
group_account_user

group_account_manager
```

Inventory

```text id="3hnd3j"
group_stock_user

group_stock_manager
```

Manufacturing

```text id="kcx8cu"
group_mrp_user

group_mrp_manager
```

Framework kế thừa Group chuẩn của Odoo khi có thể.

---

# 7. Report Groups

Framework bổ sung Group cho Report.

Ví dụ.

```text id="qg1gxr"
group_report_general_ledger

group_report_trial_balance

group_report_balance_sheet

group_report_tax

group_report_inventory
```

Có thể gán nhiều Group cho một Report.

---

# 8. Report Permission

Mỗi Report Definition khai báo.

* Allowed Groups
* Company
* Active

Service kiểm tra trước khi thực thi.

---

# 9. Multi Company

Mọi Report phải hỗ trợ Multi Company.

Filter luôn có:

```text id="8s4ikq"
company_id
```

Repository luôn lọc theo Company.

Không trả dữ liệu của Company khác.

---

# 10. Record Rules

Repository luôn truy cập ORM thông qua `env`.

Không sử dụng SQL để bỏ qua Record Rule.

Nếu cần SQL để tối ưu hiệu năng, phải đảm bảo điều kiện lọc tương đương với Record Rule và Company hiện hành.

---

# 11. Business Permission

Một số nghiệp vụ cần kiểm tra thêm.

Ví dụ.

* Fiscal Year Closed.
* Locked Period.
* Archived Company.

Các kiểm tra này thuộc Service hoặc Domain.

Không thuộc Wizard.

---

# 12. Data Isolation

Repository không được:

* Truy vấn chéo Company.
* Truy cập dữ liệu khi chưa xác định Company.
* Trả dữ liệu ngoài phạm vi quyền của người dùng.

---

# 13. sudo()

Framework hạn chế sử dụng:

```python id="mx55z4"
sudo()
```

Chỉ dùng khi:

* Đọc cấu hình hệ thống.
* Đọc Mapping.
* Đọc Metadata.

Không dùng `sudo()` để đọc dữ liệu kế toán hoặc kho nhằm vượt qua phân quyền.

---

# 14. Audit Log

Framework ghi nhận:

* User.
* Company.
* Report.
* Parameters.
* Execution Time.
* Export Format.
* Generated At.

Có thể mở rộng lưu vào model Audit riêng.

---

# 15. Export Security

File Export phải kế thừa quyền của người dùng.

Không tạo File bằng quyền Administrator.

Không chia sẻ File cho User khác nếu không có quyền.

---

# 16. API Security

Nếu triển khai REST API.

Áp dụng:

* Authentication.
* Authorization.
* Company Context.
* Access Rights.

API không được bỏ qua Security của Odoo.

---

# 17. Scheduler

Cron Job phải chạy dưới User xác định.

Không chạy mặc định bằng Administrator nếu không cần thiết.

Khuyến nghị tạo User kỹ thuật riêng cho các tác vụ nền.

---

# 18. Localization

Mọi thông báo lỗi liên quan đến Security phải hỗ trợ:

* vi.po
* en.po

Không hardcode tiếng Việt hoặc tiếng Anh.

---

# 19. Exception

Framework chuẩn hóa các loại lỗi.

Ví dụ.

```text id="vfcv7j"
PermissionException

AccessDeniedException

CompanyMismatchException
```

Khi gọi từ Wizard hoặc UI sẽ chuyển đổi thành `AccessError` hoặc `UserError` theo chuẩn Odoo.

---

# 20. Testing

Security Test bao gồm:

* User không có Group.
* Sai Company.
* Record Rule.
* Multi-company.
* Report Permission.
* Export Permission.
* Scheduler User.

---

# 21. Dependency Rules

```text id="g9p0gb"
User

↓

Wizard

↓

Service

↓

Repository

↓

ORM Security

↓

Database
```

Không được phép:

```text id="7m1f3i"
Repository

↓

sudo()

↓

Read Everything
```

---

# 22. Security Files

Mỗi Module tuân theo cấu trúc chuẩn Odoo.

```text id="z5q6qf"
security/

├── ir.model.access.csv

├── security.xml

└── record_rules.xml
```

Không đặt quyền trong Python.

---

# 23. Translation

Toàn bộ nội dung liên quan đến Security phải được dịch.

Bao gồm:

* Group Name.
* Group Description.
* Access Error.
* Permission Error.
* Menu.
* Wizard.

Tập tin:

```text id="z8rzr2"
i18n/

├── vi.po

└── en.po
```

---

# 24. Odoo Compliance

Framework không thay đổi cơ chế bảo mật của Odoo.

Mọi kiểm tra đều dựa trên:

* Users
* Groups
* Access Rights
* Record Rules
* Company Context

Điều này đảm bảo khả năng nâng cấp và tương thích với Odoo Community Edition.

---

# Summary

Security Framework tận dụng hoàn toàn cơ chế bảo mật chuẩn của Odoo.

Framework chỉ bổ sung:

* Phân quyền theo Report.
* Kiểm tra nghiệp vụ.
* Audit Log.
* Chuẩn hóa Exception.

Nhờ đó:

* Không phá vỡ kiến trúc Odoo.
* Hỗ trợ Multi-company.
* Đảm bảo an toàn dữ liệu.
* Dễ mở rộng.
* Dễ bảo trì.
