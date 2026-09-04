

# Part 5 — Financial Statement Domain Design

> **Sửa đổi bởi Part 17 §2 và §4.3.** Model ánh xạ ở §7 dưới đây
> (`account_from` / `account_to`) **không được dùng** — hiện thực theo
> `account_expression` của Part 9 §6, cộng thêm hai trường `side` và
> `split_by_partner` mà cả hai tài liệu đều thiếu. Ngoài ra §16 nói phương
> pháp trực tiếp của Lưu chuyển tiền tệ lấy được từ Ledger Summary — điều đó
> không đúng, xem Part 17 §4.3.


---

# 1. Overview

Financial Statement Domain chịu trách nhiệm xây dựng các báo cáo tài chính từ dữ liệu đã được chuẩn hóa bởi **Ledger Domain**.

Financial Statement Domain không đọc trực tiếp `account.move.line`.

Mọi dữ liệu đều phải đi qua `LedgerEngine`.

Điều này đảm bảo:

* Một nguồn dữ liệu duy nhất.
* Không lặp thuật toán.
* Báo cáo luôn nhất quán.

---

# 2. Responsibilities

Financial Statement Domain chịu trách nhiệm:

* Mapping tài khoản kế toán
* Tính chỉ tiêu báo cáo
* Tổng hợp nhiều tài khoản
* Hỗ trợ công thức
* Hỗ trợ nhiều chuẩn báo cáo

Không chịu trách nhiệm:

* Query database
* ORM
* SQL
* PDF
* Excel
* UI

---

# 3. Architecture

```text
                    Ledger Engine
                          │
                          ▼
                 Ledger Summary DTO
                          │
                          ▼
            Financial Statement Engine
                          │
              ┌───────────┼────────────┐
              ▼           ▼            ▼
        Mapping      Formula       Validator
          Engine       Engine         Engine
              │
              ▼
      Financial Statement DTO
              │
              ▼
      Report Renderer (PDF/XLSX)
```

---

# 4. Package Structure

```text
vn_core/

domain/

financial_statement/

├── engine.py
├── repository.py
├── dto.py
├── mapping_engine.py
├── formula_engine.py
├── validators.py
├── rules.py
├── services.py
└── tests/
```

---

# 5. Data Flow

Financial Statement Domain chỉ nhận một input duy nhất:

```text
LedgerSummaryDTO
```

Ví dụ:

```text
Account     Debit     Credit     Balance

111         ...

112         ...

131         ...

331         ...

511         ...

632         ...
```

Không quan tâm dữ liệu lấy từ ORM hay SQL.

---

# 6. Mapping Engine

Đây là thành phần quan trọng nhất.

Mapping Engine chuyển:

```text
Account Code

↓

Financial Statement Line
```

Ví dụ:

```text
111

↓

Tiền và tương đương tiền
```

```text
131

↓

Phải thu khách hàng
```

```text
211

↓

Tài sản cố định hữu hình
```

Không hardcode trong Python.

---

# 7. Mapping Model

Đề xuất Model:

```text
vn.report.mapping
```

Fields:

| Field        | Description                    |
| ------------ | ------------------------------ |
| name         | Mapping Name                   |
| report_type  | balance_sheet / pnl / cashflow |
| line_code    | Mã chỉ tiêu                    |
| line_name    | Tên chỉ tiêu                   |
| account_from | TK bắt đầu                     |
| account_to   | TK kết thúc                    |
| sign         | + hoặc -                       |
| sequence     | Thứ tự                         |
| formula      | Công thức nếu có               |
| company_id   | Công ty                        |

---

# 8. Mapping Example

Ví dụ:

```text
Line

110

Tiền và tương đương tiền
```

Mapping

```text
111

112

113
```

Khi chạy báo cáo:

```text
111

+

112

+

113

↓

Line 110
```

Không cần viết code.

---

# 9. Formula Engine

Một số chỉ tiêu không lấy trực tiếp từ tài khoản.

Ví dụ:

```text
Tổng tài sản

=

100

+

200
```

Hoặc:

```text
Lợi nhuận gộp

=

Doanh thu

-

Giá vốn
```

Formula Engine chịu trách nhiệm tính các dòng này.

---

# 10. Formula Syntax

Đề xuất hỗ trợ cú pháp đơn giản.

Ví dụ:

```text
110 + 120 + 130
```

```text
400 - 500
```

```text
A100 + A200
```

Sau này có thể mở rộng:

```text
SUM(100:150)

ABS(300)

ROUND(100)
```

---

# 11. Financial Statement Engine

Engine thực hiện:

```text
Ledger Summary

↓

Apply Mapping

↓

Apply Formula

↓

Validate

↓

Return DTO
```

Không truy cập Repository.

---

# 12. Financial Statement DTO

```text
FinancialStatementDTO

├── Report Name
├── Fiscal Year
├── Company
├── Currency
└── Lines
```

Line DTO:

| Field     | Description  |
| --------- | ------------ |
| line_code | Mã chỉ tiêu  |
| line_name | Tên chỉ tiêu |
| amount    | Giá trị      |
| level     | Cấp hiển thị |
| parent    | Chỉ tiêu cha |
| sequence  | Thứ tự       |

---

# 13. Supported Reports

Financial Statement Domain hỗ trợ:

* Balance Sheet
* Income Statement
* Cash Flow Statement
* Notes to Financial Statements
* Internal Management Reports

Tất cả dùng cùng một Engine.

---

# 14. Balance Sheet Flow

```text
Ledger Summary

↓

Balance Sheet Mapping

↓

Formula Engine

↓

Balance Sheet DTO

↓

PDF / XLSX
```

---

# 15. Income Statement Flow

```text
Ledger Summary

↓

P&L Mapping

↓

Formula

↓

Income Statement DTO
```

---

# 16. Cash Flow Flow

Cash Flow có thể dùng:

* Direct Method
* Indirect Method

Đều sử dụng:

```text
Ledger Summary

+

Cash Flow Mapping

+

Cash Flow Calculator
```

Không viết Report riêng.

---

# 17. Validation

Engine kiểm tra:

* Mapping tồn tại.
* Không trùng Line Code.
* Không có Formula vòng lặp.
* Formula hợp lệ.
* Mapping không bị thiếu tài khoản.

Nếu lỗi:

Throw BusinessException.

---

# 18. Extension Points

Có thể thêm:

* IFRS Mapping
* VAS Mapping
* TT200
* TT133
* Management Report

Không cần sửa Engine.

Chỉ thêm Mapping.

---

# 19. Performance Strategy

Mapping được cache theo:

* Company
* Report Type

Formula được parse một lần.

Ledger Summary chỉ load một lần.

Engine chỉ xử lý dữ liệu trong bộ nhớ.

---

# 20. Example

Ví dụ Balance Sheet.

Ledger Summary:

```text
111     100,000

112      50,000

131     200,000

331      80,000
```

Mapping:

```text
110

=

111

+

112
```

Engine:

```text
110

=

150,000
```

Không cần viết thêm code cho từng chỉ tiêu.

---

# 21. Future Enhancements

Financial Statement Domain được thiết kế để hỗ trợ:

* Multi-company Consolidation
* Comparative Reports
* Multi-year Reports
* Budget vs Actual
* Branch Reporting
* Segment Reporting
* Custom KPI Reports

Mọi tính năng mới chỉ cần mở rộng Mapping hoặc Formula Engine.

---

# Summary

Financial Statement Domain là tầng chuyển đổi dữ liệu kế toán thành báo cáo tài chính.

Kiến trúc gồm bốn thành phần chính:

* Ledger Engine (nguồn dữ liệu)
* Mapping Engine (ánh xạ tài khoản)
* Formula Engine (tính chỉ tiêu)
* Financial Statement Engine (điều phối)

Nhờ vậy:

* Không hardcode tài khoản trong code.
* Dễ thay đổi theo TT200, TT133 hoặc IFRS.
* Có thể thêm báo cáo mới bằng cấu hình Mapping.
* Giảm đáng kể chi phí bảo trì và nâng cấp.