# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows Semantic Versioning (Part 15 §21).

## [Unreleased]

### Added — Sổ chi tiết bán hàng (S35-DN)

- Doanh thu theo sản phẩm từ chính các dòng 511 (số lượng và sản phẩm giờ đi
  theo `MoveLineDTO`), khoản giảm trừ từ 521, và kết chuyển 511 → 911 cuối kỳ
  bị loại vì nó không phải doanh số. Dòng doanh thu không gắn sản phẩm được
  gom vào khối cuối thay vì bị giấu — sổ vẫn cộng ra đúng phát sinh TK 511.
- Cột thuế GTGT của mẫu giấy **không có**: thuế thuộc về hoá đơn chứ không
  thuộc về dòng 511, và Bảng kê 01/GTGT đã báo cáo nó từ chính các dòng thuế;
  chép về từng dòng doanh thu là bịa một phép phân bổ.
- Bảng tổng hợp N-X-T nhận mã **S11-DN**: mẫu "Bảng tổng hợp chi tiết vật
  liệu, dụng cụ, sản phẩm, hàng hóa" chính là tồn đầu / nhập / xuất / tồn cuối
  theo từng vật tư — báo cáo này, thêm cột số lượng.

### Added — Demo data cho Kho, Sản xuất và TSCĐ

- Mỗi module một generator riêng (`vn.demo.stock.generator`,
  `vn.demo.mrp.generator`, `vn.demo.asset.generator`), chạy lúc cài demo và
  gọi được từ `scripts/load_demo_data.py` cho database cài không demo. Kho và
  sản xuất dùng **định giá real-time** nối vào tài khoản Việt Nam nên cột TK
  đối ứng của S10-DN và bảng phân bổ 07-VT có số thật; sản xuất để lại một
  lệnh dở dang đã xuất vật tư cho cột dở dang của S37-DN; TSCĐ có một tài sản
  tăng giữa kỳ cho chỉ tiêu II của 06-TSCĐ.
- Khác generator sổ sách kế toán, ba generator này chạy **một lần** rồi tự
  báo đã nạp: phiếu kho done và khấu hao đã ghi sổ không unlink được, nên
  không có chế độ xoá-dựng-lại.
- Hoá đơn demo kế toán giờ gắn **sản phẩm** (loại consu, không cần module
  kho) để Sổ chi tiết bán hàng có dữ liệu ngay trên database demo.

### Added — Báo cáo TSCĐ: Sổ TSCĐ (S21-DN), Thẻ TSCĐ (S23-DN), Bảng phân bổ khấu hao (06-TSCĐ)

- Module mới `l10n_vn_asset_reports`, tách riêng theo Part 16 §4 vì cần một
  subledger tài sản mà Odoo 14 CE không có: dữ liệu đọc từ OCA
  `account_asset_management` (OCA/account-financial-tools 14.0, kéo theo
  `report_xlsx_helper` + `report_xlsx` từ OCA/reporting-engine). Bounded
  context mới vẫn vào bằng đúng một `_inherit` trên `vn.ledger.provider`.
- **Chỉ khấu hao đã ghi sổ được tính** — bút toán đã vào sổ, cộng các dòng số
  dư đầu (`init_entry`) mà subledger chủ đích không sinh bút toán. Kế hoạch
  khấu hao chưa ghi sổ chỉ vào báo cáo khi bật "Include planned depreciation":
  một quyển sổ trộn kế hoạch vào số đã ghi sẽ lệch với TK 214 mà không nói lý
  do. TK chi phí của từng dòng đọc từ **bút toán đã hạch toán** (bên Nợ), chỉ
  dòng chưa ghi sổ mới rơi về mặc định của profile.
- **S21-DN**: mỗi tài sản một dòng, nhóm theo profile, kèm tỷ lệ khấu hao năm
  (chỉ suy được cho phương pháp đường thẳng — tài sản giảm dần in trống thay
  vì in một con số vô nghĩa), luỹ kế, giá trị còn lại, ngày ghi giảm. Tài sản
  ghi giảm trong kỳ vẫn nằm trên trang; ghi giảm trước kỳ thì không. Cột "nước
  sản xuất" in trống có chủ đích — subledger không lưu dữ liệu đó.
- **S23-DN**: mỗi tài sản một thẻ, hao mòn cộng theo từng năm suốt đời tài sản
  (thẻ không bị `date_from` cắt — thẻ mở khi tài sản về và đi theo nó tới khi
  thanh lý).
