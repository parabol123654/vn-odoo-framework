# Part 17 — Hiện thực thực tế và các điểm khác thiết kế

Part 01–15 là tài liệu thiết kế, viết trước khi code. Part 16 chốt cách sắp xếp
mã nguồn. **Part 17 này ghi lại mã nguồn hiện có làm được gì, và những chỗ hiện
thực cố ý khác với thiết kế.**

Đọc Part 17 trước khi sửa code. Một tài liệu thiết kế mô tả sai mã nguồn còn
nguy hiểm hơn không có tài liệu, vì người đọc tin nó.

---

## §1. Những gì đã có

### Module

| Module | Vai trò |
| ------ | ------- |
| `vn_core` | Framework: Domain, DTO, Repository, Service, model ánh xạ |
| `l10n_vn_reports` | Biểu mẫu VAS, ánh xạ TT200, wizard, bản dịch |
| `l10n_vn_stock_reports` | Thẻ kho (S12-DN), Sổ chi tiết vật liệu (S10-DN), Bảng tổng hợp N-X-T. Tách riêng vì cần `stock_account` |
| `l10n_vn_mrp_reports` | Báo cáo chi phí sản xuất, Thẻ tính giá thành (S37-DN). Tách riêng vì cần `mrp` |
| `l10n_vn_asset_reports` | Sổ TSCĐ (S21-DN), Thẻ TSCĐ (S23-DN), Bảng phân bổ khấu hao (06-TSCĐ). Tách riêng vì cần OCA `account_asset_management` |

`l10n_vn_tax`, `l10n_vn_inventory`, `l10n_vn_costing` trong Part 14 §5 **chưa
tạo**, đúng theo Part 16 §4: chỉ tách module khi thật sự có người muốn cài
riêng. `l10n_vn_assets` của Part 14 thành hiện thực dưới tên
`l10n_vn_asset_reports`, khi điều kiện tách được thoả bởi phụ thuộc OCA.

### Domain

```text
domain/ledger/                  đã xong
    engine.py                   compute_trial_balance, compute_ledger,
                                compute_journal, compute_balances,
                                compute_residual_at_date, compute_aging,
                                compute_expense_ledger (S36-DN: chi tiết bên
                                Nợ, chia ra theo gốc TK đối ứng),
                                compute_allocation_table (07-VT: bảng chéo
                                ghi Có 152/153/242 theo gốc TK ghi Nợ),
                                compute_sales_ledger (S35-DN: doanh thu theo
                                sản phẩm, loại kết chuyển 911, thuế để lại
                                cho bảng kê 01/GTGT)
    calculators/                opening, running, closing, sided, counterpart, aging

domain/financial_statement/     đã xong
    engine.py                   compute (ánh xạ + công thức + so sánh kỳ trước)
    expression.py               111*, 111*,112*, 111*,-1113
    formula.py                  parser riêng, sắp xếp topo, bắt vòng lặp

domain/tax/                     đã xong
    engine.py                   compute_vat_listing
    declaration.py              tờ khai 01/GTGT
    calculators/vat_sign.py     chuẩn hoá dấu theo chiều thuế

domain/inventory/               đã xong
    engine.py                   compute_stock_card, compute_summary
    calculators/running_stock.py

domain/cash_flow/               đã xong
    engine.py                   compute (phương pháp trực tiếp)
    calculators/allocation.py   quy dòng tiền về tài khoản đối ứng

domain/manufacturing/           đã xong — chỉ NVL trực tiếp
    engine.py                   compute (giá thành theo lệnh và theo sản phẩm),
                                compute_cost_card (S37-DN: dở dang đầu kỳ,
                                phát sinh, nhập kho, dở dang cuối kỳ)

domain/asset/                   đã xong — subledger là OCA account_asset_management
    engine.py                   compute_register (S21-DN), compute_cards
                                (S23-DN), compute_allocation (06-TSCĐ, kèm
                                tổng hợp I–IV so với kỳ trước theo tháng lịch).
                                Mặc định chỉ tính khấu hao đã ghi sổ + số dư
                                đầu khai báo; kế hoạch chưa ghi sổ phải bật rõ.
```

### Vì sao tách `l10n_vn_stock_reports`

Part 16 §4 đặt điều kiện tách module: khi có người thật sự muốn cài riêng. Đây
là lần đầu điều kiện đó được thoả. Repository kho phải đọc
`stock.valuation.layer`, tức là phụ thuộc `stock_account`; một doanh nghiệp
thương mại hay dịch vụ dùng sổ sách kế toán không có lý do gì phải cài Inventory.

