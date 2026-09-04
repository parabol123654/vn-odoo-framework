
# Part 7 — Report Engine Design

> **Không hiện thực — xem Part 17 §8.3.** Toàn bộ tầng `ReportRenderer`,
> `PDFRenderer`, `XLSXRenderer`… mô tả dưới đây **không được xây**. Odoo đã
> có `ir.actions.report` + QWeb + wkhtmltopdf; dựng tầng trừu tượng render
> riêng lên trên là viết lại nền tảng. Hiện dùng `report.vn.qweb.mixin` cho
> PDF và màn hình (chung một template), `to_primitive` cho JSON, và sẽ dùng
> OCA `report_xlsx` cho Excel.


---

# 1. Overview

Report Engine chịu trách nhiệm chuyển đổi dữ liệu nghiệp vụ thành các định dạng đầu ra.

Report Engine **không thực hiện tính toán kế toán**.

Report Engine **không truy cập cơ sở dữ liệu**.

Report Engine chỉ nhận DTO và render.

---

# 2. Responsibilities

Report Engine chịu trách nhiệm:

* Render PDF
* Render XLSX
* Render CSV
* Render HTML
* Render JSON (API)

Không chịu trách nhiệm:

* Query ORM
* SQL
* Business Logic
* Mapping kế toán
* Opening Balance
* Running Balance

---

# 3. Architecture

```text
User

↓

Wizard

↓

Application Service

↓

Domain Engine

↓

DTO

↓

Report Engine

↓

Renderer

↓

PDF / XLSX / CSV / HTML
```

---

# 4. Package Structure

```text
vn_reports/

├── report_engine.py
├── renderers/
│   ├── pdf_renderer.py
│   ├── xlsx_renderer.py
│   ├── csv_renderer.py
│   ├── html_renderer.py
│   └── json_renderer.py
│
├── templates/
│
├── formatters/
│
├── exporters/
│
└── tests/
```

---

# 5. Report Engine

Report Engine chỉ có ba nhiệm vụ:

1. Chọn Renderer.
2. Truyền DTO.
3. Trả kết quả.

Ví dụ:

```text
LedgerDTO

↓

PDF Renderer

↓

general_ledger.pdf
```

---

# 6. Renderer

Mỗi định dạng có một Renderer riêng.

Ví dụ:

```text
PDFRenderer

XLSXRenderer

CSVRenderer

HTMLRenderer

JSONRenderer
```

Các Renderer đều implement cùng một Interface.

---

# 7. Renderer Interface

```python
class ReportRenderer:

    def render(self, dto):
        pass
```

Không phụ thuộc loại Report.

---

# 8. Report Definition

Mỗi Report được định nghĩa bằng metadata.

Ví dụ:

| Field       | Description          |
| ----------- | -------------------- |
| report_code | general_ledger       |
| report_name | General Ledger       |
| renderer    | pdf/xlsx             |
| template    | general_ledger.xml   |
| service     | GeneralLedgerService |

Report Engine đọc Definition thay vì hardcode.

---

# 9. Report Flow

Ví dụ Generate General Ledger PDF.

```text
User

↓

GeneralLedgerWizard

↓

GeneralLedgerService

↓

LedgerEngine

↓

LedgerDTO

↓

PDFRenderer

↓

general_ledger.pdf
```

Nếu xuất Excel:

```text
User

↓

GeneralLedgerWizard

↓

GeneralLedgerService

↓

LedgerEngine

↓

LedgerDTO

↓

XLSXRenderer

↓

general_ledger.xlsx
```

Business Logic hoàn toàn giống nhau.

---

# 10. Template

Template chỉ hiển thị dữ liệu.

Ví dụ QWeb:

```xml
<t t-foreach="dto.lines" t-as="line">
    ...
</t>
```

Không được:

* Tính Balance.
* Cộng Debit.
* Tính VAT.
* Xử lý điều kiện nghiệp vụ.

