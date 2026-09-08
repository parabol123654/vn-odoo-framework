# Vietnam VAS Framework for Odoo 18 CE

> Đây là nhánh **18.0**. Bản Odoo 14 nằm ở nhánh `14.0` của cùng repo; hai
> nhánh cùng một Domain thuần Python, khác nhau ở tầng Odoo (ORM, view, OWL).

> **Tiếp quản dự án này?** Đọc [`AGENTS.md`](AGENTS.md) trước — nó nói rõ đọc
> tài liệu nào theo thứ tự nào, luật nào không được phá, và thứ gì **cố ý** không
> có để đừng đi "sửa" chúng.


> Sổ sách và báo cáo tài chính theo Chuẩn mực Kế toán Việt Nam (VAS) cho Odoo
> Community Edition, xây dựng trên một Domain thuần Python không phụ thuộc Odoo.

---

## Tình trạng hiện tại

Đây là trạng thái **thật**, không phải kế hoạch. Phần chưa làm được ghi rõ ở
mục Roadmap bên dưới.

| Hạng mục | Tình trạng |
| --- | --- |
| Ledger Engine (số dư đầu kỳ, luỹ kế, đối ứng, tuổi nợ) | Xong |
| Financial Statement Engine + Mapping Engine | Xong |
| Tax Engine (bảng kê GTGT) | Xong |
| 24 báo cáo có giao diện và bản in | Xong |
| Phiếu thu / Phiếu chi (01-TT / 02-TT) | Xong |
| Bảng cân đối kế toán B01-DN | Xong, ánh xạ điền một phần — xem ghi chú |
| Inventory Engine | Xong |
| Manufacturing Cost Engine | Xong — chỉ NVL trực tiếp, xem ghi chú |
| Xuất Excel cho cả 24 báo cáo | Xong |

**268 unit test của Domain chạy không cần Odoo và không cần PostgreSQL**, trong
vài mili-giây. Đó là thước đo chính cho biết kiến trúc còn nguyên vẹn hay đã rò
rỉ — chi tiết ở `docs/16` §7.

---

## Báo cáo đã có

| Báo cáo | Mẫu | Menu |
| --- | --- | --- |
| Sổ Nhật ký chung | S03a-DN | Sổ kế toán |
| Sổ Cái | S03b-DN | Sổ kế toán |
| Bảng cân đối số phát sinh | S06-DN | Sổ kế toán |
| Sổ chi tiết thanh toán với người mua (người bán) | S31-DN | Sổ chi tiết |
| Sổ quỹ tiền mặt / Sổ tiền gửi ngân hàng | S07-DN / S08-DN | Sổ chi tiết |
| Sổ chi tiết bán hàng | S35-DN | Sổ chi tiết |
| Sổ chi phí sản xuất, kinh doanh | S36-DN | Sổ chi tiết |
| Bảng phân bổ nguyên liệu, vật liệu, công cụ, dụng cụ | 07-VT | Sổ chi tiết |
| Bảng tổng hợp công nợ phải thu theo tuổi nợ | — báo cáo quản trị | Sổ chi tiết |
| Bảng tổng hợp công nợ phải trả theo tuổi nợ | — báo cáo quản trị | Sổ chi tiết |
| Bảng cân đối kế toán / Báo cáo tình hình tài chính | B01-DN · B01a-DNN | Báo cáo tài chính |
| Báo cáo kết quả hoạt động kinh doanh | B02-DN · B02-DNN | Báo cáo tài chính |
| Báo cáo lưu chuyển tiền tệ | B03-DN trực tiếp · B03-DNN gián tiếp | Báo cáo tài chính |
| Bảng kê hoá đơn hàng hoá dịch vụ bán ra | phụ lục 01/GTGT | Thuế |
| Bảng kê hoá đơn hàng hoá dịch vụ mua vào | phụ lục 01/GTGT | Thuế |
| Tờ khai thuế giá trị gia tăng | 01/GTGT | Thuế |
| Bảng tổng hợp Nhập - Xuất - Tồn | S11-DN | Kho |
| Thẻ kho (sổ kho) | S12-DN | Kho |
| Sổ chi tiết vật liệu, dụng cụ, sản phẩm, hàng hóa | S10-DN | Kho |
| Báo cáo chi phí sản xuất và giá thành | — báo cáo quản trị | Sản xuất |
| Thẻ tính giá thành sản phẩm, dịch vụ | S37-DN | Sản xuất |
| Sổ tài sản cố định | S21-DN | Tài sản cố định |
| Thẻ tài sản cố định | S23-DN | Tài sản cố định |
| Bảng tính và phân bổ khấu hao TSCĐ | 06-TSCĐ | Tài sản cố định |

