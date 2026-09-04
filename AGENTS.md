# AGENTS.md — bàn giao cho người (hoặc AI) tiếp quản

Framework báo cáo kế toán Việt Nam (VAS) trên Odoo 14 Community. 5 module, 24 báo
cáo, 2 thông tư (TT200 và TT133), 268 test Domain chạy không cần Odoo.

Đọc file này trước, hết, rồi mới mở thứ khác.

---

## 1. Đọc theo đúng thứ tự này

| # | File | Vì sao |
| - | ---- | ------ |
| 1 | `README.md` | Hiện trạng: có gì, chạy thế nào, còn thiếu gì |
| 2 | **`docs/17-implementation-status.md`** | **Quan trọng nhất.** Mọi chỗ mã nguồn khác thiết kế, kèm lý do |
| 3 | `docs/16-repository-layout.md` | Cách sắp xếp mã nguồn thực tế |
| 4 | `CHANGELOG.md` | Lịch sử quyết định, đọc từ dưới lên |
| 5 | `scripts/check_repo.py` | 15 lỗi đã từng xảy ra và cách chặn chúng |

**`docs/01` … `docs/15` viết TRƯỚC khi có code.** Vài phần trong đó **cố ý không
được hiện thực**. Mỗi file đã mang một ghi chú ở đầu trỏ về đúng mục trong
Part 17 — đọc ghi chú đó trước khi tin phần còn lại. Part 17 §8 có bảng trạng
thái đủ 16 Part.

Ví dụ cụ thể: **Part 7 mô tả cả một tầng `ReportRenderer` chưa hề được xây**, và
Part 17 §8.3 giải thích tại sao. Đừng đi xây nó.

---

## 2. Ba luật không được phá

**Domain không được import odoo.** `vn_core/core/`, `dto/`, `domain/` là
Python thuần. Đó là lý do 268 test chạy trong 30 mili giây không cần database.
`scripts/run_domain_tests.py` dựng lại một package chỉ gồm ba thư mục đó, nên vi
phạm là gãy ngay với ImportError.

**Chỉ dùng API của Odoo 14.0.** Không `odoo.Command` (15.0+), không `_()` nhiều
tham số (16.0+), không manifest key `assets` (15.0+). Với thư viện ngoài thì càng
phải cẩn thận: Odoo 14 ghim `XlsxWriter==1.1.2` từ 2018, và tôi đã một lần dùng
API chỉ có ở 3.0 vì máy phát triển cài bản mới hơn.

**`python3 scripts/check_repo.py` phải sạch trước khi giao.** 15 kiểm tra, mỗi
cái sinh ra từ một lỗi đã thật sự xảy ra và **không báo gì lúc xảy ra**.

---

## 3. Xác minh việc mình làm

```bash
python3 scripts/run_domain_tests.py    # 268 test, không cần Odoo, ~30ms
python3 scripts/check_repo.py          # 15 kiểm tra cấu trúc
scripts/update.sh TÊN_DATABASE         # cập nhật đủ 5 module
```

**Luôn dùng `scripts/update.sh`, đừng gõ tay danh sách module.** Dữ liệu ánh xạ
TT200 nằm trong `l10n_vn_reports` nhưng ghi vào trường khai trên model của
`vn_core`; update thiếu một module thì lỗi báo ở file XML chứ không báo ở chỗ
thật sự thiếu. Đã có guard chặn việc này trong tài liệu, nhưng script vẫn an toàn
hơn.

---

## 3b. Bạn KHÔNG chạy được Odoo — và điều đó quyết định cách làm việc

Đây là giới hạn quan trọng nhất, đọc kỹ.

Bạn chạy được `run_domain_tests.py` và `check_repo.py` vì cả hai là Python thuần.
Bạn **không** chạy được Odoo, không cài được module, không render được PDF, không
thấy được giao diện. Nghĩa là bạn **không tự xác minh được** phần lớn thứ mình
viết ra.

Nên quy trình bắt buộc là:

1. Bạn viết, chạy hai lệnh xác minh, rồi giao kèm **lệnh cập nhật cụ thể** và
   **nói rõ cần xem gì để biết đúng hay sai**.
