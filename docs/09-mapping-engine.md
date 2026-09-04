
# Part 9 — Mapping Engine Design

> **Bổ sung bởi Part 17 §3.** Danh sách trường ở §6 dưới đây chưa đủ để lập
> Bảng cân đối kế toán: thiếu `side` (lấy dư Nợ / dư Có / số dư ròng) và
> `split_by_partner` (tách theo từng đối tượng rồi mới cộng). Không có hai
> trường đó thì chỉ tiêu "Phải thu khách hàng" và "Người mua trả tiền trước"
> đều sai số. Cú pháp `DEBIT()` ở §20 cố ý không hiện thực.


---

# 1. Overview

Mapping Engine chịu trách nhiệm chuyển đổi dữ liệu kế toán thành các chỉ tiêu báo cáo.

Engine không biết:

* account.move.line
* ORM
* SQL

Engine chỉ biết:

```text
Ledger Summary

↓

Account Mapping

↓

Financial Statement Lines
```

Đây là nơi loại bỏ hoàn toàn việc hardcode tài khoản trong source code.

---

# 2. Objectives

Mapping Engine phải hỗ trợ:

* VAS TT200
* VAS TT133
* IFRS
* Internal Reports
* Management Reports

Không cần sửa Python.

Chỉ cần thay Mapping.

---

# 3. Architecture

```text
Ledger Summary

↓

Mapping Definition

↓

Mapping Engine

↓

Mapped Lines

↓

Formula Engine

↓

Financial Statement
```

---

# 4. Data Source

Input.

```text
LedgerSummaryDTO
```

Ví dụ.

| Account | Balance  |
| ------- | -------- |
| 111     | 150,000  |
| 112     | 300,000  |
| 131     | 500,000  |
| 331     | -200,000 |

Mapping Engine không đọc Database.

---

# 5. Mapping Model

Model.

```text
vn.report.mapping
```

Master.

Fields.

| Field       | Description                    |
| ----------- | ------------------------------ |
| code        | Mapping Code                   |
| name        | Mapping Name                   |
| report_type | balance_sheet / pnl / cashflow |
| version     | TT200 / TT133 / IFRS           |
| company_id  | Company                        |
| active      | Active                         |

---

# 6. Mapping Line

Model.

```text
vn.report.mapping.line
```

Fields.

| Field              | Description         |
| ------------------ | ------------------- |
| sequence           | Thứ tự              |
| line_code          | Mã chỉ tiêu         |
| line_name          | Tên chỉ tiêu        |
| parent_id          | Dòng cha            |
| level              | Cấp hiển thị        |
| account_expression | Biểu thức tài khoản |
| sign               | 1 hoặc -1           |
| formula            | Công thức           |
| visible            | Hiển thị            |

---

# 7. Account Expression

Không lưu:

```text
111
112
131
```

Thay vào đó.

Hỗ trợ biểu thức.

Ví dụ.

```text
111
```

```text
111*
```

```text
111,112
```

```text
111*,112*
```

```text
111*,-1118
```

```text
111*,112*,113*
```

Engine sẽ parse Expression.

---

# 8. Expression Examples

```text
111*
```

↓

Tất cả TK bắt đầu bằng 111.

---

```text
131*
```

↓

Tất cả công nợ phải thu.

---

```text
111*,112*
```

↓

Tiền mặt + Tiền gửi.

---

```text
111*,-1113
```

↓

Toàn bộ TK111 ngoại trừ 1113.

---

# 9. Formula

Formula chỉ tham chiếu Line Code.

Ví dụ.

```text
110+120+130
```

Không tham chiếu Account.

Điều này giúp Mapping độc lập với Formula.

---

# 10. Sign Handling

Có trường.

```text
sign
```

Ví dụ.

| Account | Balance | Sign | Result |
| ------- | ------- | ---- | ------ |
| 214     | 100     | -1   | -100   |

Không viết Python.

---

# 11. Parent Structure

Ví dụ.

```text
100

├──110

├──120

└──130
```

Engine hỗ trợ Tree.

Renderer chỉ hiển thị.

---

# 12. Sequence

Không hardcode.

Có Field.

```text
sequence
```

Đổi thứ tự báo cáo không cần sửa code.

---

# 13. Multi Mapping

Một Account.

Có thể Mapping nhiều Report.

Ví dụ.

```text
111

↓

Balance Sheet
```

và.

```text
111

↓

Cash Flow
```

Không xung đột.

---

# 14. Validation

Engine kiểm tra.

* Duplicate Line Code.
* Formula Loop.
* Invalid Expression.
* Parent Not Found.
* Missing Mapping.

Nếu lỗi.

Throw.

```text
MappingException
```

---

# 15. Parser

Engine chia Expression thành Token.

Ví dụ.

```text
111*,112*,-1118
```

↓

```text
111*

112*

-1118
```

Sau đó Resolve Account.

---

# 16. Resolver

Resolver nhận.

```text
111*
```

↓

```text
1111

1112

1113

1118
```

Không cần hardcode.

---

# 17. Execution Flow

```text
Ledger Summary

↓

Expression Parser

↓

Account Resolver

↓

Balance Collector

↓

Sign Processor

↓

Mapping Line

↓

Formula

↓

DTO
```

---

# 18. Cache

Mapping được Cache theo.

* Company
* Report
* Version

Không parse lại mỗi lần.

---

# 19. Testing

Bao gồm.

* Wildcard.
* Exclude.
* Formula.
* Parent Tree.
* Invalid Expression.
* Duplicate.
* Empty Mapping.
* TT200.
* TT133.

---

# 20. Extension

Sau này có thể thêm.

```text
REGEX()

SUM()

AVG()

IF()

CASE()

ACCOUNT_TYPE()

TAG()

ANALYTIC()

CURRENCY()
```

Mà không thay đổi kiến trúc.

---

# Summary

Mapping Engine là lớp chuyển đổi giữa dữ liệu kế toán và báo cáo.

Các thành phần chính:

* Mapping
* Mapping Line
* Expression Parser
* Account Resolver
* Formula Processor

Nhờ đó:

* Không hardcode tài khoản.
* Dễ thay đổi biểu mẫu.
* Hỗ trợ nhiều chuẩn kế toán.
* Có thể mở rộng mà không thay đổi Business Logic.