Ngoài ra có **Phiếu thu (01-TT)** và **Phiếu chi (02-TT)**, in thẳng từ bút toán
chứ không qua menu báo cáo — chúng là chứng từ, không phải sổ. Nút *In phiếu quỹ*
chỉ hiện trên bút toán thật sự làm dịch chuyển tiền mặt.

Mỗi báo cáo có bản xem trên màn hình (thu gọn nhóm, lọc, bấm vào chứng từ để mở)
và bản in PDF **dùng chung một QWeb template**, nên hai bên không thể lệch nhau.

---

## Cài đặt

```bash
tar -xzf odoo-vn-framework.tar.gz -C ~
cd ~/odoo-vn-framework
python3 scripts/run_domain_tests.py        # 268 test, không cần Odoo

./odoo-bin -c odoo.conf -d YOURDB \
    -i l10n_vn,vn_core,l10n_vn_vas_reports,l10n_vn_stock_reports,l10n_vn_mrp_reports,l10n_vn_asset_reports \
    --stop-after-init
```

`l10n_vn_asset_reports` đọc sổ chi tiết tài sản của OCA
`account_asset_management` (repo `OCA/account-financial-tools`, nhánh 14.0 —
kéo theo `report_xlsx_helper` và `report_xlsx` từ `OCA/reporting-engine`), nên
hai repo đó phải nằm trong `addons_path`. Không dùng TSCĐ thì bỏ module này ra
khỏi lệnh cài là xong.

Cập nhật về sau thì dùng script, đừng gõ tay danh sách module:

```bash
scripts/update.sh YOURDB
```

Dữ liệu ánh xạ TT200 nằm trong `l10n_vn_vas_reports` nhưng ghi vào các trường khai
trên model của `vn_core`. Đó là phân chia có chủ ý — framework giữ model,
localisation giữ dữ liệu — nhưng hệ quả là **hai module phải update cùng nhau**.
Update thiếu một cái sẽ hỏng ở chỗ khó đoán:

```
psycopg2.errors.UndefinedColumn: column "cash_expression"
of relation "vn_report_mapping" does not exist
```

`scripts/update.sh` tự tìm mọi manifest ở gốc repo nên không sót được.

Thêm thư mục gốc của repo vào `addons_path` (các module nằm ngay gốc,
đúng layout Odoo Apps yêu cầu); mẫu cấu hình ở
`scripts/odoo.conf.example`.

Trên WSL nên giải nén vào `~` chứ đừng vào `/mnt/c/` — thư mục Windows mount qua
9P chậm hơn nhiều lần và quyền file không bám.

Nạp dữ liệu mẫu — sổ sách kế toán (22 bút toán trải hai năm, 8 hoá đơn có thuế
GTGT gắn sản phẩm), kho, sản xuất và TSCĐ tuỳ theo module đã cài:

```bash
./odoo-bin shell -c odoo.conf -d YOURDB --no-http < scripts/load_demo_data.py
```

| Item | Version |
| --- | --- |
| Odoo | 18.0 Community Edition |
| Python | 3.10 – 3.12 |
| PostgreSQL | 12+ |
| License | AGPL-3 |

---

## Kiến trúc

```text
Wizard  ──►  Service  ──►  Domain Engine  ──►  Repository interface
                                                      │
                                          Odoo Repository (ORM/SQL)
```

Toàn bộ nghiệp vụ kế toán nằm trong `vn_core/domain/`, và **tầng đó không
được phép import `odoo`** — có script kiểm tra tự động, không phải quy ước suông.
Nhờ vậy Engine test được bằng một repository giả trong bộ nhớ.

```text
vn_core/
├── core/           exceptions, enums, làm tròn tiền tệ, năm tài chính   ← không có odoo
├── dto/            filter, ledger, financial statement, result          ← không có odoo
├── domain/
│   ├── ledger/                 engine + calculators                     ← không có odoo
│   └── financial_statement/    mapping, expression, formula             ← không có odoo
├── infrastructure/ nơi DUY NHẤT có SQL
├── services/       use case, audit log, đổi exception
└── models/         provider (điểm mở rộng), index, model ánh xạ
```

Hai module:

* **`vn_core`** — framework, không chứa gì đặc thù Việt Nam.
* **`l10n_vn_vas_reports`** — biểu mẫu, ánh xạ TT200, bản dịch.
* **`l10n_vn_stock_reports`** — báo cáo kho. Tách riêng vì cần `stock_account`,
  mà doanh nghiệp thương mại hay dịch vụ không có lý do phải cài Inventory.
* **`l10n_vn_mrp_reports`** — báo cáo giá thành. Tách riêng vì cần `mrp`.
* **`l10n_vn_asset_reports`** — báo cáo TSCĐ. Tách riêng vì cần OCA
  `account_asset_management` — Odoo 14 CE không có subledger tài sản.