2. Chủ dự án chạy trên máy họ và gửi lại lỗi hoặc ảnh màn hình.
3. Bạn sửa.

Vòng lặp đó không phải thủ tục. **Hai lỗi nặng nhất của dự án này đều lộ ra ở
bước 2, không phải bước 1**: cột tài khoản đối ứng in id thay vì mã, và
`Worksheet.ignore_errors` không tồn tại ở XlsxWriter 1.1.2. Lỗi thứ hai đặc biệt
đáng nhớ — tôi *đã* chạy thử và tuyên bố "workbook hợp lệ", nhưng trên phiên bản
thư viện mà máy đích không có.

Vì vậy:

* **Đừng nói "đã kiểm chứng" cho thứ chỉ chạy được ở môi trường của bạn.** Nói rõ
  đã kiểm được gì và chưa kiểm được gì.
* **Đừng giả vờ đã đối chiếu số liệu.** Việc kiểm chứng ở §7 cần database thật và
  một kế toán viên; bạn không có cả hai.
* **Luôn kèm lệnh cập nhật** cho mỗi lần giao, và nêu đúng một hai chỗ cần nhìn.

## 3c. Một thay đổi coi là xong khi

Bộ guard sẽ chặn nếu thiếu, nên làm đủ ngay từ đầu sẽ nhanh hơn:

* `run_domain_tests.py` và `check_repo.py` đều sạch;
* logic nghiệp vụ mới có test ở `vn_core/tests/` — và test đó phải **thật
  sự đỏ** nếu gỡ bản vá đi;
* chuỗi hiển thị mới đã dịch: chạy `scripts/regenerate_translations.py <module>`
  rồi điền phần còn trống, đừng sửa `.po` bằng tay;
* thêm báo cáo thì `README.md` phải liệt kê nó, thêm module thì mọi lệnh `-i`/`-u`
  trong tài liệu phải có nó;
* `CHANGELOG.md` ghi **lý do**, không chỉ ghi đã làm gì;
* lệch với thiết kế cũ thì ghi vào `docs/17`.

## 4. Thói quen làm nên codebase này

Nếu tiếp quản, giữ mấy điều sau — chúng không phải nghi thức, chúng đã bắt được
lỗi thật.

**Viết test chứng minh được là nó biết fail.** Có lần tôi viết test cho lỗi "cột
đối ứng in id thay vì mã tài khoản", nhưng fixture đánh số tài khoản 511 với id
cũng bằng 511 — test xanh mà chẳng chứng minh gì. Phải dựng lại fixture có id
khác mã, rồi **tạm gỡ bản vá** để xem test có đỏ không.

**Viết guard xong thì cố tình phá.** Guard không bao giờ báo lỗi là guard vô
dụng, nó chỉ tạo cảm giác an toàn giả.

**Guard báo sai thì sửa guard, đừng sửa code.** Đã xảy ra ba lần trong dự án
này. Một guard nhiễu làm người ta tắt cả bộ.

**Đừng đoán dữ liệu luật định.** Ánh xạ B01-DN có 72 chỉ tiêu; 12 chỉ tiêu ít
gặp **cố ý để trống** thay vì đoán. Bù lại, báo cáo tự liệt kê tài khoản có số dư
mà chưa chỉ tiêu nào nhặt. Ánh xạ sai trên báo cáo tài chính tệ hơn ánh xạ thiếu,
vì nó in ra bình thường và vẫn sai.

**Báo cáo nào tự kiểm được thì phải tự kiểm.** B01-DN kiểm 270 = 440. B03-DN kiểm
tiền cuối kỳ với số dư tiền thật. Tờ khai 01/GTGT kiểm thuế đầu ra với phát sinh
Có TK 3331 — chính cái này bắt được bút toán thuế ghi tay không lên bảng kê.

---

## 5. Những thứ cố ý KHÔNG có — đừng "sửa" chúng

