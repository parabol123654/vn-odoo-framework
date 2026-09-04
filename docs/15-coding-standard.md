
# Part 15 — Coding Standards & Development Guidelines

> **Ghi chú bởi Part 17 §8.** Tên `LedgerRepository` ở §4 dưới đây nay tách
> thành `ILedgerRepository` (interface, tầng Domain) và
> `OdooLedgerRepository` (hiện thực, tầng Infrastructure), đúng theo
> Part 6 §6–7.


---

# 1. Overview

Framework phải tuân thủ đồng thời:

* Python PEP 8
* Odoo Coding Guidelines
* OCA Coding Standards
* Clean Architecture
* SOLID Principles

Mục tiêu của Coding Standard là:

* Code dễ đọc.
* Code dễ Review.
* Code dễ Test.
* Code dễ Upgrade.
* Code dễ đóng góp.

Framework ưu tiên khả năng bảo trì hơn là viết ngắn.

---

# 2. General Principles

Mọi thay đổi phải đảm bảo:

* Không sửa Core Odoo.
* Không Monkey Patch.
* Không Duplicate Code.
* Không Hardcode.
* Không Side Effect.

Ưu tiên:

* Readability
* Simplicity
* Maintainability

---

# 3. Odoo Compliance

Framework phải tuân thủ chuẩn Odoo.

Ví dụ.

* models.Model
* models.TransientModel
* fields.*
* api.depends
* api.onchange
* api.constrains

Không tự xây dựng ORM.

Không thay đổi Registry.

---

# 4. Naming Convention

Module.

```text id="kdr4xp"
vn_core

vn_account_engine

vn_financial_statement
```

Model.

```text id="kkgj6q"
vn.report.definition

vn.report.mapping

vn.report.audit
```

Python Class.

```text id="hnm8l8"
GeneralLedgerService

LedgerRepository

LedgerEngine
```

DTO.

```text id="0ffgjl"
LedgerDTO

LedgerFilter

MoveLineDTO
```

Repository luôn kết thúc bằng:

```text id="xtr36q"
Repository
```

Service luôn kết thúc bằng:

```text id="ymwwzw"
Service
```

Engine luôn kết thúc bằng:

```text id="nv6wsk"
Engine
```

---

# 5. File Organization

Một file Python chỉ nên chứa:

* Một Class chính.

Hoặc:

* Một nhóm Class liên quan chặt chẽ.

Không tạo file dài hàng nghìn dòng.

---

# 6. Method Size

Khuyến nghị.

Một Method.

* 20–50 dòng.

Nếu vượt quá.

Xem xét tách thành Method nhỏ hơn.

---

# 7. Function Responsibility

Một Function.

Chỉ thực hiện.

Một nhiệm vụ.

Không kết hợp:

* Query.
* Validate.
* Calculate.
* Render.

Trong cùng Function.

---

# 8. Layer Rules

Wizard.

↓

Service.

↓

Engine.

↓

Repository.

↓

ORM.

Không gọi ngược.

Ví dụ.

Repository.

↓

Service.

là không hợp lệ.

---

# 9. Business Logic

Business Logic chỉ được đặt trong:

* Domain Engine.

Không đặt trong.

* Wizard.
* Report.
* XML.
* Controller.
* Repository.

---

# 10. Repository Rules

Repository chỉ thực hiện:

* ORM Query.
* SQL Query.
* Mapping sang DTO.

Repository không:

* Validate.
* Calculate.
* Render.

---

# 11. DTO Rules

DTO.

Không chứa.

* ORM.
* SQL.
* Business Logic.

DTO chỉ là dữ liệu.

---

# 12. Exception Rules

Không sử dụng.

```python id="fbmxpr"
except:
    pass
```

Không bỏ qua Exception.

Exception phải:

* Được Log.
* Được Translate.
* Được xử lý đúng tầng.

---

# 13. Logging

Sử dụng chuẩn Logging của Python/Odoo.

Ghi Log.

* Execution Time.
* Report.
* User.
* Company.
* Error.

Không ghi dữ liệu nhạy cảm như mật khẩu hoặc token.

---

# 14. SQL Guidelines

SQL chỉ sử dụng khi cần.

Ưu tiên.

* ORM.
* read_group().

SQL phải.

* Parameterized.
* Có Index phù hợp.
* Được Review.
* Có Performance Test.

Không nối chuỗi SQL bằng dữ liệu đầu vào của người dùng.

---

