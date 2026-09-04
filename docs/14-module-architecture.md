
# Part 14 — Module Architecture & Packaging

> **Sửa đổi bởi Part 17 §8.6.** Mới có 2 trong 14 module đề xuất ở §5:
> `vn_core` và `l10n_vn_reports`. Đây là chủ ý theo Part 16 §4 — chỉ tách
> module khi thật sự có người muốn cài riêng. `vn_financial_statement` nằm
> trong `vn_core/domain/financial_statement/`: cùng ranh giới, khác cách
> đóng gói.


---

# 1. Overview

Framework được xây dựng hoàn toàn theo chuẩn Addons của Odoo.

Mỗi chức năng là một Module độc lập.

Module chỉ phụ thuộc thông qua:

* `__manifest__.py`
* depends
* XML ID
* Odoo ORM

Không import chéo một cách tùy tiện.

Không tạo Framework chạy ngoài Odoo.

---

# 2. Objectives

Module Architecture được thiết kế nhằm:

* Tuân thủ chuẩn Odoo.
* Dễ cài đặt.
* Dễ nâng cấp.
* Dễ bảo trì.
* Dễ mở rộng.
* Giảm phụ thuộc giữa các Module.

---

# 3. High Level Architecture

```text id="7safm2"
Odoo CE

↓

OCA Modules

↓

Vietnam Framework

↓

Localization Modules

↓

Customer Modules
```

Framework là tầng trung gian.

Không thay thế Odoo.

---

# 4. Module Layers

Framework chia thành các nhóm Module.

Core

↓

Accounting

↓

Inventory

↓

Manufacturing

↓

Reports

↓

Localization

↓

Customer Customization

---

# 5. Suggested Modules

```text id="8c2vkt"
vn_core

vn_report_engine

vn_report_catalog

vn_account_engine

vn_financial_statement

vn_tax

vn_inventory

vn_manufacturing

vn_assets

vn_cashflow

vn_report_xlsx

vn_report_pdf

vn_report_api

l10n_vn_reports
```

Mỗi Module có trách nhiệm rõ ràng.

---

# 6. Core Module

```text id="o0qdyj"
vn_core
```

Bao gồm.

* DTO
* Base Repository
* Base Service
* Base Engine
* Exception
* Utilities
* Common Models

Không phụ thuộc kế toán.

Đây là Module gốc của Framework.

---

# 7. Report Engine Module

```text id="mlt9hz"
vn_report_engine
```

Bao gồm.

* Renderer
* Formatter
* Exporter
* Template Loader

Không chứa Business Logic.

---

# 8. Report Catalog Module

```text id="yg6c8r"
vn_report_catalog
```

Bao gồm.

* Report Definition
* Categories
* Templates
* Parameters
* Report Registry

Quản lý cấu hình báo cáo.

---

# 9. Accounting Engine

```text id="t91n6i"
vn_account_engine
```

Bao gồm.

* Ledger Engine
* Trial Balance Engine
* Journal Engine
* Partner Ledger Engine

Không chứa Wizard.

Không chứa QWeb.

---

# 10. Financial Statement

```text id="qg4kva"
vn_financial_statement
```

Bao gồm.

* Balance Sheet
* Income Statement
* Cash Flow
* Mapping Engine
* Formula Engine

---

# 11. Tax Module

```text id="w0ykvv"
vn_tax
```

Bao gồm.

* VAT Purchase
* VAT Sales
* VAT Summary
* Tax Repository

---

# 12. Inventory Module

```text id="t8b3ba"
vn_inventory
```

Bao gồm.

* Stock Card
* Inventory Ledger
* Stock Valuation
* Warehouse Reports

---

# 13. Manufacturing Module

```text id="6wxwz3"
vn_manufacturing
```

Bao gồm.

* Production Cost
* Material Consumption
* WIP
* Finished Goods Cost

---

# 14. Assets Module

```text id="3iqm4x"
vn_assets
```

Bao gồm.

* Asset Register
* Depreciation
* Asset Ledger