Đáng chú ý: module mới thêm nguyên một bounded context **chỉ bằng cách
`_inherit` một AbstractModel** (`vn.ledger.provider`), không sửa một dòng nào
trong `vn_core` hay `l10n_vn_reports`. Đó chính là điểm mở rộng đã dựng từ đợt
đầu, và giờ có bằng chứng nó hoạt động.

### Ngày của valuation layer

`stock.valuation.layer` ở Odoo 14 không có trường ngày kế toán riêng, chỉ có
`create_date` — thời điểm ghi bản ghi, không phải thời điểm phát sinh. Ngày hiệu
lực nằm trên `stock.move`, nên repository dùng `COALESCE(sm.date,
svl.create_date)`. Layer không gắn stock move (chủ yếu là đánh giá lại kho) sẽ
rơi về `create_date`. Đây là hạn chế của dữ liệu, không phải lựa chọn.

### Số hoá đơn trên bảng kê

Bảng kê GTGT lấy số hoá đơn từ trường `ref` của chứng từ, nếu trống thì lấy số
bút toán. Hoá đơn điện tử của Viettel, VNPT, MISA… thường ghi số vào `ref`,
nhưng nếu khách lưu ở trường tuỳ biến thì override
`OdooTaxRepository._invoice_number_column`. Đây là điểm cần xác nhận với từng
khách hàng chứ không có đáp án chung.

### Báo cáo

Danh sách đầy đủ ở README §"Báo cáo đã có" — README là nguồn duy nhất của danh
sách này và có guard đối chiếu với code. Mỗi báo cáo dùng **một** QWeb template
cho cả màn hình và PDF.

### Kiểm thử

* 268 unit test Domain — `python3 scripts/run_domain_tests.py`, không cần Odoo.
* Test tích hợp cần DB: `test_odoo_ledger_repository.py`, `test_mapping_data.py`.

Ba guard chạy tự động:

1. Domain không được import `odoo`.
2. `t-att-data-group*` phải render ra chuỗi (xem §4.5).
3. Mọi menu phải có bản dịch gắn reference `ir.ui.menu`.

---

## §2. Sửa đổi so với Part 5 — Model ánh xạ

Part 5 §7 đề xuất `account_from` / `account_to` (khoảng mã). Part 9 §6 đề xuất
`account_expression` (biểu thức). **Hai tài liệu mâu thuẫn nhau.**

Đã chọn **Part 9**. Khoảng mã không diễn đạt được `111*,-1113`, mà loại trừ là
nhu cầu có thật khi doanh nghiệp mở tài khoản chi tiết ngoài dự kiến.

Part 5 §7 xem như đã bị Part 9 §6 thay thế.

---

## §3. Bổ sung vào Part 9 — Hai trường bắt buộc phải có

Danh sách trường ở Part 9 §6 **không đủ để lập Bảng cân đối kế toán**. Đã bổ
sung hai trường vào `vn.report.mapping.line`:

| Trường | Giá trị | Vì sao bắt buộc |
| ------ | ------- | ---------------- |
| `side` | `both` / `debit_only` / `credit_only` | B01-DN tách TK 131 thành "Phải thu khách hàng" (dư Nợ) và "Người mua trả tiền trước" (dư Có) |
| `split_by_partner` | boolean | Việc tách đó phải làm **theo từng đối tượng** rồi mới cộng |

Ví dụ cụ thể. Hai khách trên TK 131: khách A nợ 500, khách B trả trước 200.

| Cách tính | Phải thu khách hàng | Người mua trả tiền trước |
| --------- | ------------------- | ------------------------ |
| Bù trừ tài khoản trước rồi tách | 300 | 0 |
| **Tách theo từng khách rồi cộng** | **500** | **200** |

Dòng đầu là sai, và sai theo kiểu nhìn vẫn hợp lý. Có test dựng đúng tình huống
này kèm một dòng đối chứng in ra số dư ròng 300 để thấy rõ khác biệt:
`test_financial_statement.py::TestPartnerSideSplit`.

Part 9 §20 dự kiến cú pháp `DEBIT()` trong biểu thức. **Không làm.** Nợ/có và
tách theo đối tượng là *cách đo* một con số, không phải *chọn tài khoản nào*.
Để chúng thành trường thì parser giữ nguyên độ đơn giản, và thêm chiều mới sau
này không phải sửa parser.

---

## §4. Sửa đổi so với các Part khác

### §4.1 Part 8 §7 — Không dùng `ReportRegistry.register()`

Part 8 §7 đề xuất registry Python đăng ký lúc import. **Không làm.** Một dict
toàn cục nạp lúc import được chia sẻ giữa mọi database trong cùng worker
process, nên module cài trên DB này sẽ rò sang DB khác.

