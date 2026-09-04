# Part 16 — Repository Layout

> **Xem thêm Part 17** để biết mã nguồn hiện có làm được gì và những chỗ hiện
> thực cố ý khác với Part 01–15.

Tài liệu này ghi lại cách sắp xếp mã nguồn thực tế, và **ghi đè một điểm trong
Part 2**. Đọc phần "Quyết định 1" trước khi thắc mắc tại sao không có `shared/`.

---

## 1. Cây thư mục

```text
odoo-vn-framework/
│
├── README.md                     # Giới thiệu dự án
├── CHANGELOG.md                  # Semantic Versioning (Part 15 §21)
├── LICENSE                       # AGPL-3
├── requirements.txt              # Phụ thuộc Python ngoài Odoo
├── .gitignore
├── .editorconfig
├── .pre-commit-config.yaml       # black, isort, flake8, pylint-odoo
├── .pylintrc
│
├── docs/                         # 01 … 16, tài liệu thiết kế
│
├── scripts/
│   ├── odoo.conf.example         # Mẫu cấu hình, có addons_path
│   ├── run_tests.sh              # Test đầy đủ, cần Odoo + PostgreSQL
│   └── run_domain_tests.py       # Test Domain, KHÔNG cần Odoo
│
├── vn_core/                      # Các module Odoo nằm ngay gốc repo
└── l10n_vn_reports/              # (layout Odoo Apps store yêu cầu)
```

Các module nằm **ngay gốc repo** — apps.odoo.com quét manifest ở đúng một cấp
thư mục dưới gốc, và đây cũng là layout của các repo OCA. Thư mục gốc được thêm
vào `addons_path`; `docs/` và `scripts/` không có manifest nên Odoo bỏ qua.
(Trước đây module nằm trong `addons/`; đổi khi publish lên Odoo Apps.)

---

## 2. Quyết định 1 — Không có `shared/`

Part 2 §2 đề xuất `shared/` nằm ngoài `addons/`, và Part 2 §11 nói "Business
Framework không phải Odoo Module".

**Không làm như vậy.** Odoo 14 chỉ import những gì nằm trong `addons_path`. Một
package `shared/` ở ngoài sẽ cần:

* đóng gói pip riêng và cài đặt riêng,
* quản lý `PYTHONPATH` trên mọi môi trường (dev, CI, staging, production),
* đồng bộ version giữa package và addon — khi hai bên lệch nhau, lỗi hiện ra ở
  runtime chứ không ở lúc cài module.

Part 14 §17 đã đặt `services/`, `repositories/`, `engines/`, `dto/` **bên trong**
module, và đó là phương án được chọn. Framework vẫn tách tầng đầy đủ; nó chỉ
không tách *thư mục cài đặt*.

Điều quan trọng cần giữ không phải vị trí thư mục, mà là **Domain không import
`odoo`**. Điều đó vẫn đúng và được kiểm tra tự động: `scripts/run_domain_tests.py`
chạy toàn bộ test Domain sau khi đã cắt bỏ mọi package có dính Odoo.

---

## 3. Quy tắc đặt tên module

Part 14 §5 dùng lẫn cả `vn_*` và `l10n_vn_*`. Chốt một quy tắc:

| Tiền tố      | Chứa gì                                                        | Ví dụ |
| ------------ | -------------------------------------------------------------- | ----- |
| `vn_*`       | Framework: DTO, Engine, Repository, Service. Không dữ liệu VN. | `vn_core` |
| `l10n_vn_*`  | Đặc thù Việt Nam: mapping TT200/TT133, biểu mẫu, bản dịch.     | `l10n_vn_reports` |

Phép thử: **nếu xoá hết nội dung tiếng Việt mà module vẫn có ích cho một nước
khác, nó là `vn_*`.** Ledger Engine không biết gì về Việt Nam — nó tính số dư đầu
kỳ theo năm tài chính, việc mọi nước đều làm. Ngược lại "Mẫu số S03b-DN" thì chỉ
Việt Nam có.

---

## 4. Khi nào tách module mới

Part 14 §5 liệt kê 14 module. **Đừng tạo hết ngay.** Một module chỉ nên sinh ra
khi có người thực sự muốn cài nó mà không cài cái kia.

Lộ trình đề xuất:

```text
Hiện tại        vn_core, l10n_vn_reports
Khi làm thuế    + l10n_vn_tax
Khi làm kho     + l10n_vn_inventory
Khi làm giá thành + l10n_vn_costing
Khi làm TSCĐ    + l10n_vn_assets       (phụ thuộc OCA account_asset_management)
```