- **06-TSCĐ**: bảng chéo nhóm TSCĐ × TK chi phí ghi Nợ, kèm khối tổng hợp
  I–IV. Cả bốn chỉ tiêu đo trực tiếp, không suy nhau, nên I + II − III ≠ IV là
  thông tin (tính lại bảng khấu hao, điều chỉnh giữa kỳ) chứ không phải lỗi bị
  giấu. "Kỳ trước" lùi theo **tháng lịch** khi kỳ chọn tròn tháng — lùi cơ học
  30 ngày sẽ nuốt bút toán 31/1 vào "tháng 2".

### Added — Bảng phân bổ nguyên liệu, vật liệu, công cụ, dụng cụ (07-VT)

- Bảng chéo một kỳ: cột là các TK ghi Có (mặc định 152, 153, 242 theo đúng mẫu),
  dòng là gốc TK ghi Nợ nhận giá trị, ô là số phân bổ giữa hai bên. Lập từ dòng
  ghi Có trên sổ, nên tổng mỗi cột đối chiếu được với phát sinh Có của chính tài
  khoản đó — và trên database định giá kho thủ công bảng này trống, vì trong sổ
  không có gì được phân bổ cả.
- Cùng luật với S36-DN: bút toán mà bên Nợ trải trên nhiều gốc TK nằm nguyên ở
  dòng "Khác", không chẻ tiền theo tỉ lệ tự bịa. Xuất dùng không bị bù trừ với
  nhập lại kho — mẫu báo cái đã xuất, còn nhập lại là một lần nhập.
- Cặp cột "giá hạch toán / giá thực tế" của mẫu gốc rút về một cột giá thực tế,
  vì Odoo không có khái niệm giá hạch toán; template nói rõ điều này.
- Đặt cạnh S36-DN trong menu Sổ chi tiết và dùng chung nhóm quyền với nó (như
  hai báo cáo tuổi nợ dùng chung một nhóm): cùng một người lập, cùng chỉ đọc
  sổ cái, không bắt ai cài `stock` hay `mrp`.

### Added — Sổ chi phí sản xuất, kinh doanh (S36-DN)

- Sổ chi tiết bên Nợ của các TK chi phí, mỗi tài khoản một trang, kèm các cột
  "chia ra" theo khoản mục. Khoản mục là **gốc TK đối ứng** (152 là NVL, 334
  nhân công, 214 khấu hao) — suy từ đúng cột "TK đối ứng" bên cạnh nên hai cột
  không thể mâu thuẫn; dòng có nhiều gốc đối ứng nằm nguyên trong cột "Khác"
  chứ không bị chẻ tiền theo phỏng đoán, vì counterpart calculator vốn không
  phân bổ số tiền. Bên Có in một dòng "Ghi Có TK" như mẫu quy định.
- Nằm ở `l10n_vn_reports`, menu Sổ chi tiết — không phải cạnh các báo cáo sản
  xuất. Mẫu này dùng cho cả 641, 642, 242, 335, và nó chỉ đọc sổ cái: bắt một
  công ty thương mại cài `mrp` để xem sổ chi phí quản lý là thêm phụ thuộc cho
  một báo cáo không cần nó (Part 16 §4).
- Mặc định wizard chọn đúng các tài khoản mẫu S36-DN tự kê: 154, 242, 335,
  621, 622, 623, 627, 631, 632, 641, 642 — theo tiền tố, nên tài khoản chi
  tiết (6421, 6422…) tự được gom.

### Added — Sổ chi tiết vật liệu (S10-DN) và Thẻ tính giá thành (S37-DN)

- **S10-DN** là bố cục thứ ba của wizard kho: cùng phép tính với Thẻ kho nhưng
  in đủ cột giá trị và **TK đối ứng**. Cột đối ứng đọc từ bút toán mà valuation
  layer đã sinh — tài khoản nằm phía bên kia của lớp giá trị — nên layer không
  có bút toán (kiểm kê định kỳ) in trống thay vì in bừa.
- **S37-DN** là bố cục thứ ba của wizard sản xuất: dở dang đầu kỳ, phát sinh
  trong kỳ, giá thành nhập kho, dở dang cuối kỳ — theo sản phẩm, chỉ NVL trực
  tiếp như lập trường đã ghi ở đầu engine. Bốn con số đo trực tiếp từ layer chứ
  không suy ra nhau, nên thẻ không tự cân: cột chênh lệch tồn tại để chỉ ra biến
  động giá định mức hoặc phát sinh ghi ngoài kỳ.