---

# 11. Formatter

Formatter chuẩn hóa dữ liệu hiển thị.

Ví dụ:

* Format Date
* Format Currency
* Format Number
* Format Account Code

Formatter không thay đổi giá trị nghiệp vụ.

---

# 12. Exporters

Exporter xử lý ghi dữ liệu ra file.

Ví dụ:

* PDF Export
* Excel Export
* CSV Export

Exporter không biết Business Logic.

---

# 13. PDF Renderer

Sử dụng:

* QWeb
* wkhtmltopdf

Input:

```text
LedgerDTO
```

Output:

```text
general_ledger.pdf
```

---

# 14. XLSX Renderer

Khuyến nghị sử dụng:

OCA `report_xlsx`

Input:

```text
LedgerDTO
```

Output:

```text
general_ledger.xlsx
```

Không đọc ORM.

---

# 15. CSV Renderer

Dùng cho:

* Import
* Audit
* External System

Không định dạng trình bày.

---

# 16. HTML Renderer

Dùng cho:

* Dashboard
* Preview
* Portal

Có thể tái sử dụng Template.

---

# 17. JSON Renderer

Dùng cho:

* REST API
* Mobile
* Integration

Output:

```json
{
  "opening": {},
  "lines": [],
  "summary": {},
  "closing": {}
}
```

---

# 18. Multi-format Support

Một DTO có thể render thành nhiều định dạng.

```text
LedgerDTO

├── PDF

├── XLSX

├── CSV

├── HTML

└── JSON
```

Không cần tính toán lại.

---

# 19. Report Catalog

Report Engine không biết từng Report.

Thay vào đó sử dụng Catalog.

Ví dụ:

| Report         | Service              | Renderer |
| -------------- | -------------------- | -------- |
| General Ledger | GeneralLedgerService | PDF      |
| Trial Balance  | TrialBalanceService  | XLSX     |
| Balance Sheet  | BalanceSheetService  | PDF      |

Catalog có thể cấu hình bằng XML hoặc Model.

---

# 20. Error Handling

Report Engine chỉ xử lý:

* Template Not Found
* Renderer Not Found
* Export Error

Không xử lý:

* Business Validation
* Accounting Rules

---

# 21. Performance Strategy

Đối với Report lớn:

* Stream dữ liệu khi export XLSX nếu cần.
* Không nhân bản DTO nhiều lần.
* Render theo batch với dữ liệu rất lớn.
* Tách việc tính toán và render để dễ cache.

---

# 22. Testing

Các bài kiểm thử:

* PDF Render Test
* XLSX Render Test
* CSV Export Test
* HTML Render Test
* JSON Render Test
* Empty DTO Test
* Large Dataset Test

Business Logic không nằm trong phạm vi kiểm thử của Report Engine.

---

# 23. Extension Points

Có thể bổ sung:

* DOCX Renderer
* ODS Renderer
* XML Export
* XBRL Export
* Digital Signature

Không cần thay đổi Domain Engine.

---

# 24. Dependency Graph

```text
Wizard

↓

Application Service

↓

Domain Engine

↓

DTO

↓

Report Engine

↓

Renderer

↓

Output File
```

Renderer không biết Repository.

Template không biết Engine.

DTO là ranh giới giữa Domain và Presentation.

---

# Summary

Report Engine là tầng trình bày của Framework.

Các nguyên tắc cốt lõi:

* Report chỉ render.
* Template chỉ hiển thị.
* Renderer chỉ xuất dữ liệu.
* DTO là đầu vào duy nhất.
* Business Logic không xuất hiện trong Report.

Nhờ đó:

* Một nghiệp vụ có thể xuất ra nhiều định dạng.
* Dễ bảo trì Template.
* Không lặp code giữa PDF và Excel.
* Có thể mở rộng thêm định dạng mới mà không ảnh hưởng Domain.