Phép thử phân chia: xoá hết nội dung tiếng Việt mà module vẫn có ích cho nước
khác thì nó thuộc `vn_core`. Quy tắc đầy đủ ở `docs/16` §3.

---

## Ba điểm nghiệp vụ dễ sai đã được xử lý

Đây là những chỗ khiến báo cáo VAS trông hợp lý mà sai số liệu.

**Số dư đầu kỳ theo năm tài chính.** Tài khoản bảng cân đối luỹ kế từ khi thành
lập; tài khoản kết quả kinh doanh reset vào đầu năm tài chính. Nếu bỏ qua, doanh
thu năm trước sẽ chảy vào Bảng cân đối phát sinh năm nay. Quy tắc nằm trong
calculator, không nằm trong SQL, và sinh ra đúng hai truy vấn thay vì một truy
vấn mỗi tài khoản.

**Tách nợ/có theo từng đối tượng.** Trên Bảng cân đối kế toán, TK 131 tách thành
"Phải thu khách hàng" và "Người mua trả tiền trước", tính **theo từng khách hàng**
rồi mới cộng. Bù trừ trên tài khoản trước sẽ triệt tiêu khách đang nợ với khách
trả trước, và cả hai chỉ tiêu cùng bị thiếu.

**Số dư công nợ tại một ngày trong quá khứ.** `amount_residual` chỉ đúng cho hôm
nay. Báo cáo tuổi nợ chốt ngày 30/6 phải cộng ngược mọi khoản đối trừ phát sinh
sau ngày đó, nếu không hoá đơn đã thu tháng 7 sẽ biến mất khỏi báo cáo tháng 6.

---

## Thông tư 200 hay Thông tư 133

Đặt ở **Cấu hình → Công ty → Thông tư áp dụng**. Báo cáo tài chính tự chọn bộ chỉ
tiêu khớp; không phải chọn lại mỗi lần chạy, vì thông tư là thuộc tính của doanh
nghiệp chứ không phải lựa chọn lúc lập báo cáo.

Đây cũng là chỗ kiểm chứng luận điểm trung tâm của kiến trúc: **thêm TT133 không
sửa một dòng Python nào**. Cùng Financial Statement Engine, cùng bộ phân tích
biểu thức, cùng khối chẩn đoán — chỉ khác dữ liệu ánh xạ.

Và hai bộ khác nhau thật, không phải đổi tên: TT133 có 45 chỉ tiêu thay vì 72,
tổng tài sản là mã 200 chứ không phải 270, và chi phí bán hàng với chi phí quản
lý gộp làm một. Có test khẳng định từng điểm đó.

Báo cáo lưu chuyển tiền tệ có cả hai phương pháp: TT200 dùng **trực tiếp**
(đọc bút toán, phân loại theo tài khoản đối ứng), TT133 dùng **gián tiếp** (đi từ
lợi nhuận, điều chỉnh bằng biến động số dư). Phương pháp là thuộc tính của biểu
mẫu; hệ thống tự chọn engine tương ứng. Gián tiếp **không cần engine mới** — nó
chính là thứ Financial Statement Engine vẫn làm.

---

## Ánh xạ báo cáo tài chính

Không có mã tài khoản nào trong mã nguồn Python. Chỉ tiêu báo cáo được cấu hình
tại **Kế toán → Cấu hình → Statement Mappings**:

| Trường | Ý nghĩa |
| --- | --- |
| `expression` | Chọn tài khoản theo mã: `511*`, `111*,112*,-1113` |
| `formula` | Chỉ tham chiếu mã chỉ tiêu khác: `10 - 11` |
| `sign` | `-1` cho tài khoản dư Có, để in ra số dương |
| `side` | Lấy dư Nợ, dư Có, hay số dư ròng |
| `split_by_partner` | Tính theo từng đối tượng rồi mới cộng |

Công thức được đánh giá bằng parser riêng, **không dùng `eval`** — ánh xạ là dữ
liệu do kế toán sửa qua giao diện nên tuyệt đối không được thực thi mã.

Đổi sang TT133, hay cập nhật theo thông tư mới, là sửa dữ liệu chứ không sửa
Engine.

---

## Truy vết ngược từ báo cáo tài chính

Bấm vào một chỉ tiêu trên Bảng cân đối kế toán hay Báo cáo kết quả kinh doanh sẽ
mở Sổ Cái của **đúng những tài khoản cấu thành chỉ tiêu đó**, cùng kỳ, cùng điều
kiện lọc. Từ dòng sổ bấm tiếp ra bút toán, rồi theo liên kết sẵn có của Odoo về
phiếu kho, lệnh sản xuất, định mức.

```text
Bảng cân đối kế toán
   └─ Phải thu ngắn hạn của khách hàng (131)
        └─ Sổ Cái các TK 131*        ← tổng cộng đúng bằng chỉ tiêu vừa bấm
             └─ Bút toán
                  └─ Hoá đơn / Phiếu kho / Lệnh sản xuất
```