# 15. Performance Guidelines

Không sử dụng.

```python id="fsg6qn"
for line in move_lines:
```

để thực hiện Query bên trong vòng lặp.

Tránh.

* N+1 Query.
* ORM lồng nhau.
* browse() không cần thiết.

Ưu tiên.

* read_group().
* Batch Query.
* Prefetch của ORM.
* Cache khi phù hợp.

---

# 16. XML Guidelines

XML chỉ khai báo.

* Menu.
* Action.
* View.
* Report.
* Security.
* Data.

Không đặt Business Logic trong XML.

---

# 17. Translation

Mọi chuỗi hiển thị.

Phải hỗ trợ.

* vi.po
* en.po

Bao gồm.

* Menu.
* Wizard.
* Report.
* Help.
* Error.
* Selection.

Không hardcode chuỗi giao diện trong Python hoặc XML khi có thể dùng cơ chế dịch của Odoo.

---

# 18. Testing Standards

Mỗi Module.

Có.

* Unit Test.
* Integration Test.
* Security Test.
* Performance Test.

Mọi Bug.

Phải có Test trước khi Fix.

---

# 19. Git Standards

Branch.

Ví dụ.

```text id="tzd7l9"
feature/general-ledger

feature/trial-balance

bugfix/opening-balance

hotfix/vat-report
```

Commit Message.

Ví dụ.

```text id="0oxg3i"
feat(account): add ledger engine

fix(report): opening balance calculation

refactor(repository): optimize sql query
```

Khuyến nghị tuân theo Conventional Commits.

---

# 20. Documentation

Mỗi Module.

Có.

* README.md
* CHANGELOG.md
* LICENSE
* SECURITY.md (nếu phát hành công khai)

Các Class và Method công khai cần có Docstring ngắn mô tả mục đích.

---

# 21. Versioning

Áp dụng Semantic Versioning.

Ví dụ.

```text id="n4j0r3"
1.0.0

1.1.0

1.2.0

2.0.0
```

Không thay đổi API công khai trong Minor Version.

---

# 22. Dependency Rules

Không Import vòng.

Ví dụ.

```text id="vqm9pd"
Service

↓

Repository

↓

Service
```

Không hợp lệ.

Dependency luôn một chiều.

---

# 23. OCA Compatibility

Ưu tiên sử dụng.

* report_xlsx
* queue_job
* server-tools
* web
* account-financial-reporting (khi phù hợp)

Không sao chép mã nguồn từ OCA nếu có thể phụ thuộc trực tiếp.

Khi mở rộng module OCA, ưu tiên kế thừa thay vì sửa trực tiếp.

---

# 24. Upgrade Strategy

Framework phải hỗ trợ.

* Install.
* Update.
* Uninstall.
* Migration.

Không yêu cầu sửa Database thủ công ngoài các Migration Script đã được kiểm soát.

---

# 25. Code Review Checklist

Mỗi Pull Request cần kiểm tra.

* Đúng Layer.
* Đúng Dependency.
* Có Test.
* Có Translation.
* Có Security.
* Có Documentation.
* Không Hardcode.
* Không Duplicate.
* Đúng Odoo Convention.

---

# 26. Development Checklist

Trước khi Merge.

* Code chạy trên Odoo 14 CE.
* Không có lỗi pylint (theo cấu hình dự án).
* Không có lỗi cú pháp XML.
* Manifest hợp lệ.
* Translation cập nhật.
* Security cập nhật.
* Test Pass.
* Performance đạt yêu cầu.

---

# 27. Project Conventions

Toàn bộ Repository sử dụng cấu trúc thống nhất.

```text id="a3h9pd"
addons/

docs/

scripts/

tests/

requirements.txt

README.md

.pre-commit-config.yaml

.pylintrc

.editorconfig
```

Khuyến nghị sử dụng:

* black
* isort
* pylint-odoo
* pre-commit

để đồng nhất chất lượng mã nguồn.

---

# Summary

Coding Standards là nền tảng đảm bảo Framework phát triển bền vững.

Framework tuân thủ:

* Python PEP 8.
* Odoo Coding Guidelines.
* OCA Best Practices.
* Clean Architecture.
* SOLID Principles.

Mục tiêu cuối cùng là tạo ra một Framework:

* Dễ đọc.
* Dễ mở rộng.
* Dễ kiểm thử.
* Dễ nâng cấp.
* Tương thích hoàn toàn với Odoo Community Edition.