Thay bằng `ir.actions.report` + menu của Odoo, đúng như Part 8 §4 mô tả. Khi số
báo cáo vượt khoảng 10 mới cân nhắc model `vn.report.definition`.

### §4.2 Part 10 §18 — DTO dùng `NamedTuple`

Part 10 §18 ghi "không dùng Tuple". Ý đúng là không trả tuple trần không tên
trường. `typing.NamedTuple` **có** tên trường, bất biến, và trên Python 3.8 là
lựa chọn stdlib duy nhất vừa bất biến vừa tiết kiệm bộ nhớ —
`dataclass(slots=True)` phải tới 3.10 mới có. `MoveLineDTO` sinh ra mỗi journal
item một thể hiện nên khác biệt này là thật.

### §4.3 Part 5 §16 — Lưu chuyển tiền trực tiếp không lấy được từ Ledger Summary

Part 5 §16 nói cả phương pháp trực tiếp lẫn gián tiếp đều dùng
`LedgerSummaryDTO`. Gián tiếp thì đúng. **Trực tiếp thì không**: khi đã tổng hợp
số dư theo tài khoản, mối liên hệ giữa một phát sinh tiền và nguyên nhân của nó
biến mất.

Vì vậy `CashFlowEngine` đọc **bút toán**, không đọc số dư, rồi hỏi ánh xạ xem
mỗi tài khoản đối ứng thuộc chỉ tiêu lưu chuyển nào.

**Đính chính một giả định cũ của chính tài liệu này.** Bản trước ghi rằng bút
toán nhiều dòng sẽ cần một quy tắc phân bổ tuỳ ý. Sai. Bút toán luôn cân, nên
trong mọi bút toán có dính tiền thì **phía không phải tiền chính là dòng tiền**,
theo từng tài khoản, chỉ đảo dấu:

```
Nợ 111   1.100      tiền vào 1.100
Có 511   1.000  ->  quy cho 511:   1.000
Có 3331    100  ->  quy cho 3331:    100
                                   -----
                                    1.100
```

Không phân bổ theo tỷ lệ, không xấp xỉ, và các phần luôn cộng lại đúng bằng số
tiền đã dịch chuyển — vì bút toán vốn đã cân. Chuyển tiền nội bộ giữa hai tài
khoản tiền tự triệt tiêu và không sinh dòng tiền nào; chuyển tiền có phí ngân
hàng sinh ra đúng khoản phí.

Việc duy nhất còn phải quyết là tài khoản nào được coi là tiền, và đó là dữ liệu
ánh xạ (`cash_expression`) chứ không phải mã nguồn.

**Tự đối chiếu.** Tiền là con số duy nhất trên báo cáo tài chính kiểm chứng được
bằng nguồn độc lập. Chỉ tiêu 70 phải bằng số dư thực tế của các tài khoản tiền;
lệch bao nhiêu thì đúng bằng phần đã rơi qua những tài khoản đối ứng chưa được
ánh xạ, và báo cáo liệt kê chúng ra.

### §4.4 Part 6 §18–19 — Hoãn Snapshot và Materialized View

Chưa làm, có chủ ý. Doanh nghiệp Việt Nam ghi bút toán lùi ngày thường xuyên
(tháng 3 hạch toán chứng từ tháng 12), nên mọi snapshot phải bị vô hiệu khi có
bút toán ghi với `date` nhỏ hơn hoặc bằng mốc snapshot. Cơ chế vô hiệu hoá đó
khó hơn bản thân snapshot. Hiện dựa vào index tổng hợp trên `account_move_line`.

### §4.5 QWeb bỏ qua thuộc tính có giá trị falsy

Không phải sửa thiết kế mà là một cái bẫy của Odoo, ghi lại để khỏi dẫm lại.

QWeb chỉ render `t-att-*` khi giá trị **truthy hoặc đã là chuỗi**. Nhóm đầu tiên
trong vòng lặp có `group_index = 0`, mà `0` là falsy, nên thuộc tính không được
sinh ra và **nhóm đầu tiên của mọi báo cáo không thu gọn được**.

Vì vậy khoá nhóm luôn render thành chuỗi: `t-att-data-group="'g%s' % group_index"`.
Có guard tự động cấm dùng chỉ số trần.

### §4.11 Gián tiếp dùng lại Financial Statement Engine

Part 5 §16 nói cả hai phương pháp lập báo cáo lưu chuyển tiền tệ đều dùng
`LedgerSummaryDTO`. §4.3 đã đính chính phần **trực tiếp** — nó phải đọc bút toán.
Nhưng phần **gián tiếp** thì Part 5 nói đúng: nó đi từ lợi nhuận rồi điều chỉnh
bằng biến động số dư, chính là thứ Financial Statement Engine vẫn làm.

