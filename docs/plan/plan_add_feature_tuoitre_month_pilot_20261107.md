# Pilot Tuổi Trẻ tháng 01/2026

## Phase 0: Input Clarification

Người dùng đã approve đề xuất: xử lý nhãn con, chạy pilot 01/2026, kiểm tra dữ liệu và resume trước khi mở rộng.
Giữ branch feat/tuoitre-crawler, mẫu cũ và tốc độ tải tuần tự trong config.

## Phase 1: Requirements Analysis (EARS)

- R1: Khi category là nhãn con, dùng đường dẫn/breadcrumb JSON-LD chính thức để tìm nhóm cha. Nhánh /chung-khoan/ thuộc Kinh doanh theo liên kết nguồn; không gán Cần biết vào nhóm này.
- R2: Khi backfill, tìm cả sitemap báo chữ và sitemap Video, chỉ các kỳ giao với khoảng ngày đăng; không dùng lastmod làm published_at.
- R3: Khi lưu/resume dữ liệu lớn, chỉ giữ metadata kiểm tra và khóa dedup trong RAM; mỗi bài ghi CSV trước checkpoint.
- R4: Khi ngắt/chạy tiếp, dùng manifest cố định theo khoảng ngày và nhật ký kết quả từng URL, không tải lại bài đã lưu hoặc bỏ qua URL lỗi âm thầm.
- R5: Khi báo cáo pilot, ghi số bài theo ngày/category, ngày 0 bài, từng URL lỗi/ngoài phạm vi/chưa xử lý; không khẳng định đủ mọi bài trên website.
- R6: Khi kiểm tra resume thật, dừng theo giới hạn lượt thử trong config sau một đợt nhỏ, rồi chạy tiếp cùng manifest; CSV không trùng, báo cáo không mất lỗi cũ.

## Phase 2: Specification

| Cách làm | Ưu điểm | Hạn chế | Phức tạp | Truy cập | Chọn |
|---|---|---|---|---|---|
| CSV + JSONL checkpoint + metadata RAM | Giữ cấu trúc hiện tại, dễ đối chiếu | Một writer, URL metadata tăng theo corpus | Thấp | HTTP tuần tự theo robots | Có |
| Database và scheduler | Transaction/query thuận tiện | Vượt phạm vi crawl_plan | Cao | Không cần thêm | Không |

| Edge case | Trigger | Xử lý | Rủi ro |
|---|---|---|---|
| Nhãn con | Breadcrumb chỉ còn Chứng khoán | Map route đã xác minh trong config | Bỏ sót nhóm |
| Ranh giới tháng | Sitemap 26–31 có bài ngày 1 tháng sau | So kỳ sitemap có overlap config, lọc ngày đăng thật | Sai tháng |
| URL chuyển hướng | Slug thay đổi | Journal giữ requested/resolved, dedup theo bản đã lưu | Tải lại |
| URL lỗi | Parse/HTTP lỗi | Giữ kết quả cuối và lịch sử, retry khi resume theo config | Che giấu thiếu dữ liệu |
| Gián đoạn | KeyboardInterrupt hoặc giới hạn lượt thử | CSV đã ghi giữ nguyên, snapshot report/checkpoint | Mất tiến độ |
| Video ít text | Chỉ có sapo | Giữ text nguồn, không transcript | Dữ liệu giả |

| Exception | Nguồn | Xử lý | Recovery |
|---|---|---|---|
| 401/403/429/robots | HTTP | Dừng toàn bộ | Xem lý do trước chạy tiếp |
| Timeout/5xx | HTTP | Retry hữu hạn theo config | Ghi journal URL lỗi |
| Category ngoài scope | Cần biết/Thư giãn đã xác minh | Ghi excluded, không gọi là lỗi parser | Audit số loại |
| Ngày ngoài tháng | published_at thực tế | Ghi outside_range | Không ghi CSV |

Một writer dùng lock hiện tại. Report/manifest JSON ghi qua file tạm rồi replace; JSONL có thể bỏ dòng cuối dở dang khi khởi động lại, nhưng các dòng khác hỏng phải báo lỗi.

## Phase 3: Implementation Planning

1. Red/Green: hierarchy và phân biệt category ngoài scope. Verify: python -m pytest -q.
2. Red/Green: backfill news + Video và lựa chọn kỳ ở ranh giới tháng.
3. Red/Green: metadata RAM, checkpoint, report theo ngày, phân biệt lỗi/chưa xử lý; integration test ngắt/resume.
4. Config kế thừa cho 01/2026, output riêng. Chạy một đợt nhỏ có giới hạn trong config, xác minh rồi resume đến hết tháng.
5. Đối chiếu CSV/report/journal và mẫu bài. Chỉ đánh giá mở rộng sau khi pilot hoàn tất, không tuyên bố full năm đã đạt.

Files: crawl_tuoitre.py, config/tuoitre.json, config/tuoitre.january2026.json, tests/test_tuoitre_backfill.py, README.md, docs/tuoitre_january_pilot.md.
