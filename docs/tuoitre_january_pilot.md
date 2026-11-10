# Pilot Tuổi Trẻ tháng 01/2026

> Cập nhật 18:55 ngày 07/11/2026: người dùng yêu cầu tiếp tục theo từng tháng. Tiến trình
> pilot cũ đã dừng; hàng đợi mới đang resume cùng CSV/checkpoint tháng 1 rồi chuyển các tháng tiếp theo.
> Xem [hướng dẫn hiện tại](tuoitre_monthly_crawl.md). Phần dưới là snapshot của lượt chạy ban đầu.

Người dùng đã duyệt chuẩn bị và chạy pilot trước khi mở rộng cả năm.
Branch `feat/tuoitre-crawler`, config `config/tuoitre.january2026.json`.

## Phạm vi và trạng thái bàn giao ngày 07/11/2026

Pilot từ 01/01/2026 đến 31/01/2026 đã chạy nền lúc 10:03 theo giờ Việt Nam.
Chưa có kết quả đánh giá cuối tháng tại thời điểm bàn giao. Không chạy các tháng khác.
Trạng thái mới nhất nằm trong report JSON, không suy ra tiến độ hiện tại từ số liệu snapshot bên dưới.

Manifest gồm **8.674 URL ứng viên**, từ sitemap bài viết và Video. Có kỳ cuối tháng 12
để xét bài qua ranh giới đầu năm; ngày đăng thực tế mới quyết định có lưu vào CSV tháng 1 hay không.
Đây không phải cam kết sẽ có 8.674 bài hợp lệ tháng 1.

Khoảng nghỉ HTTP mặc định là 2 giây giữa các lần bắt đầu request. Riêng khoảng nghỉ cho
8.674 URL đã tương đương khoảng 4 giờ 50 phút, chưa tính phản hồi/retry. Máy cần tiếp tục
hoạt động và có mạng; nếu quá trình dừng, xem status/log và resume cùng config sau khi xác nhận
không có writer còn chạy.

## Những phần đã xác minh

- 25 tests PASS (`python -m pytest -q`).
- “Tin tức thị trường” trong nhánh `/chung-khoan/` được nhận diện Kinh doanh qua breadcrumb JSON-LD.
- Cần biết, Thư giãn và Thời tiết được ghi `excluded` theo config, không gán vào 18 nhóm.
- Đã đọc sitemap Video theo kỳ và parse thật một Video ngày 06/01/2026 (233 ký tự mô tả nguồn).
- CSV giữ đầy đủ text; RAM backfill chỉ giữ metadata/cờ chất lượng. Test với text 1,3 MB xác nhận không giữ body trong RAM và đọc lại đầy đủ CSV.
- Retry hữu hạn cả response bị cắt giữa chừng; không retry vòng lặp vô hạn.

## Kiểm tra resume thật

Chạy hai đợt giới hạn 20 lượt mỗi đợt trước khi bỏ giới hạn:

1. Đợt đầu: `checkpointed`, 8 bài được lưu, 11 URL ngoài khoảng ngày và 1 category cần xem lại.
2. Xác minh category đó là Thời tiết ngoài scope và cập nhật config theo nguồn.
3. Đợt tiếp: manifest SHA-256 không đổi, không request lại 8 URL đã lưu, không trùng URL/ID,
   bài cũ còn nguyên, lại dừng đúng checkpoint. Có 39 URL duy nhất đã có kết quả cuối
   (8 saved, 3 excluded, 27 outside_range, 1 lỗi mạng chờ retry).
4. Bỏ giới hạn trong config và resume nền. Lỗi mạng cũ đã được retry thành công ở đợt nền,
   được xác định ngoài khoảng ngày; lịch sử lỗi vẫn giữ trong JSONL.

Bằng chứng máy đọc được: `data/tuoitre/pilot_2026-01/resume_validation.json`.
Không dùng kết quả 8 bài đầu để kết luận chất lượng toàn tháng đã đạt.

## Theo dõi và artifacts

- CSV đang ghi: `data/tuoitre/pilot_2026-01/tuoitre_2026-01.csv`.
- Report đang cập nhật: `backfill_report.json` cùng thư mục.
- Manifest: `backfill_urls.json`; kết quả từng URL: `backfill_results.jsonl`.
- Log lỗi lịch sử: `backfill_errors.jsonl`; stdout/stderr: `crawl_stdout.log`, `crawl_stderr.log`.
- PID và lệnh/config: `process.json`. PID chỉ dùng để kiểm tra tiến trình đang tồn tại, không chứng minh crawl thành công.

```powershell
$pilotReport = Get-Content -Raw -Encoding UTF8 data/tuoitre/pilot_2026-01/backfill_report.json | ConvertFrom-Json
$pilotReport | Select-Object status, discovered, total_valid, pending_count, result_counts, updated_at
```

Report checkpoint sau mỗi 10 lượt. `attempted`/`saved` là số của lượt hiện tại;
`result_counts` là kết quả cuối tích lũy của các URL trong manifest; `pending_count`
là số URL chưa có kết quả. Lỗi cũ không bị mất khi chạy lại: xem `unresolved_errors`.

## Đánh giá sau khi đợt tháng kết thúc

Chỉ đánh giá mở rộng khi không còn pending hoặc process đang chạy. Nếu status là
`finished_with_errors`, xem và xử lý `unresolved_errors` trước khi kết luận. Kiểm tra:

1. CSV đúng schema, ngày đăng thuộc tháng 1, timezone +07:00, không thiếu field hoặc URL/ID trùng.
2. Tổng URL manifest khớp các kết quả saved/excluded/outside_range/error và không còn URL chưa xử lý.
3. Thống kê theo ngày/nhóm, xem riêng ngày 0 bài và nhóm chưa có bài; đối chiếu nguồn để phân biệt thiếu crawl với không có dữ liệu.
4. Xem mẫu bài cũ thuộc nhiều chuyên mục, cả Video, và các layout lỗi; không coi log sạch là bằng chứng đủ website.

Sau pilot có thể cân nhắc tách storage/report khỏi file crawler để dễ bảo trì; chưa thực hiện refactor riêng.