Nên gián tiếp không có engine riêng. Nó chỉ cần thêm tiền đầu kỳ và cuối kỳ, đưa
vào qua đúng hai mã giả mà engine trực tiếp đã dùng — một quy ước ánh xạ dùng
chung cho cả hai phương pháp.

Phương pháp lập là thuộc tính của biểu mẫu (`cash_flow_method`), service chọn
engine theo đó chứ không theo phỏng đoán của người gọi.

**Điểm yếu cố hữu của gián tiếp** là chỉ tiêu 01 (lợi nhuận trước thuế). Biểu thức
`5*,6*,7*,8*,9*,-821*` đúng cả khi chưa kết chuyển lẫn khi đã kết chuyển sang TK
911, vì phần kết chuyển triệt tiêu ở tài khoản gốc rồi hiện lại trên 911. Nhưng
nếu bút toán kết chuyển gộp cả TK 821 vào 911 thì ra lợi nhuận **sau** thuế.
Khối đối chiếu bắt được ngay, và đó là lý do nó phải có.

### §4.10 TT133: bằng chứng cho luận điểm ánh xạ

Toàn bộ tầng Mapping Engine tồn tại với một lời hứa: đổi thông tư là đổi dữ
liệu, không đổi engine. Lời hứa đó nằm trong tài liệu từ đầu mà **chưa bao giờ
được kiểm chứng** — cho tới khi thêm TT133.

Kết quả: không sửa một dòng Python nào trong Domain. Hai file dữ liệu, một
trường chọn thông tư trên `res.company`, và một hàm `default_for()` chọn ánh xạ
khớp. Engine, bộ phân tích biểu thức, bộ đánh giá công thức, khối chẩn đoán —
nguyên vẹn.

Đáng nói là hai bộ biểu mẫu khác nhau thật: 45 chỉ tiêu so với 72, mã tổng tài
sản 200 so với 270, và TT133 gộp chi phí bán hàng với chi phí quản lý làm một
chỉ tiêu. Nếu chỉ khác tên gọi thì phép thử này chẳng chứng minh được gì.

### §4.9 Tờ khai 01/GTGT là mã nguồn, không phải dữ liệu ánh xạ

Báo cáo tài chính dùng `vn.report.mapping` vì đầu vào của chúng là tài khoản, mà
tài khoản nào nuôi chỉ tiêu nào thì khác nhau thật giữa các doanh nghiệp và giữa
các thông tư.

Tờ khai thì không: đầu vào của nó là các nhóm thuế suất trên bảng kê, và số học
của nó do luật cố định — chỉ tiêu 27 bằng 29 + 30 + 32 với mọi người nộp thuế.
Cho cấu hình phần đó là mời người dùng chọn một thứ họ không có quyền chọn, đồng
thời giấu đi thứ đáng kiểm tra duy nhất là số học có đúng không. Nên nó được
viết thẳng trong `domain/tax/declaration.py` và **mỗi quan hệ luật định có một
test riêng**.

Chưa xử lý các chỉ tiêu 32a, 39 và 40b.

### §4.7 Mẫu số trên nhãn menu

Báo cáo luật định hiện thị mẫu số ngay trên menu — `Sổ Cái (S03b-DN)` — vì kế
toán tra theo mã nhanh hơn tra theo tên. Chỉ báo cáo thật sự có mẫu số mới được
gắn: bảng tuổi nợ và bảng tổng hợp N-X-T là báo cáo quản trị, bảng kê GTGT là
phụ lục của tờ khai 01/GTGT — bịa mẫu số cho chúng còn tệ hơn để trống.

Mẫu số vốn khai trong `_report_form_code` của wizard, nên viết thêm vào menu là
tạo bản sao thứ hai, mà hai bản sao thì sẽ lệch. `scripts/check_repo.py` đối
chiếu mọi mã ghi trên menu với mã mà wizard đứng sau nó khai báo.

### §4.8 Drill-down chỉ mở ở nơi số liệu cộng lại đúng

Chỉ tiêu trên B01-DN và B02-DN mở được xuống Sổ Cái của các tài khoản cấu thành.
Engine giải tài khoản cho từng chỉ tiêu, truyền đệ quy qua công thức, nên một
dòng tổng như mã 100 (`110 + 120 + 130`) vẫn biết nó gồm những tài khoản nào.