Những module Part 14 nêu mà tôi đề nghị **hoãn**:

* `vn_report_engine` — hiện chỉ có QWeb PDF, chưa đủ nội dung để thành module.
  Tách khi thêm XLSX/CSV/JSON renderer.
* `vn_report_catalog` — đáng tách khi số báo cáo vượt khoảng 10. Dưới mức đó,
  `ir.actions.report` + menu của Odoo đã làm đúng việc đó rồi.
* `vn_account_engine`, `vn_financial_statement` — tách khỏi `vn_core` khi
  `vn_core` phình quá lớn, chưa phải bây giờ.

Tách module quá sớm tạo ra chi phí thật: mỗi module là một `__manifest__.py`,
một chuỗi dependency, một bộ test, một lần cài đặt phải kiểm tra.

---

## 5. Bên trong một module

Bốn tầng của Part 2 §3 map vào thư mục như sau:

| Tầng           | Thư mục                              | Được import `odoo`? |
| -------------- | ------------------------------------ | ------------------- |
| Core           | `core/`                              | Không               |
| Domain         | `domain/<bounded_context>/`          | **Không**           |
| DTO            | `dto/`                               | Không               |
| Application    | `services/`                          | Có                  |
| Infrastructure | `infrastructure/`                    | Có                  |
| Presentation   | `wizard/`, `report/`, `views/`, `static/` | Có             |
| Odoo adapter   | `models/`                            | Có                  |

`models/` chỉ chứa những gì buộc phải là model Odoo: index trên bảng có sẵn,
provider làm extension point, model cấu hình. Nghiệp vụ không nằm ở đây.

Ví dụ `vn_core` hiện tại:

```text
vn_core/
├── core/            exceptions, enums, utils/{number,dates}
├── dto/             common, filters, ledger, financial_statement,
│                    result, serialization
├── domain/
│   ├── ledger/
│   │   ├── repository.py          # Interface — hợp đồng duy nhất ra ngoài
│   │   ├── engine.py              # Orchestrator
│   │   └── calculators/           # opening, running, closing, sided,
│   │                              # counterpart, aging
│   └── financial_statement/
│       ├── repository.py          # Interface ánh xạ
│       ├── engine.py              # ánh xạ → chỉ tiêu
│       ├── expression.py          # 111*, 111*,-1113
│       └── formula.py             # 10 - 11, parser riêng, không eval
├── infrastructure/  base_repository, odoo_ledger_repository,
│                    odoo_mapping_repository        ← nơi duy nhất có SQL
├── services/        base_service, general_ledger_service
├── models/          ledger_provider (điểm mở rộng), account_move_line (index),
│                    vn_report_mapping (model ánh xạ)
├── security/        ir.model.access.csv
├── views/           vn_report_mapping_views.xml
└── tests/           fakes, test_calculators, test_ledger_engine,
                     test_serialization, test_aging,
                     test_financial_statement, test_odoo_ledger_repository
```

Domain mới (`inventory`, `tax`, `manufacturing`) thêm vào `domain/` theo đúng
khuôn đó: một `repository.py` interface, một `engine.py`, một thư mục
`calculators/`. `financial_statement/` là ví dụ đã có thật của khuôn này.

---

## 6. Chiều phụ thuộc giữa module

```text
account  (Odoo CE)
   ↓
vn_core
   ↓
l10n_vn_reports ── l10n_vn_tax ── l10n_vn_inventory ── l10n_vn_costing
   ↓
<module của khách hàng>
```

Không có mũi tên ngược. `vn_core` không được `depends` vào bất kỳ `l10n_vn_*`
nào — nếu một ngày nó cần, nghĩa là có mã đặc thù Việt Nam đã lọt vào framework
và cần chuyển ra.

Module của khách hàng (`abc_custom_reports`) chỉ `depends` vào framework, không
sửa framework. Điểm mở rộng chính là `vn.ledger.provider`.

---

## 7. Chạy test

**Test Domain — không cần Odoo, không cần PostgreSQL:**

```bash
python3 scripts/run_domain_tests.py
```

Chạy trong vài chục milli-giây. Dùng cái này trong lúc code.

**Test đầy đủ — cần Odoo và PostgreSQL:**

```bash
./scripts/run_tests.sh
```

Hai lệnh riêng biệt là có chủ ý: nếu bao giờ `run_domain_tests.py` bắt đầu cần
Odoo mới chạy được, tức là đã có import `odoo` lọt vào Domain và kiến trúc đang
rò rỉ.