- Repository sản xuất trả lời được câu hỏi lịch sử "lệnh nào đang dở dang tại
  ngày X" (`get_productions_open_at`) — khác với `done=False`, một lệnh nay đã
  xong vẫn tính nếu hôm đó nó chưa xong — và `get_material_costs` nhận cận ngày
  để tách tiêu hao trước kỳ, trong kỳ và luỹ kế.
- Demo generator gán tài khoản phải thu/phải trả (131/331) cho partner demo khi
  chưa có: trên database chưa cài chart of accounts, dòng phải thu Odoo tự sinh
  cho hoá đơn sẽ không có tài khoản và vỡ constraint ngay lúc cài demo.

### Fixed — Báo cáo kho bỏ rơi phát sinh của chính ngày cuối kỳ

- `OdooInventoryRepository.get_movements` chặn trên bằng `<= 'YYYY-MM-DD'`,
  mà ngày của layer là timestamp: mọi phát sinh sau 00:00 của chính ngày
  `date_to` bị loại im lặng. Chạy báo cáo "đến hôm nay" là thấy — các phiếu
  nhập xuất trong ngày biến mất, không lỗi, không cảnh báo. Sửa thành
  `23:59:59` theo đúng quy ước repository sản xuất đã dùng.
- Lỗi lộ ra nhờ `scripts/smoke_test_reports.py` (mới): dựng tồn kho và một
  lệnh sản xuất *ngay hôm nay* rồi render từng bố cục — dữ liệu demo toàn
  ngày quá khứ nên không bao giờ chạm vào nhánh này.

### Fixed — Statement mapping resolution raised on every financial statement

- `default_for` had been appended to the end of its file, which put it inside
  `vn.report.mapping.line` rather than `vn.report.mapping`. Nothing failed at
  import, at install, or in any test: a model method is a runtime lookup, so it
  raised only when someone opened a balance sheet.
- A structural check now resolves every `self.env['x'].method()` call against
  the classes that actually declare the model, unioned across modules so a
  method contributed by another addon still counts.
- The first version of that check reported nothing, because it registered a
  model only when the model had at least one method — and the broken model had
  none, so it was silently treated as an Odoo core model. Fixed, then verified
  by putting the bug back and watching all three call sites light up. A check
  that passes over the bug it was written for is worse than no check.

### Added — Handoff notes

- `AGENTS.md`: what to read and in what order, the three rules that cannot be
  broken, the two commands that verify a change, and — most importantly — what
  was deliberately **not** built, so whoever takes over does not go and "fix" it.
- The design documents predate the code and several describe things that were
  rejected. Handing someone all seventeen of them is worse than handing them
  five: Part 7 alone would send a reader off building a renderer layer that was
  considered and refused.
- `AGENTS.md` also states the one limit that shapes everything else: an agent
  can run the domain tests and the structural checks, but cannot run Odoo. Most
  of what it writes it cannot verify itself, so each handover must name the
  update command and say what to look at. Both of this project's worst bugs
  surfaced in that loop, not in the writing.
- A structural check keeps the handoff file honest — it must still name every
  module and every verification command. A handoff file that has fallen behind
  is worse than none, because it is confidently wrong about the thing its reader
  has least ability to check.
- `docs/17` §7 rewritten: all three of its "next steps" had been done. It now
  separates work that can be estimated from verification work that cannot, and
  says plainly that the latter has not started.

### Added — Indirect cash flow, and TT133's third statement

- **B03-DNN for Thông tư 133**, indirect method. Closes the gap recorded when
  TT133 was added: a company on that circular had no cash flow form at all.
- **No new engine.** The indirect method starts from profit and adjusts it with
  balance movements, which is exactly what the Financial Statement Engine does.
  It only needed the period's opening and closing cash, delivered through the
  same pseudo-codes the direct engine already used — so one mapping convention
  now covers both methods.
- Which method a form uses is a property of the form, declared on the mapping.
  The service picks the engine from it rather than from the caller's guess.
- **The indirect statement checks itself against real cash.** An indirect cash
  flow is a chain of adjustments, and one wrong sign anywhere produces a total
  that still looks plausible; comparing item 70 with the actual closing balance
  is the only way to know. A test deliberately flips the sign on the receivables
  adjustment and asserts the check catches it, off by exactly twice the amount.
- The two methods fail differently, so the diagnostics are worded differently: a
  direct statement is short because a counterpart went unmapped, an indirect one
  because an adjustment carries the wrong sign. Saying the wrong one sends the
  accountant looking in the wrong place.