**B03-DN cố ý không bật.** Biểu thức của báo cáo lưu chuyển tiền tệ chọn tài
khoản **đối ứng** của các phát sinh tiền, không phải tài khoản có số dư. Mở Sổ
Cái của chúng sẽ ra toàn bộ phát sinh của tài khoản đó, kể cả phần không liên
quan tới tiền, nên tổng không bằng con số vừa bấm. Một drill-down mà tổng không
khớp còn tệ hơn không có, vì nó dạy người đọc mất tin vào cả hai con số. Muốn làm
đúng thì cần một màn hình riêng chỉ liệt kê các phát sinh tiền đã quy về tài
khoản đó.

Đích drill là Sổ Cái chứ không phải danh sách `account.move.line`: danh sách trả
lời được "gồm những dòng nào" nhưng mất số dư đầu kỳ, số dư luỹ kế và cột tài
khoản đối ứng — những thứ giúp kế toán nhận ra mình đang xem cái gì.

### §4.6 Định dạng file `.po` của Odoo khác gettext chuẩn

Mỗi mục bắt buộc phải có dòng `#. module: <tên_module>` phía trước. File `.po`
viết tay đúng chuẩn gettext nhưng thiếu marker này sẽ làm **hỏng cả registry**
lúc chuyển ngôn ngữ, với traceback trỏ vào `translate.py` chứ không trỏ vào file.

Ngoài ra một msgid có thể cần nhiều reference: `General Ledger` vừa là tên menu,
vừa là tên action, vừa là chuỗi `_()` trong Python. Thiếu reference
`model:ir.ui.menu` thì menu lặng lẽ hiện tiếng Anh, không báo lỗi gì.

---

## §5. Ràng buộc của Odoo 14 CE

Ghi lại để khỏi phí thời gian tìm.

| Thứ | Tình trạng ở 14.0 |
| --- | ----------------- |
| `odoo.Command` | **Không có**, chỉ từ 15.0. Dùng tuple `(0, 0, {...})` |
| `_('...', arg)` | **Không có**, chỉ từ 16.0. Dùng `_('...') % (arg,)` |
| Manifest key `assets` | **Không có**, chỉ từ 15.0. Kế thừa `web.assets_backend` |
| QWeb client template | Khai qua manifest key `qweb` |
| OWL | 1.x — mount vào action registry cần ComponentWrapper. Đang dùng `AbstractAction` legacy |
| `account_asset` | Enterprise. Khấu hao TSCĐ cần OCA `account_asset_management` |
| `create_index` | Import từ `odoo.tools.sql`, không chắc có ở `odoo.tools` |
| `XlsxWriter` | Odoo 14 ghim **1.1.2** (2018). `Worksheet.ignore_errors` chỉ có từ 3.0 |

---

## §6. Nợ kỹ thuật

Ghi rõ để không quên, không phải để bào chữa.

**`get_move_lines` nạp toàn bộ kết quả.** Interface đã khai trả `Iterable`, nên
đổi sang đọc theo lô được mà không sửa Engine — nhưng Engine hiện `tuple()` lại
để nhóm. Đây chính là mâu thuẫn giữa "DTO bất biến" (Part 10 §17) và "hàng triệu
bút toán" (README), và nó nằm ở một dòng cụ thể. Phải xử lý trước khi làm xuất
Excel dạng stream.

**Tài khoản đối ứng trên Sổ Cái không kèm số tiền.** `CounterpartCalculator`
trả về mọi tài khoản bên đối diện để hiển thị "511, 3331", không phân bổ số
tiền. Với Sổ Cái như vậy là đủ. B03-DN không dùng nó mà dùng
`CashFlowAllocator`, quy được chính xác từng khoản — xem §4.3.

**Phiếu thu / Phiếu chi: đã làm, không tạo model mới.** Phiếu quỹ *chính là* bút
toán trên sổ nhật ký tiền mặt. Tạo model riêng nghĩa là hai bản ghi cho một sự
kiện kinh tế và cả đời phải giữ chúng đồng bộ. Nên `account.move` được thêm loại
phiếu và số phiếu, kèm hai dãy số riêng cấp lúc vào sổ. Sổ quỹ giờ in số phiếu
đúng như S07-DN yêu cầu.

**Giá thành chưa có nhân công và sản xuất chung.** Báo cáo chi phí sản xuất chỉ
gồm chi phí nguyên vật liệu trực tiếp, lấy từ valuation layer nên khớp TK 152 và
155. Chi phí nhân công trực tiếp (622) và sản xuất chung (627) **cố ý không có**:
Odoo 14 Community không hạch toán chúng vào sổ. `costs_hour` của workcenter chỉ
sinh ra số liệu thống kê, không bao giờ thành bút toán, và bản Community cũng
không có tài khoản sản phẩm dở dang.

