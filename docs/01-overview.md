# Part 1 — System Overview & Design Principles

> **Xem Part 17** để biết mã nguồn hiện có làm được gì. Inventory Engine,
> Tax Engine và Manufacturing Cost Engine mô tả dưới đây **chưa xây**;
> Ledger Engine và Financial Statement Engine thì đã có.


---

# 1. Introduction

## Purpose

Vietnam ERP Framework là một framework mở rộng cho **Odoo 14 Community Edition**, được thiết kế để hiện thực đầy đủ các nghiệp vụ kế toán theo **Chuẩn mực Kế toán Việt Nam (VAS)**, đồng thời cung cấp nền tảng cho các báo cáo tài chính, báo cáo quản trị, quản lý kho và tính giá thành sản xuất.

Framework **không thay thế Odoo Accounting**, mà hoạt động như một tầng nghiệp vụ (Business Framework) nằm phía trên Odoo.

Mục tiêu là tách hoàn toàn:

* Business Logic
* Data Access
* Report Rendering
* User Interface

để hệ thống dễ bảo trì, dễ mở rộng và dễ nâng cấp.

---

# 2. Vision

Framework hướng đến việc xây dựng một nền tảng dùng chung cho toàn bộ các nghiệp vụ kế toán Việt Nam.

Thay vì mỗi báo cáo tự tính toán số liệu, tất cả báo cáo sẽ sử dụng chung các Engine nghiệp vụ.

Ví dụ:

* General Ledger
* Trial Balance
* Balance Sheet
* Income Statement
* Cash Book
* Partner Ledger

đều sử dụng cùng một **Ledger Engine**.

Tương tự:

* Stock Card
* Inventory Ledger
* Inventory Valuation

đều sử dụng cùng một **Inventory Engine**.

Điều này giúp loại bỏ việc lặp code và đảm bảo mọi báo cáo luôn cho kết quả nhất quán.

---

# 3. Problems to Solve

## Problem 1 — Business Logic bị phân tán

Trong nhiều dự án Odoo, mỗi report thường tự viết lại logic:

```python
lines = self.env["account.move.line"].search(domain)

opening = ...

running = ...

closing = ...
```

Khi có nhiều report:

* General Ledger
* Trial Balance
* Partner Ledger

thì cùng một thuật toán được viết lại nhiều lần.

Điều này dẫn đến:

* Khó bảo trì
* Khó kiểm thử
* Dễ phát sinh sai lệch số liệu

---

## Problem 2 — Business Logic phụ thuộc ORM

Ví dụ:

```python
self.env["account.move.line"].search(...)
```

xuất hiện trực tiếp trong:

* Wizard
* Report
* Controller

Khi cần tối ưu bằng SQL hoặc thay đổi datasource, phải sửa rất nhiều nơi.

---

## Problem 3 — Mỗi Report tự tính toán

Ví dụ:

General Ledger tự tính Opening Balance.

Trial Balance cũng tự tính Opening Balance.

Cash Book cũng tự tính Opening Balance.

Nếu một thuật toán thay đổi thì phải sửa ở nhiều nơi.

Đây là nguyên nhân phổ biến gây sai lệch giữa các báo cáo.

---

# 4. Proposed Solution

Toàn bộ nghiệp vụ sẽ được tập trung vào các **Business Engine**.

Ví dụ:

```
Ledger Engine
    ├── Opening Balance
    ├── Running Balance
    ├── Closing Balance
    ├── Counterpart Account
    └── Account Aggregation
```

Các report chỉ sử dụng Engine.

Report không được phép tự tính toán.

---

# 5. Design Principles

## 5.1 Single Source of Truth

Mỗi Domain chỉ có một nguồn dữ liệu chuẩn.

### Accounting

```
account.move.line
```

### Inventory

```
stock_move
stock_valuation_layer
```

### Manufacturing

```
mrp_production
mrp_workorder
```

### Tax

```
account_tax
account_move_line
```

Mọi Engine đều phải đọc dữ liệu từ các nguồn này.

Không tạo bảng trung gian nếu không thật sự cần thiết.

---

## 5.2 Separation of Concerns

Framework chia thành các tầng độc lập:

```
Presentation

↓

Application

↓

Domain

↓

Infrastructure
```

Mỗi tầng chỉ có một trách nhiệm.

---

## 5.3 Dependency Rule

Dependency chỉ được phép đi theo một chiều.

```
Report

↓

Application Service

↓

Business Engine

↓

Repository

↓

Odoo ORM

↓

PostgreSQL
```

Không được phép gọi ngược từ Repository lên Service hoặc Report.

---

## 5.4 DRY (Don't Repeat Yourself)

Mỗi nghiệp vụ chỉ có duy nhất một implementation.

Ví dụ:

* Opening Balance
* Running Balance
* Counterpart Detection
* VAT Calculation
* Inventory Valuation

không được viết lại ở nhiều nơi.

---

## 5.5 Open / Closed Principle

Framework phải cho phép mở rộng mà không sửa mã nguồn hiện có.

Ví dụ:

* Thêm Report mới
* Thêm Mapping mới
* Thêm Tax Rule mới

không làm thay đổi Ledger Engine.

---

## 5.6 Composition over Inheritance

Không thiết kế theo kiểu:

```
GeneralLedger

↓

PartnerLedger

↓

CashBook
```

Thay vào đó:

```
Partner Ledger

↓

uses Ledger Engine
```

Mỗi Report chỉ là một cách hiển thị dữ liệu.

---

# 6. High-Level Architecture

```
+-------------------------+
|        User             |
+------------+------------+
             |
             v
+-------------------------+
| Wizard / Controller     |
+------------+------------+
             |
             v
+-------------------------+
| Application Services    |
+------------+------------+
             |
     +-------+--------+----------------+
     |                |                |
     v                v                v
+-----------+   +-------------+   +-----------+
| Ledger    |   | Inventory   |   | Tax       |
| Engine    |   | Engine       |   | Engine    |
+-----------+   +-------------+   +-----------+
      \             |              /
       \            |             /
        +-----------+------------+
                    |
                    v
      +----------------------------+
      | Financial Statement Engine |
      +-------------+--------------+
                    |
                    v
      +----------------------------+
      | Repository Layer           |
      +-------------+--------------+
                    |
                    v
      +----------------------------+
      | Odoo ORM                   |
      +-------------+--------------+
                    |
                    v
      +----------------------------+
      | PostgreSQL                 |
      +----------------------------+
```

---

# 7. Architecture Layers

## Presentation Layer

Chịu trách nhiệm:

* Wizard
* Report
* API
* Controller

Không chứa Business Logic.

---

## Application Layer

Điều phối luồng nghiệp vụ.

Ví dụ:

```
Generate General Ledger
```

Application Service sẽ:

* Validate Input
* Gọi Ledger Engine
* Chuẩn bị dữ liệu cho Report

Không thực hiện tính toán kế toán.

---

## Domain Layer

Đây là tầng quan trọng nhất của Framework.

Bao gồm:

* Ledger Engine
* Inventory Engine
* Tax Engine
* Manufacturing Engine
* Financial Statement Engine

Toàn bộ Business Logic nằm ở đây.

---

## Infrastructure Layer

Bao gồm:

* Repository
* ORM
* SQL
* Cache
* Queue Job
* File Storage

Không chứa Business Logic.

---

# 8. Domain-Oriented Design

Framework được tổ chức theo Domain thay vì theo loại Report.

Sai:

```
reports/

general_ledger.py

trial_balance.py

cashbook.py
```

Đúng:

```
ledger/
    ledger_engine.py
    ledger_service.py
    ledger_repository.py

inventory/
    inventory_engine.py

tax/
    tax_engine.py
```

Report chỉ là lớp hiển thị kết quả.

---

# 9. Single Source of Truth

| Domain        | Data Source                       |
| ------------- | --------------------------------- |
| Accounting    | account.move.line                 |
| Inventory     | stock_move, stock_valuation_layer |
| Manufacturing | mrp_production, mrp_workorder     |
| Tax           | account_tax, account_move_line    |
| Partner       | res_partner                       |
| Product       | product_product, product_template |

Các bảng trên là nguồn dữ liệu chuẩn.

Engine không đọc dữ liệu từ Report hoặc Wizard.

---

# 10. Core Rules

Các quy tắc sau là bắt buộc trong toàn bộ Framework.

1. Report không được phép tính toán.
2. Wizard không được query database.
3. Repository không chứa Business Logic.
4. Engine không biết UI.
5. Service không biết SQL.
6. ORM không xuất hiện trong Report.
7. Mapping thay cho Hardcode.
8. Mọi Report phải dùng chung Engine.

Nếu một đoạn code vi phạm các quy tắc này thì cần xem lại thiết kế.

---

# 11. Success Criteria

Framework được xem là thành công khi đạt các tiêu chí sau:

* Thêm một Report mới mà không cần sửa Engine.
* Thay đổi biểu mẫu TT200 hoặc TT133 chỉ cần sửa Mapping hoặc Template.
* Có thể thay Repository từ ORM sang SQL mà không ảnh hưởng Domain Layer.
* Có thể nâng cấp Odoo 14 lên Odoo 16 hoặc 18 mà chỉ cần điều chỉnh Infrastructure Layer.
* Có thể Unit Test toàn bộ Business Logic mà không cần render Report.

---

# 12. Summary

Vietnam ERP Framework được xây dựng theo nguyên tắc:

* Business Logic tập trung trong Domain Engine.
* Report chỉ hiển thị dữ liệu.
* Repository chỉ truy cập dữ liệu.
* Service điều phối nghiệp vụ.
* Odoo chỉ đóng vai trò là nền tảng hạ tầng (Infrastructure).

Với kiến trúc này, Framework có thể mở rộng để hỗ trợ hàng chục báo cáo VAS, các nghiệp vụ sản xuất, kho, thuế và giá thành mà vẫn đảm bảo tính nhất quán, khả năng kiểm thử và khả năng nâng cấp lâu dài.