- Pseudo-codes now render as "Số dư tiền cuối kỳ" rather than
  `__closing_cash__`; machinery should not surface in a statutory report.

### Added — Thông tư 133

- Balance sheet (B01a-DNN) and income statement (B02-DNN) for Thông tư 133, the
  circular most Vietnamese SMEs actually report under.
- **Not one line of Python changed.** Same engine, same expression parser, same
  formula evaluator, same diagnostics — only mapping rows. This is the claim the
  mapping layer was built to make good on, and until now nothing had tested it.
- The forms genuinely differ rather than being renamed: 45 items against 72,
  total assets is item 200 not 270, and selling and administrative expenses
  merge into one item so accounts 641 and 642 land together. Tests assert each
  of those.
- Which circular applies is a property of the company, set on the company form.
  Putting it on the wizard would invite producing statements under a circular
  the company does not keep its books under.
- The two hard VAS rules survive the change: accounts 131 and 331 still split
  per partner on the TT133 form, and it still checks its own identity — 200 =
  500 where TT200 checks 270 = 440.

### Added — Cash vouchers

- **Phiếu thu (01-TT) and Phiếu chi (02-TT)**, printed straight from the journal
  entry. Vietnamese law requires a numbered, signed voucher for every cash
  movement and Odoo has no such document.
- **No new model.** A cash voucher *is* a journal entry on a cash journal;
  giving it a record of its own would mean two rows for one economic event and a
  lifetime of keeping them in step. `account.move` gains a voucher type and a
  voucher number instead.
- The type follows the direction of the cash, not the shape of the document: a
  refund to a customer sits on a sales-shaped entry and is still money leaving
  the till.
- Two sequences, one per voucher type. Sharing the journal entry name would
  interleave receipts and payments and leave both series with gaps — and a gap
  in a statutory voucher series is the first thing an inspector asks about.
  Numbers are assigned at posting, not in draft, for the same reason.
- **Sổ quỹ now prints the voucher number**, which is what S07-DN asks for. This
  closes a gap recorded when the cash book was first built.
- `vn_core` reads the voucher column only when the localisation that adds it is
  installed: the framework must install and run on its own, so the column is
  detected in the registry rather than assumed.

### Fixed — Printed reports had no styling at all

- The stylesheet was registered only in `web.assets_backend`, but wkhtmltopdf
  loads `web.report_assets_common`. Every PDF was therefore unstyled: no table
  borders, no header shading, and the filter summary running together into one
  line. Registered in both bundles, from one file — the screen and the print
  share a QWeb template, so splitting the styles would let the two drift.

### Fixed — Excel export raised on Odoo 14's pinned xlsxwriter

- `Worksheet.ignore_errors` arrived in XlsxWriter 3.0 and Odoo 14 pins 1.1.2, so
  clicking Export raised `AttributeError` on a stock install. The call is now
  feature-detected: without it the green "number stored as text" triangles come
  back, the figures do not change, and an export that works with a cosmetic
  blemish beats one that fails.
- The export had been verified by building a real workbook — but in a sandbox
  carrying XlsxWriter 3.2.9. Running it for real only proves something about the
  environment it ran in; for a third-party library the target's version is what
  decides.
- A structural check now holds the list of workbook and worksheet methods
  present in 1.1.2. Anything outside it must be feature-detected. The check
  resolves which variables actually hold a workbook rather than matching on
  names, after a first version flagged a plain dict called `sheet` — a guard
  that cries wolf gets switched off.

### Fixed — Counterpart accounts printed database ids

- A report that filters accounts — the partner ledger restricted to 131, the
  cash book restricted to 111 — loaded only those accounts, so the counterpart
  column could not name anything facing them and fell back to the raw database
  id: "78, 143" where the accountant expected "511, 3331".
- The engine now resolves the accounts actually referenced as counterparts,
  fetching only those and only when the column was asked for.
- The regression test uses ids deliberately unlike the codes. The previous
  fixture happened to number account 511 as id 511, which would have hidden the
  bug completely.

### Added — Excel from the report screen

- The viewer toolbar gained an Export Excel button beside Print PDF; until now
  the export existed only on the wizard.
- The workbook is built server-side from the same wizard, so it carries the same
  period and filters as the screen. Rebuilding it from the rendered table would
  give a file that agrees with the screen only until somebody collapses a group
  or types in the search box.
- Text columns are marked so Excel stops flagging account codes as "number
  stored as text". A code is text — 111 and 0111 are different accounts — and a
  green warning triangle against every row of a ledger teaches the reader to
  ignore warnings.