In một con số thống kê cạnh một con số đã vào sổ, mà trên trang giấy không có gì
nói cái nào là cái nào, thì tệ hơn là in thiếu. Muốn có đủ giá thành thì phải
chọn một trong hai hướng, và đó là quyết định nghiệp vụ chứ không phải kỹ thuật:

1. **Hạch toán thật** — định kỳ phân bổ nhân công và sản xuất chung vào 622/627
   bằng bút toán, gắn tài khoản quản trị theo lệnh sản xuất. Giá thành khớp sổ,
   kế toán bảo vệ được con số. Đổi lại phải thêm quy trình phân bổ.
2. **Số liệu quản trị** — lấy từ thời gian workcenter nhân đơn giá giờ. Không
   cần thêm quy trình, nhưng con số không nằm trong sổ và không dùng để quyết
   toán được.

Engine hiện tại đã sẵn sàng cho cả hai: chỉ cần thêm nguồn chi phí vào
`IManufacturingRepository` và một cột trên báo cáo ghi rõ nguồn.

**Chi phí dở dang** thì suy được: giá trị vật tư đã xuất cho các lệnh chưa hoàn
thành tại ngày báo cáo, để đối chiếu với số dư TK 154. Báo cáo nói rõ con số này
không nằm ở đâu trong sổ.

**Bài học về kiểm chứng phiên bản thư viện.** Phần xuất Excel từng được "kiểm
chứng bằng workbook thật" — nhưng thật trên sandbox có XlsxWriter 3.2.9, trong
khi Odoo 14 ghim 1.1.2. `Worksheet.ignore_errors` chỉ có từ 3.0, nên nó chạy
được ở nơi viết và nổ ở nơi dùng, đúng lúc kế toán bấm Xuất Excel.

Chạy thật vẫn là cách kiểm chứng tốt nhất có, nhưng nó chỉ chứng minh được điều
gì đó về **môi trường đã chạy**. Với thư viện ngoài, phiên bản của môi trường
đích mới là thứ quyết định. Đã xử lý bằng feature-detect và một guard giữ danh
sách API có trong 1.1.2.

**Bình quân cuối kỳ chưa hiện thực.** Odoo tính bình quân gia quyền *liên hoàn*,
tính lại sau mỗi lần nhập. Nhiều doanh nghiệp Việt Nam dùng bình quân cuối kỳ —
một đơn giá chốt cuối tháng. Hai cách cho giá trị tồn cuối kỳ khác nhau. Báo cáo
hiện trung thành với số Odoo đã ghi sổ (nếu không thì lệch với TK 152/155/156),
và bày thêm đơn giá bình quân cuối kỳ ở `average_unit_cost` để thấy chênh lệch.
Muốn hạch toán theo bình quân cuối kỳ thì cần một bút toán đánh giá lại cuối
tháng, không phải sửa báo cáo.

**Dữ liệu ánh xạ vượt ranh giới module.** 18 trường trong `tt200_*.xml` của
`l10n_vn_reports` ghi vào model khai ở `vn_core`. Phân chia này đúng theo
Part 16 §3, nhưng nó tạo một cái bẫy vận hành: update thiếu `vn_core` thì cột
chưa tồn tại mà dữ liệu đã ghi vào, và lỗi báo ở file XML chứ không báo ở chỗ
thật sự thiếu. Đã xử lý bằng `scripts/update.sh` (đọc danh sách module từ
các manifest ở gốc repo) và một guard bắt mọi lệnh `-i`/`-u` trong tài liệu bỏ sót module.

**Dữ liệu demo dồn vào một sổ nhật ký chung.** VAS phân biệt Nhật ký chung với
các nhật ký chuyên dùng (thu tiền, chi tiền, mua hàng, bán hàng). Đủ để test báo
cáo, nhưng khi làm Sổ Nhật ký thu tiền / chi tiền thì phải tách sổ.

---

## §7. Việc kế tiếp

Ba mục cũ ở đây (ánh xạ B01-DN, xuất Excel, Tax Engine) đã xong; danh sách được
viết lại theo thực trạng. Chia theo **loại việc**, vì phần còn lại không cùng một
loại với phần đã làm.

### 7.1 Xây thêm — đoán được khối lượng

1. **Sổ tài sản cố định (S21-DN) và bảng tính khấu hao.** Odoo 14 CE không có
   `account_asset`; cần OCA `account_asset_management`, mà đó là phụ thuộc chưa
   kiểm chứng được.
2. **Chi phí nhân công (622) và sản xuất chung (627) trong giá thành.** Chặn ở
   một quyết định nghiệp vụ, không phải ở kỹ thuật — xem §6.