Chỉ tiêu là công thức cũng mở được: mã 100 không có biểu thức riêng, nó là
`110 + 120 + 130`, nên tài khoản của nó là hợp của những chỉ tiêu đó — truy đệ
quy xuống dưới.

Chỉ những chỉ tiêu mà **sổ cộng lại đúng bằng con số vừa bấm** mới mở được. Dòng
tiêu đề và chỉ tiêu nhập tay không có gì để mở, và con trỏ chuột nói điều đó.
Báo cáo lưu chuyển tiền tệ cố ý không bật: biểu thức của nó chọn tài khoản *đối
ứng*, nên Sổ Cái của chúng sẽ ra cả những phát sinh không dính tiền và tổng
không khớp — xem `docs/17` §4.8.

---

## Xuất Excel

Mọi báo cáo đều có nút **Xuất Excel** bên cạnh In PDF. File mang theo đúng phần
xuất xứ như bản in — đơn vị, kỳ, điều kiện lọc — vì một bảng tính rời khỏi màn
hình sinh ra nó và được gửi đi khắp nơi.

Không dùng OCA `report_xlsx`: Odoo 14 đã ship sẵn `xlsxwriter` cho chức năng
Export của chính nó, nên bớt được một phụ thuộc.

**24 báo cáo nhưng chỉ 15 bố cục**, vì nhiều báo cáo dùng chung một dạng DTO.
Thêm một báo cáo mới thường chỉ cần khai tên một bố cục đã có, không phải viết
mã xuất riêng.

---

## Roadmap

**Kế tiếp**

* Hoàn thiện ánh xạ B01-DN. 72 chỉ tiêu đã có cấu trúc và công thức đầy đủ;
  12 chỉ tiêu ít gặp còn để trống biểu thức tài khoản. Báo cáo tự liệt kê tài
  khoản chưa được ánh xạ nên biết chính xác phải điền gì.

**Sau đó**

* Chi phí nhân công trực tiếp (622) và sản xuất chung (627) trong báo cáo giá
  thành. Odoo 14 CE không hạch toán chúng vào sổ, nên cần quyết định lấy từ đâu
  trước khi làm — xem `docs/17` §6.

**Hạn chế đã biết**

* `get_move_lines` nạp toàn bộ kết quả vào bộ nhớ; chưa đạt mục tiêu "hàng triệu
  bút toán". Cần chuyển sang đọc theo lô trước khi làm xuất Excel dạng stream.
* Tài khoản đối ứng của bút toán nhiều dòng trả về mọi tài khoản bên đối diện,
  không phân bổ số tiền. Sổ Cái hiển thị như vậy là đủ; báo cáo lưu chuyển tiền
  tệ dùng cách quy nạp riêng và chính xác — xem `docs/17` §4.3.
* Báo cáo TSCĐ dựa trên OCA `account_asset_management`, vì Odoo 14 CE không có
  `account_asset`. Mẫu S21-DN có cột "nước sản xuất, năm sản xuất" mà subledger
  không lưu — cột in trống có chủ đích; muốn có thì thêm trường vào
  `account.asset` rồi override template.

---

## Tài liệu

`docs/01` … `docs/15` là tài liệu thiết kế gốc, viết **trước** khi code. Một số
phần trong đó cố ý không được hiện thực.

**Đọc `docs/17` trước.** Nó có bảng trạng thái từng Part và ghi lại mọi chỗ mã
nguồn khác thiết kế kèm lý do. Mỗi file thiết kế cũng mang một ghi chú ở đầu trỏ
về đúng mục tương ứng, và có script kiểm tra bắt buộc điều đó
(`scripts/check_repo.py`).

Ba chỗ khác biệt lớn nhất:

* **Part 7 (Report Engine)** — không hiện thực. Odoo đã có `ir.actions.report` +
  QWeb; dựng tầng render riêng là viết lại nền tảng.
* **Part 2 §2 (`shared/` ngoài `addons/`)** — bị `docs/16` bãi bỏ. Odoo chỉ nạp
  thứ nằm trong `addons_path`.
* **Part 3 §2 (16 thư mục con)** — chưa tạo. Package rỗng làm cây thư mục trông
  có kiến trúc mà không có nội dung.

---

## Đóng góp

Pull request cần: đúng tầng, có test, có bản dịch, có khai báo phân quyền, không
hardcode mã tài khoản, không lặp thuật toán. Chi tiết ở `docs/15` §25.

Trước khi gửi:

```bash
python3 scripts/run_domain_tests.py     # Domain, không cần Odoo
./scripts/run_tests.sh                  # đầy đủ, cần Odoo + PostgreSQL
```