- A structural check rejects a toolbar button with no handler. Such a button
  renders, looks enabled, and does nothing when clicked, without raising or
  logging anything.

### Added — Excel export for every report

- Every report now exports to xlsx beside its PDF, with real dates, number
  formats following the reporting currency, frozen headers and autofilter.
- **Sixteen reports, seven layouts.** Layouts are named after the shape of the
  data rather than after the report, because the DTOs are shared: the ledger
  layout serves the general ledger, the journal, the partner ledger and the cash
  book, and the statement layout serves B01, B02, B03 and the VAT declaration. A
  new report usually names an existing layout and needs no export code.
- The workbook carries the same provenance as the printed header — company,
  period, applied filters. A spreadsheet outlives the screen it came from and
  gets mailed around; without that it is a grid nobody can check.
- The balance sheet's coverage diagnostic gets its own tab rather than a
  footnote: on paper it sits under the statement, in a workbook it is a list to
  work through.
- **No OCA `report_xlsx` dependency.** Odoo 14 already ships `xlsxwriter` for its
  own list-view export, so the workbook is built with nothing beyond the server.
- Part 7 proposed a renderer interface and Part 17 §8.3 recorded why it was not
  built. This is the second renderer and the answer is unchanged: a concrete
  writer, not a polymorphic layer. Nothing dispatches on renderer type.
- A structural check rejects a layout name no wizard can resolve. The name is a
  string, so a typo installs cleanly and fails only when somebody clicks Export.

### Added — VAT declaration

- `vn_core`: `VatDeclarationEngine` builds form 01/GTGT from the two VAT
  listings, filling the rate columns, the totals and the settlement.
- Unlike the financial statements this one is code rather than mapping data: its
  inputs are the rate buckets of the listings rather than accounts, and its
  arithmetic is fixed by law — item 27 is 29 + 30 + 32 for every taxpayer. Every
  relation the form prescribes is asserted in a test rather than trusted.
- Items 22, 37, 38 and 42 are wizard fields. Carried-forward credit comes from
  the previous period's own declaration, which this framework does not store,
  and the adjustments are decisions rather than derivations. Asking is more
  honest than defaulting them to zero and letting the form look complete.
- **The declaration reconciles against the ledger.** VAT posted by a hand-written
  journal entry produces no tax line, so no listing row and no indicator: the
  form looks complete and is short by exactly that amount. The engine compares
  item 28 against the period's credit movement on the output VAT account and
  reports the gap.

### Fixed — Translations were being lost on regeneration

- `regenerate_translations.py` read existing translations with a single-line
  regex, while gettext wraps long strings over several quoted lines and tools
  such as polib rewrap on save. Every regeneration therefore dropped exactly the
  longest entries, silently. Replaced with a wrap-aware parser, and nine lost
  translations restored.
- A structural check now refuses any empty translation. An untranslated entry
  raises nothing — Odoo falls back to English — so without a check the loss is
  invisible until a user notices.

### Added — Production cost

- `vn_core`: **Manufacturing Domain** — `ManufacturingCostEngine`, the sixth
  bounded context.
- New module **`l10n_vn_mrp_reports`**: production cost by product and by
  manufacturing order, plus work in progress at the reporting date.
- Cost and quantity both come from the valuation layers of the moves an order
  owns, so the figures agree with accounts 152 and 155. Taking the output
  quantity from `qty_produced` and the value from a layer would let a unit cost
  disagree with both of its own inputs.
- Variance is reported per order: zero under moving average or FIFO, where Odoo
  values the output at exactly the sum of the inputs, and non-zero under
  standard costing or after a landed cost.
- **Direct labour and production overhead are deliberately absent.** Odoo 14
  Community journalises neither — a workcenter's `costs_hour` is statistical and
  never reaches account 622 or 627, and there is no work-in-progress account.
  Printing a statistical figure beside a journalised one, with nothing on the
  page saying which is which, would be worse than printing less. The report
  states its own scope, and Part 17 §6 records the two ways to complete it.
- Work in progress is derived from materials issued to orders still open, for
  reconciling against the 154 balance, and says on the report that it exists
  nowhere in the ledger.

### Added — Drill-down from the financial statements

- An item on the Balance Sheet or the Income Statement opens the General Ledger
  of exactly the accounts behind it, over the same period and filters. From a
  ledger line the existing drill reaches the journal entry, and Odoo's own links
  carry on to the picking, the manufacturing order and the bill of materials.