3. **Thông tư 132** cho doanh nghiệp siêu nhỏ. Thuần dữ liệu, như TT133.
4. **Hiệu lực theo ngày cho ánh xạ.** `version` hiện là Char tự do. Lập lại báo
   cáo kỳ cũ bằng biểu mẫu mới là sai mà nhìn vẫn hợp lý.
5. **Thuyết minh BCTC (B09-DN).** Chủ yếu là văn bản diễn giải — bài toán soạn
   thảo tài liệu, không phải bài toán report engine. Đừng ước lượng chung với
   các báo cáo khác.

### 7.2 Kiểm chứng — không đoán được khối lượng

Đây mới là phần đáng lo, và nó **chưa bắt đầu**.

1. **Chưa từng chạy trên hệ thống tài khoản thật của một doanh nghiệp thật.**
   Toàn bộ kiểm thử dùng chart rút gọn hoặc dữ liệu demo tự sinh.
2. **Chưa có kế toán viên đối chiếu.** Không con số nào trong 16 báo cáo được so
   với một bộ sổ lập tay. Ánh xạ luật định là thứ phải verify, kể cả phần đã điền.
3. **Chưa đo hiệu năng.** `get_move_lines` nạp toàn bộ kết quả vào bộ nhớ; chưa
   ai chạy thử một Sổ Cái nửa triệu dòng.
4. **Chưa kiểm đa công ty và phân quyền thật.** Record rule có trong mã, chưa có
   ai thử với người dùng bị giới hạn.

Hai lỗi nặng nhất tìm được cho tới nay — cột đối ứng in id thay vì mã tài khoản,
và `ignore_errors` không có ở XlsxWriter 1.1.2 — **đều không thể phát hiện bằng
cách viết thêm mã**. Cả hai lộ ra khi có người chạy thật và gửi ảnh màn hình. Đó
là hình dạng của phần việc còn lại.

## §8. Bản đồ tài liệu ↔ mã nguồn

Trạng thái từng Part so với mã nguồn hiện có.

| Part | Trạng thái | Ghi chú |
| ---- | ---------- | ------- |
| 01 Overview | Còn đúng | Nguyên tắc thiết kế được giữ nguyên |
| 02 Layered Architecture | **Khác một phần** | `shared/` ngoài `addons/` bị Part 16 bãi bỏ; các package `commands/`, `queries/`, `orm/`, `sql/`, `cache/`, `queue/` chưa tạo — xem §8.1 |
| 03 Core Framework | **Khác một phần** | Cây 16 thư mục ở §2 chưa tạo — xem §8.1 |
| 04 Ledger Domain | **Khác một phần** | `aggregators/`, `mappers/`, `rules/`, `validators/` chưa tạo — xem §8.2 |
| 05 Financial Statement | Đã sửa | Xem §2, §4.3 |
| 06 Repository | Đã ghi chú | Xem §4.4 |
| 07 Report Engine | **Không hiện thực** | Xem §8.3 |
| 08 Report Catalog | Đã sửa | Xem §4.1 |
| 09 Mapping Engine | Đã bổ sung | Xem §3 |
| 10 DTO | Đã làm rõ | Xem §4.2 |
| 11 Service Layer | **Khác một phần** | Service gộp một file, chưa tách theo domain — xem §8.4 |
| 12 Wizard Framework | **Khác tên gọi** | Module là `l10n_vn_reports`; base wizard là AbstractModel `vn.report.wizard.mixin` — xem §8.5 |
| 13 Security | Còn đúng | Hiện thực đúng như mô tả |
| 14 Module Architecture | **Khác một phần** | Chỉ có 2 trong 14 module đề xuất — xem §8.6 |
| 15 Coding Standard | Còn đúng | Tên `LedgerRepository` ở §4 nay là `ILedgerRepository` + `OdooLedgerRepository` theo đúng Part 6 §6–7 |
| 16 Repository Layout | Còn đúng | Đã cập nhật cây `vn_core` |

### §8.1 Các package chưa tạo — có chủ ý

Part 3 §2 liệt kê 16 thư mục con của `vn_core` (`rules/`, `validators/`,
`mappers/`, `mixins/`, `cache/`, `constants/`, `helpers/`, `enums/`,
`exceptions/`…). Hiện chỉ có `core/`, `dto/`, `domain/`, `infrastructure/`,
`services/`, `models/`, `tests/`.

Lý do: tạo sẵn 16 package rỗng làm cây thư mục trông có kiến trúc mà không có
nội dung, và người đọc phải mở từng cái mới biết nó trống. `enums.py` và
`exceptions.py` hiện là **file** trong `core/`; khi nào chúng đủ lớn thì tách
thành package, không sớm hơn. Cùng lý do với `cache/` và `queue/`: chưa có gì để
cache, chưa có job nền nào.