| Thứ | Lý do | Xem |
| --- | ----- | --- |
| Tầng `ReportRenderer` đa hình | Odoo đã có `ir.actions.report` + QWeb. Hai renderer chưa đủ để trừu tượng hoá | §8.3 |
| `shared/` ngoài các module | Odoo chỉ nạp thứ trong `addons_path` | Part 16 |
| 16 package con của `vn_core` | Package rỗng làm cây thư mục trông có kiến trúc mà không có nội dung | §8.1 |
| Model riêng cho Phiếu thu/Chi | Phiếu quỹ *chính là* bút toán trên sổ tiền mặt | §6 |
| Nhân công, sản xuất chung trong giá thành | Odoo 14 CE không hạch toán chúng vào sổ. Cần **quyết định nghiệp vụ** trước | §6 |
| Drill-down trên B03-DN | Biểu thức chọn tài khoản *đối ứng*; mở Sổ Cái sẽ ra số khác | §4.8 |
| 12 chỉ tiêu B01-DN để trống | Không đoán dữ liệu luật định | §7 |

---

## 6. Bẫy đã biết

**Ánh xạ vượt ranh giới module.** 18 trường trong `tt200_*.xml` ghi vào model của
`vn_core`. Luôn update cả bốn module cùng lúc.

**QWeb bỏ qua `t-att-*` khi giá trị falsy.** `t-att-data-group="group_index"` với
`group_index=0` không sinh thuộc tính nào. Dùng `'g%s' % group_index`.

**File `.po` của Odoo khác gettext chuẩn** — cần `#. module: <tên>` ở mỗi entry.
Thiếu nó thì registry sập lúc đổi ngôn ngữ. Dùng
`scripts/regenerate_translations.py`, đừng sửa tay.

**Bản in và màn hình dùng bundle khác nhau.** wkhtmltopdf nạp
`web.report_assets_common`, không nạp `web.assets_backend`. SCSS phải đăng ký cả
hai.

**Nối code vào cuối file thì nó rơi vào class cuối cùng.** Đã xảy ra thật:
`default_for` đáng lẽ thuộc `vn.report.mapping` nhưng rơi vào
`vn.report.mapping.line`. Không lỗi lúc import, lúc cài, hay trong test nào —
chỉ nổ khi kế toán bấm nút. Guard `model-method` giờ chặn việc này; đừng sửa file
bằng cách nối chuỗi vào cuối, hãy chèn đúng chỗ.

**Tài khoản đối ứng nằm ngoài bộ lọc của báo cáo.** Sổ chi tiết công nợ lọc còn
TK 131 thì 511 và 3331 không có trong danh mục đã nạp. Engine phải tra riêng, nếu
không sẽ in id thay vì mã.

---

## 7. Việc tiếp theo

`docs/17` §7 có danh sách đầy đủ, chia hai nhóm. Tóm tắt:

**Xây thêm** — Sổ tài sản cố định (cần OCA `account_asset_management`), giá thành
đầy đủ (chặn ở quyết định nghiệp vụ), TT132, hiệu lực theo ngày cho ánh xạ,
thuyết minh B09-DN.

**Kiểm chứng — chưa bắt đầu, và đây mới là phần khó.** Chưa từng chạy trên hệ
thống tài khoản thật. **Chưa có kế toán viên nào đối chiếu một con số nào** với
bộ sổ lập tay. Chưa đo hiệu năng. Chưa kiểm đa công ty với quyền hạn thật.

Hai lỗi nặng nhất tìm được cho tới nay đều **không thể phát hiện bằng cách viết
thêm mã** — chúng lộ ra khi có người chạy thật. Nếu được chọn, đừng xây thêm báo
cáo: lấy một kỳ đã khoá sổ của khách hàng thật, chạy đủ B01/B02/B03 và bảng cân
đối phát sinh, rồi soi từng chênh lệch.

---

## 8. Câu hỏi nên hỏi chủ dự án

Có hai thứ bị chặn ở quyết định nghiệp vụ, không phải kỹ thuật:

1. **Chi phí nhân công và sản xuất chung lấy từ đâu** — bút toán thật (chính xác,
   khớp sổ, nhưng phải thêm quy trình phân bổ) hay số liệu thống kê từ workcenter
   (nhẹ hơn, nhưng không dùng để quyết toán được). Hai hướng cho hai con số giá
   thành khác nhau và kế toán phải bảo vệ được con số đó.
2. **Doanh nghiệp áp dụng thông tư nào** — TT200, TT133 hay TT132.