- The engine resolves accounts per item transitively through formulas, so a
  total like item 100 — which is `110 + 120 + 130` and has no expression of its
  own — still knows what it is made of.
- Only items where the ledger adds back to the figure clicked are offered. The
  cash flow statement is deliberately excluded: its expressions select
  *counterpart* accounts, so their ledger would include movements unrelated to
  cash and the total would not match. A drill-down that does not reconcile is
  worse than none.
- The drill target is the ledger rather than a raw `account.move.line` list: the
  list answers which rows, but loses the opening balance, the running balance
  and the counterpart column.
- Only the item code crosses to the server. Which accounts make up an item is
  mapping data the server already holds, and putting a copy in the DOM would put
  it somewhere it can go stale.
- A structural check enforces that any template calling a shared table declares
  the variables that table reads. QWeb raises on an undefined name, so a caller
  that forgets one does not lose a feature quietly — the report fails to render.

### Fixed — Updating one module at a time broke the load

- The TT200 mapping data lives in `l10n_vn_reports` but writes to fields
  declared on `vn_core` models. Updating only the downstream module leaves the
  column missing and the load fails pointing at the XML file rather than at the
  module that was skipped.
- `scripts/update.sh` reads the module list from `addons/` and updates all of
  them, so nothing can be left out by hand.
- A structural check refuses any `-i` or `-u` command in the documentation that
  omits a module. The command people copy is the one written in the README, so a
  command written short there becomes a broken database elsewhere.

### Added — Provenance on printed reports

- Every report now prints the filters that produced it. A printed page that does
  not say which accounts it covers cannot be audited: it looks identical whether
  it is the whole ledger or three hand-picked accounts. Unrestricted dimensions
  print as "All", so the absence of a filter is stated rather than implied.
- Each wizard declares its own filter fields; the shared header just iterates,
  so a stock report lists products and a ledger lists accounts without either
  template knowing about the other.
- Printed reports carry "Trang X / Y" and who printed them, when.

### Changed — Print layout

- Print templates use `vn_print_layout` instead of `web.internal_layout`. The
  standard layout emits its own company header, which would sit above the
  statutory "Đơn vị / Mã số thuế / Mẫu số" block that TT200 prescribes and print
  the same information twice in two styles.

### Fixed — Collapsed groups survive a refresh

- Collapsed state was keyed by position ("g0", "g1"), so after a refresh over a
  different period group 0 was a different account and the state applied to the
  wrong rows. Group headers now carry a stable identity — account code, partner
  or product — and the state is keyed on that.

### Added — Cash Flow Statement

- `vn_core`: **Cash Flow Domain** — `CashFlowEngine` and an allocator, the
  fifth bounded context. Completes the B01/B02/B03 set.
- `l10n_vn_reports`: **Cash Flow Statement (B03-DN)**, direct method, 30 items
  shipped as data.
- Part 17 §4.3 recorded the multi-line allocation as an unsolved problem needing
  an arbitrary proportional rule. That was wrong: an entry balances, so in any
  entry touching cash the non-cash side **is** the cash flow, account by
  account, with the sign flipped. The parts always add back to the cash movement
  exactly. An internal transfer correctly produces no flow; a transfer carrying
  a bank charge produces exactly the charge.
- The mapping's `side` is read as cash direction rather than debit or credit
  balance, so account 341 feeds both "tiền thu từ đi vay" and "tiền trả nợ gốc".
- Opening and closing cash reach the mapping through the pseudo-codes
  `__opening_cash__` and `__closing_cash__`, so item 60 needs no extra field.
- The statement reconciles itself: item 70 must equal the closing balance of the
  cash accounts. Cash is the one figure in a financial statement verifiable
  against an independent source, and when it fails the difference is exactly
  what the unmapped counterpart accounts moved.

### Fixed — Report viewer

- On long statements a row scrolled into view above the sticky toolbar instead
  of under it. The scroll container carried top padding, and a sticky bar pins
  against the scrollport, so that padding was a strip rows passed through in
  plain sight. The spacing moved onto the toolbar, which now also bleeds across
  the side gutters so nothing shows beside it either.
- The toolbar sits at `z-index: 10` and everything below it is pinned into a
  stacking context at `0`, so no table style added later can paint over the bar.
- Its bottom border became an inset shadow: a border on a sticky element can
  leave a hairline that rows show through while scrolling.

### Changed — Menu labels carry the form number