### §8.2 Aggregator gộp vào Engine

Part 4 §13 đề xuất `aggregators/account.py`, `partner.py`, `journal.py`,
`analytic.py`, mỗi chiều tổng hợp một lớp. Hiện thực dùng enum `GroupBy` với
tuple tên trường, do Engine tiêu thụ.

Bốn lớp đó sẽ giống hệt nhau, chỉ khác một tên trường. Enum khiến việc thêm một
chiều tổng hợp mới là thêm một dòng, và Repository nhận thẳng tuple đó để dựng
`GROUP BY`.

`validators/` và `rules/` cũng chưa tạo: kiểm tra đầu vào hiện nằm trong
`LedgerEngine._load_context` và `FinancialStatementEngine._validate`. Khi có
luật nghiệp vụ thứ ba dùng chung thì tách.

### §8.3 Part 7 — Report Engine không hiện thực

Part 7 đề xuất `ReportRenderer` interface với `PDFRenderer`, `XLSXRenderer`,
`CSVRenderer`, `HTMLRenderer`, `JSONRenderer` và các package `renderers/`,
`formatters/`, `exporters/`.

**Không làm.** Odoo đã có sẵn `ir.actions.report` + QWeb + wkhtmltopdf; dựng một
tầng trừu tượng render riêng lên trên là viết lại nền tảng. Hiện thực:

* PDF và màn hình: `report.vn.qweb.mixin` gọi `ir.ui.view._render_template`,
  **dùng chung một template** nên hai bên không thể lệch nhau.
* JSON: `dto/serialization.py::to_primitive`, đủ cho REST/mobile sau này.
* XLSX: chưa có, sẽ dùng OCA `report_xlsx` chứ không tự viết renderer.

**Cập nhật: đã có renderer thứ hai, và kết luận không đổi.** `xlsx_writer.py`
sinh workbook từ một mô tả sheet khai báo, `xlsx_layouts.py` có một bố cục cho
mỗi *dạng DTO* — 16 báo cáo dùng chung 7 dạng. Nhưng đây vẫn là một writer cụ
thể, không phải tầng đa hình: không có chỗ nào dispatch theo loại renderer.
Wizard cần workbook thì gọi writer, cần PDF thì gọi QWeb.

Cũng không dùng OCA `report_xlsx`: Odoo 14 đã có `xlsxwriter` cho chức năng
Export của nó, nên workbook dựng được mà không thêm phụ thuộc nào.

### §8.4 Part 11 — Service chưa tách theo domain

Part 11 §4 đề xuất `services/accounting/`, `inventory/`, `tax/`,
`manufacturing/`, `assets/`. Hiện tất cả service kế toán nằm trong
`services/general_ledger_service.py`.

Tên file giờ đã hẹp hơn nội dung (nó chứa cả `TrialBalanceService`,
`AgedReceivableService`, `IncomeStatementService`). Nên đổi thành
`accounting_services.py` hoặc tách theo Part 11 khi thêm domain thứ hai. Ghi lại
để không quên.

### §8.5 Part 12 — Tên module và base wizard

Part 12 gọi module là `vn_reports`; thực tế là `l10n_vn_reports`, đúng theo quy
tắc đặt tên ở Part 16 §3 vì nó chứa biểu mẫu đặc thù Việt Nam.

Part 12 §5 gọi lớp cơ sở là `BaseReportWizard`; thực tế là AbstractModel
`vn.report.wizard.mixin`. Dùng AbstractModel để mỗi wizard `_inherit` được và
kế thừa trường theo đúng cơ chế của Odoo, thay vì kế thừa Python thuần.

### §8.6 Part 14 — Mới có 2 trong 14 module

Part 14 §5 đề xuất `vn_core`, `vn_report_engine`, `vn_report_catalog`,
`vn_account_engine`, `vn_financial_statement`, `vn_tax`, `vn_inventory`,
`vn_manufacturing`, `vn_assets`, `vn_cashflow`, `vn_report_xlsx`,
`vn_report_pdf`, `vn_report_api`, `l10n_vn_reports`.

Hiện có `vn_core` và `l10n_vn_reports`. Đây là chủ ý theo Part 16 §4: chỉ tách
module khi có người thật sự muốn cài riêng. `vn_financial_statement` nằm trong
`vn_core/domain/financial_statement/` — cùng ranh giới, khác cách đóng gói.

Mốc tách hợp lý tiếp theo: khi thêm renderer XLSX/CSV thì `vn_report_engine`
mới có nội dung thật.
