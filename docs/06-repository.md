
# Part 6 — Repository Design

> **Ghi chú bởi Part 17 §4.4.** Snapshot (§18) và Materialized View (§19)
> cố ý chưa hiện thực: bút toán ghi lùi ngày là chuyện thường ngày ở Việt
> Nam, nên cơ chế vô hiệu hoá snapshot khó hơn bản thân snapshot.


---

# 1. Overview

Repository Layer là tầng duy nhất được phép truy cập dữ liệu.

Mọi truy vấn đến:

* Odoo ORM
* PostgreSQL
* SQL
* Materialized View
* Cache

đều phải đi qua Repository.

Repository đóng vai trò là cầu nối giữa Domain và Odoo.

```text
Domain

↓

Repository Interface

↓

Odoo Repository

↓

ORM / SQL

↓

PostgreSQL
```

---

# 2. Objectives

Repository được thiết kế nhằm:

* Cô lập Business Logic khỏi Data Access.
* Cho phép thay đổi ORM sang SQL mà không ảnh hưởng Engine.
* Tối ưu hiệu năng.
* Dễ Unit Test.
* Hỗ trợ Cache.

---

# 3. Repository Rules

Repository được phép:

* search()
* browse()
* read()
* read_group()
* SQL
* Cache
* Aggregate Query

Repository không được:

* Tính Opening Balance.
* Tính Running Balance.
* Tính VAT.
* Mapping Financial Statement.
* Render Report.

Repository chỉ trả dữ liệu.

---

# 4. Repository Structure

```text
vn_core/

repositories/

├── base_repository.py

├── ledger_repository.py

├── inventory_repository.py

├── tax_repository.py

├── manufacturing_repository.py

├── asset_repository.py

└── partner_repository.py
```

---

# 5. Base Repository

Mọi Repository kế thừa từ:

```python
BaseRepository
```

Chức năng:

* env
* cr
* uid
* company
* logging
* transaction helper

Không chứa nghiệp vụ.

---

# 6. Repository Interface

Ví dụ Ledger Repository.

```python
class ILedgerRepository:

    def get_move_lines(self, filter):
        pass

    def get_opening_lines(self, filter):
        pass

    def get_accounts(self):
        pass

    def get_journals(self):
        pass

    def get_partners(self):
        pass
```

Engine chỉ làm việc với Interface.

---

# 7. Odoo Repository

Implementation.

```python
class OdooLedgerRepository(
    ILedgerRepository
):
```

Đây là nơi:

* ORM
* SQL
* read_group()

được sử dụng.

Không xuất hiện ở Domain.

---

# 8. Query Strategy

Repository phải chọn phương pháp truy vấn phù hợp.

| Use Case    | Strategy   |
| ----------- | ---------- |
| Dữ liệu ít  | ORM search |
| Tổng hợp    | read_group |
| Báo cáo lớn | SQL        |
| Dashboard   | Cache      |

Không sử dụng một cách duy nhất cho mọi trường hợp.

---

# 9. Ledger Repository

Input.

```text
LedgerFilter
```

Output.

```text
MoveLineDTO
```

Không trả:

```python
account.move.line
```

---

# 10. Inventory Repository

Input.

```text
InventoryFilter
```

Output.

```text
StockMoveDTO
```

Nguồn dữ liệu:

* stock_move
* stock_move_line
* stock_valuation_layer

---

# 11. Manufacturing Repository

Nguồn dữ liệu.

* mrp_production
* stock_move
* workorder
* valuation_layer

Output.

```text
ManufacturingDTO
```

---

# 12. Tax Repository

Nguồn dữ liệu.

* account_tax
* account_move
* account_move_line

Output.

```text
VATDTO
```

---

# 13. Data Mapping

Repository luôn chuyển đổi:

```text
ORM Record

↓

DTO
```

Không truyền Recordset lên Domain.

---

# 14. SQL Guidelines

SQL chỉ dùng khi:

* ORM quá chậm.
* read_group không đáp ứng.
* Aggregate dữ liệu lớn.

SQL phải:

* Có parameter binding.
* Không hardcode.
* Có index hỗ trợ.
* Có EXPLAIN ANALYZE trước khi merge.

---

# 15. ORM Guidelines

Ưu tiên:

* read_group()
* search_read()
* mapped()

Hạn chế:

```python
for rec in records:
```

đối với dữ liệu lớn.

---

# 16. Index Strategy

Các bảng lớn cần có index phù hợp.

Ví dụ `account_move_line`:

* company_id
* date
* account_id
* partner_id
* journal_id
* move_id
* parent_state

Index phải phục vụ đúng điều kiện filter phổ biến.

---

# 17. Cache Strategy

Repository có thể cache.

Ví dụ:

* Chart of Accounts
* Journals
* Currency
* Fiscal Year
* Mapping

Không cache:

* account.move.line

trừ khi có Snapshot.

---

# 18. Snapshot Strategy

Đối với dữ liệu lớn.

Có thể tạo:

```text
monthly_snapshot

yearly_snapshot
```

Chỉ lưu:

* Opening Balance
* Closing Balance

Không lưu toàn bộ Journal Items.

Điều này giúp giảm thời gian tính Opening Balance cho các kỳ sau.

---

# 19. Materialized View

Có thể dùng cho:

* Trial Balance
* Balance Sheet
* Profit & Loss

Không dùng cho Journal Detail.

Materialized View phải có cơ chế refresh rõ ràng.

---

# 20. Error Handling

Repository chỉ throw:

* RepositoryException
* DatabaseException

Không throw ValidationException.

Không throw BusinessException.

---

# 21. Testing

Repository Test bao gồm:

* ORM Query Test
* SQL Query Test
* Performance Test
* Index Usage Test
* Empty Dataset Test
* Multi-company Test

---

# 22. Performance Targets

Mục tiêu:

| Report                      | Target   |
| --------------------------- | -------- |
| General Ledger (100k lines) | < 5 giây |
| Trial Balance               | < 2 giây |
| Balance Sheet               | < 1 giây |
| Income Statement            | < 1 giây |
| Cash Book                   | < 2 giây |
| Partner Ledger              | < 5 giây |

(Các con số phụ thuộc vào phần cứng và chiến lược index, nhưng đây là mục tiêu thiết kế.)

---

# 23. Repository Dependency

```text
Service

↓

Engine

↓

Repository Interface

↓

Repository

↓

ORM / SQL

↓

PostgreSQL
```

Không được phép:

```text
Repository

↓

Engine
```

---

# Summary

Repository Layer là tầng truy cập dữ liệu duy nhất của Framework.

Repository có nhiệm vụ:

* Đọc dữ liệu.
* Chuyển đổi sang DTO.
* Tối ưu truy vấn.
* Che giấu chi tiết ORM và SQL.

Nhờ đó:

* Domain không phụ thuộc Odoo ORM.
* Có thể thay đổi chiến lược truy vấn mà không ảnh hưởng Business Logic.
* Hệ thống đạt hiệu năng tốt trên dữ liệu lớn.
* Dễ kiểm thử và bảo trì.