- Statutory reports now show their form number in the menu, e.g. "Sổ Cái
  (S03b-DN)". Accountants look a report up by its number more readily than by
  its name.
- Only reports that genuinely carry a number get one. The aged balances are
  management reports, the VAT listings are an annex to form 01/GTGT, and the
  inventory summary has no number either — inventing one would be worse than
  leaving it out.
- The number lives in the wizard's `_report_form_code`, so repeating it on the
  menu creates a second copy that can drift. A structural check now verifies
  every number written on a menu against what the report behind it declares.
- `scripts/regenerate_translations.py` replaces the ad-hoc extraction used
  until now, and carries an existing translation across when a label gains a
  form number.

### Added — Inventory

- `vn_core`: **Inventory Domain** — `InventoryEngine`, `IInventoryRepository`
  and a running-stock calculator. The fourth bounded context.
- New module **`l10n_vn_stock_reports`**: Bảng tổng hợp Nhập - Xuất - Tồn and
  Thẻ kho (S12-DN). Split out because the repository needs `stock_account`, and
  a trading company running the accounting books should not be forced to
  install Inventory. First time Part 16 §4's test for splitting is met.
- The new module adds a whole bounded context by inheriting one AbstractModel,
  `vn.ledger.provider`, without a line changing in `vn_core` or
  `l10n_vn_reports`.
- Quantity and value both come from `stock.valuation.layer`, so the closing
  value agrees with accounts 152/155/156 by construction. Recomputing value from
  quantity times a current cost is what makes a stock report drift from the
  ledger.
- A valuation layer has no accounting date in Odoo 14, only `create_date`. The
  effective date is taken from the originating `stock.move` where there is one,
  so a backdated movement reports under the date an accountant expects.
- `StockCardGroupDTO.average_unit_cost` exposes the period-end weighted average
  beside Odoo's moving average, making the gap between bình quân cuối kỳ and
  what Odoo posted visible instead of a year-end surprise.

### Fixed — Interface language

- Menu section labels were Vietnamese in source while report names were English
  with a translation, so the menu came out half translated in either language.
  All source strings are now English, Vietnamese comes from `i18n/vi.po`, and a
  structural check refuses a non-ASCII menu or view label.

### Added — Demo invoices carrying VAT

- The demo generator now creates real customer and supplier invoices with taxes
  attached, so the VAT listings have something to show. Hand-written journal
  entries with a manual 3331 line look correct on the general ledger but carry
  no `tax_line_id`, and the listings read tax lines.
- Demo partners carry tax codes, which is what the Bảng kê prints.
- Invoices are dated from March onward so the documented opening balances of
  the ledger reports are unaffected.

### Added — Balance Sheet

- `l10n_vn_reports`: **Balance Sheet (B01-DN)**, 72 items with the full
  hierarchy and totalling formulas, shipped as data.
- Account expressions are filled in for the items a manufacturing SME actually
  uses; twelve uncommon items are left blank **on purpose** rather than guessed.
  A wrong statutory mapping is worse than an absent one.
- `vn_core`: the engine now reports what the mapping failed to cover — every
  account carrying a balance that no item picks up — and evaluates the form's
  own identity (`270=440`), showing the difference when it fails. A ninety-item
  mapping is impossible to complete blind; this turns an invisible error into a
  list of account codes.
- Accounts 131 and 331 each feed a receivable and a payable item, split per
  partner. This is what the `side` / `split_by_partner` fields were built for.
- The "Số đầu năm" column is the closing position on the day before the fiscal
  year began, not the same date a year earlier — the latter is meaningless for a
  company whose year does not follow the calendar.

### Added — VAT listings

- `vn_core`: **Tax Domain** — `TaxEngine`, `ITaxRepository` and a sign
  calculator. The third bounded context, and the first one that does not read
  the ledger through `ILedgerRepository`.
- Rows arrive from SQL already aggregated per `(invoice, tax rate)`. A Bảng kê
  lists one row per invoice, not per product line, so grouping twenty lines in
  Python only to collapse them would be wasted work.
- Sign normalisation is by direction, not by account code: output VAT is a
  credit on 3331 and input VAT a debit on 133, and both must print positive. A
  credit note then comes out negative with no special case, which is what the
  filing expects.
- `l10n_vn_reports`: **VAT Sales Listing** and **VAT Purchase Listing**, grouped
  by rate, with partner tax codes and a distinct treatment for credit notes.
- The statutory invoice number is read from `ref` with a fallback to the move
  name, and the column is overridable — e-invoice providers do not agree on
  where they store it.

### Added — Financial statements