Có thể phụ thuộc OCA nếu cần.

---

# 15. Localization Module

```text id="czxkg4"
l10n_vn_reports
```

Bao gồm.

* TT200 Mapping
* TT133 Mapping
* Vietnamese Templates
* Vietnamese Translation

Không chứa Engine.

---

# 16. Customer Modules

Khách hàng không sửa Framework.

Khách hàng tạo Module riêng.

Ví dụ.

```text id="a4cvjr"
abc_custom_reports

abc_manufacturing

abc_management_reports
```

Các Module này chỉ phụ thuộc Framework.

---

# 17. Standard Odoo Structure

Mỗi Module tuân thủ cấu trúc chuẩn.

```text id="2g8xdy"
module_name/

├── __init__.py

├── __manifest__.py

├── models/

├── wizard/

├── report/

├── services/

├── repositories/

├── engines/

├── dto/

├── security/

├── data/

├── views/

├── report_templates/

├── i18n/

├── demo/

├── tests/

└── static/
```

Các thư mục như `services/`, `repositories/`, `engines/` và `dto/` là phần mở rộng của framework, nhưng vẫn nằm trong Module Odoo nên không ảnh hưởng cơ chế cài đặt của Odoo.

---

# 18. Manifest Rules

Mỗi Module phải khai báo rõ.

* Name
* Version
* Depends
* Data
* Demo
* License
* Installable

Không phụ thuộc vòng lặp.

---

# 19. Dependency Rules

```text id="iz6zcq"
vn_core

↓

vn_report_engine

↓

vn_report_catalog

↓

vn_account_engine

↓

vn_financial_statement

↓

l10n_vn_reports
```

Không import ngược.

Ví dụ.

```text id="xgzq79"
vn_core

↓

vn_financial_statement
```

là không hợp lệ.

---

# 20. OCA Compatibility

Framework ưu tiên tái sử dụng Module OCA.

Ví dụ.

* report_xlsx
* queue_job
* component (khi phù hợp)
* base_sparse_field
* server-tools

Không sao chép mã nguồn từ OCA nếu có thể phụ thuộc trực tiếp.

---

# 21. Module Independence

Có thể cài riêng.

Ví dụ.

Chỉ cần General Ledger.

```text id="d87szy"
vn_core

vn_report_engine

vn_report_catalog

vn_account_engine
```

Không bắt buộc cài Manufacturing.

---

# 22. Translation

Mỗi Module có thư mục.

```text id="ael2k8"
i18n/

vi.po

en.po
```

Bao gồm.

* Menu
* Views
* Reports
* Fields
* Selection
* Help
* Errors

Không hardcode chuỗi hiển thị.

---

# 23. Upgrade Strategy

Mọi thay đổi phải hỗ trợ:

* Update Module (`-u`)
* Install Module (`-i`)
* Migration Script nếu thay đổi Model

Không yêu cầu sửa Core Odoo.

---

# 24. Packaging

Framework có thể phát hành dưới dạng Repository Git.

```text id="f5u0bo"
addons/

vn_core/

vn_report_engine/

vn_account_engine/

vn_financial_statement/

l10n_vn_reports/
```

Người dùng chỉ cần thêm `addons_path` và cài Module theo nhu cầu.

---

# 25. Testing

Mỗi Module có:

* Unit Test.
* Integration Test.
* Demo Data (nếu phù hợp).
* Sample Reports.

Không phụ thuộc dữ liệu của Module khác ngoài các dependency đã khai báo.

---

# Summary

Framework được tổ chức thành các Module Odoo độc lập.

Mỗi Module có trách nhiệm rõ ràng, phụ thuộc thông qua `__manifest__.py` và tuân thủ đầy đủ chuẩn Addons của Odoo.

Kiến trúc này giúp:

* Cài đặt linh hoạt.
* Dễ nâng cấp.
* Dễ kiểm thử.
* Dễ tái sử dụng.
* Tương thích với Odoo Community Edition và các Module OCA.