- `vn_core`: **Financial Statement Domain** — `FinancialStatementEngine`,
  `IMappingRepository`, an account-expression parser (`111*`, `111*,-1113`) and
  a formula evaluator over item codes (`10 - 11`).
- The formula evaluator uses a hand-written parser rather than `eval`: a mapping
  is data edited by accountants through the UI and must never execute code. It
  detects cycles and names them instead of exhausting the stack.
- `vn.report.mapping` / `vn.report.mapping.line` with an editing UI under
  Accounting → Configuration. No account code appears in Python.
- Mapping lines carry `side` and `split_by_partner`, which Part 5 and Part 9
  both omitted. Without them a Vietnamese balance sheet cannot be produced:
  account 131 splits into a receivable and a customer prepayment, computed per
  partner before summing. See Part 17 §3.
- `l10n_vn_reports`: **Income Statement (B02-DN)**, 20 statutory items shipped
  as data, with a prior-year comparative column.

### Added — Aged balances

- `vn_core`: `LedgerEngine.compute_aging` plus an aging calculator with
  configurable buckets, and `AgedReceivableService` / `AgedPayableService`.
- Aging reconstructs the residual **as at the reporting date**: every partial
  reconciliation dated after it is added back, so an invoice collected in July
  still shows as outstanding on a June report.
- `l10n_vn_reports`: Aged Receivable and Aged Payable, aged from either the due
  date or the document date.

### Added — Books

- `l10n_vn_reports`: General Journal (S03a-DN), Partner Ledger (S31-DN), Cash
  Book (S07-DN) and Bank Book (S08-DN). Cash and partner accounts are resolved
  by code prefix and account type, never by hardcoded ids.
- `vn_core`: `LedgerLineDTO` now carries `account_code` / `account_name`,
  resolved by the Engine at no extra query. Sổ Nhật ký chung is ungrouped, so a
  line cannot read its account off a group header.
- `vn_core`: `LedgerEngine.compute_balances` — aggregates with no detail lines,
  which is what a financial statement consumes.

### Added — Foundations

- `vn_core`: Ledger Domain — `LedgerEngine`, `ILedgerRepository`, and
  calculators for opening balance, running balance, closing balance, one-sided
  presentation and counterpart detection.
- Opening balances are fiscal-year aware: balance-sheet accounts accumulate from
  inception, P&L accounts reset at the year start. The rule lives in a
  calculator, and costs two queries rather than one per account.
- `OdooLedgerRepository` — the single place in the ledger stack touching ORM or
  SQL, with record rules enforced via `_where_calc` + `_apply_ir_rules`.
- `vn.ledger.provider` extension point, resolved per database rather than
  through an import-time Python registry (Part 17 §4.1).
- Composite indexes on `account_move_line`.
- `l10n_vn_reports`: General Ledger (S03b-DN), Trial Balance, per-report
  security groups, Vietnamese translations, and an interactive viewer sharing
  one QWeb template with the PDF.
- Demo data generator: 22 entries across two fiscal years, reachable from both
  the `demo/` hook and `scripts/load_demo_data.py`.
- 220 Domain unit tests running without Odoo or PostgreSQL.

### Fixed

- QWeb drops a `t-att-*` whose value is falsy, so the first group of every
  report (index 0) rendered no `data-group` attribute and refused to collapse.
  Group keys are now strings. Guard added.
- The closing-balance row carried no `data-group-child`, so it stayed visible
  when a group was collapsed.
- `i18n/vi.po` was valid gettext but not valid Odoo: without a `#. module:`
  marker per entry the registry fails to load. Regenerated from source with
  full references. A translation without a `model:ir.ui.menu` reference leaves
  the menu silently in English.
- Removed three APIs that do not exist in Odoo 14: `odoo.Command` (15.0+),
  multi-argument `_()` (16.0+), and `tools.create_index` re-export.

### Known limitations

- `get_move_lines` materialises the full result set; not yet safe for the
  "millions of journal items" target. Blocks streaming XLSX export.
- Counterpart detection returns every account on the opposite side of a
  multi-line entry with no amount allocation. The direct-method cash flow
  statement needs an explicit allocation rule (Part 17 §4.3).
- Balance Sheet B01-DN ships with twelve items unmapped; the report lists
  which accounts they should cover.
- Cash Book lacks separate Phiếu thu / Phiếu chi numbering required by S07-DN.
- No XLSX export, no Costing domain.
- VAT listings cover the annex; form 01/GTGT itself is not summarised yet.
