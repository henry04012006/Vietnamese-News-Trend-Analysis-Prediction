# Crawl Tuổi Trẻ theo tháng

> Cập nhật 20:30 ngày 07/11/2026: đã benchmark và resume với 3 worker, khoảng cách
> chung 0,25 giây giữa lượt bắt đầu request. Đo 9.657 URL/giờ, nhanh hơn mức tuần tự
> 1 giây 2,75 lần; xem [báo cáo mới](tuoitre_rapid_speed.md).

Phạm vi hàng đợi hiện tại: **01/01/2026–07/11/2026**, 11 tháng, chạy tuần tự.
Tháng cuối chỉ lấy đến ngày 07/11. Kế hoạch được đóng băng trong status để khi resume
vào ngày khác không làm thay đổi manifest của tháng đã chạy.

## Trạng thái khởi chạy ngày 07/11/2026

Tiến trình cũ không còn tồn tại khi kiểm tra lúc 18:48; stderr trống nên chưa biết
nguyên nhân dừng. CSV tháng 1 có 62 bản ghi hợp lệ, journal có 1.516 URL đã có kết quả.
Đã xác minh không còn process crawl trước khi gỡ khóa runtime stale.

Hàng đợi mới chạy nền lúc 18:55, resume từ dữ liệu cũ, không tải lại bài đã lưu.
Đã quan sát CSV tăng từ 62 lên 70 bài; report ghi 0 URL/ID trùng và không thiếu required fields
trong các kiểm tra trước khởi chạy. Số liệu này là snapshot, xem report mới nhất để biết hiện tại.
29 tests PASS, bao gồm chia tháng, warning/stop, resume, freeze range và ngăn writer thứ hai.

## File dữ liệu

Tháng 1 giữ vị trí cũ để tiếp tục checkpoint:

```text
data/tuoitre/pilot_2026-01/tuoitre_2026-01.csv
```

Các tháng tiếp theo được tạo khi đến lượt:

```text
data/tuoitre/monthly/2026-02/tuoitre_2026-02.csv
data/tuoitre/monthly/2026-03/tuoitre_2026-03.csv
...
data/tuoitre/monthly/2026-11/tuoitre_2026-11.csv
```

Mỗi thư mục tháng có `crawl_config.json`, `backfill_urls.json`, `backfill_results.jsonl`,
`backfill_report.json`, `backfill_errors.jsonl`. Ngày đăng thực tế quyết định tháng CSV;
không deduplicate theo nội dung giữa các bài khác URL.

## Chạy và theo dõi

```powershell
python crawl_tuoitre_monthly.py --config config/tuoitre.fast.json
```

Hàng đợi hiện đã chạy, chỉ dùng lệnh trên để resume sau khi xác nhận tiến trình trước không còn chạy.
Không chạy đồng thời với core crawler ghi cùng tháng. Máy phải tiếp tục hoạt động và có mạng;
script không tự khởi động sau reboot hoặc khôi phục một tiến trình bị hệ điều hành dừng.

Status hàng đợi: `data/tuoitre/monthly/monthly_status.json`.
PID của tiến trình: `data/tuoitre/monthly/process.json`.
Stdout/stderr: `data/tuoitre/monthly/crawl_stdout.log`, `crawl_stderr.log`.

```powershell
$monthlyState = Get-Content -Raw -Encoding UTF8 data/tuoitre/monthly/monthly_status.json | ConvertFrom-Json
$monthlyState | Select-Object status, active_month, start_date, end_date
$monthlyState.months | Select-Object month, status, total_valid, unresolved_count, report
```

Status hàng đợi cập nhật khi bắt đầu/kết thúc một tháng; **tiến độ trong tháng** cập nhật
trong `backfill_report.json` của tháng đó sau mỗi 10 lượt thử. Trường `report` trong job
trỏ đến file tương ứng. PID/report cũ có thể stale sau gián đoạn; kiểm tra process thực tế.

## Config và lỗi

Phần `monthly` trong config quy định thư mục gốc/template, override thư mục tháng 1,
tên status/lock/config snapshot, các field summary và policy lỗi.

`tuoitre.fast.json` kế thừa config gốc, đặt `http.workers=3`, `prefetch=6`,
`delay_seconds=0.25`. Các tháng vẫn chạy lần lượt; trong mỗi tháng chỉ tải HTTP song song,
parse/CSV/journal/report dùng một luồng. Tổng mức bắt đầu request tối đa 4/giây,
bao gồm retry/redirect; crawl-delay lớn hơn từ robots được ưu tiên. Mọi worker dừng
nhận việc mới khi một worker gặp access denial, kể cả response in-flight khi đóng pool.
Config gốc vẫn giữ một worker và delay 1 giây.

- `finished`: hết manifest tháng, không còn URL lỗi.
- `finished_with_errors`: hết manifest nhưng vẫn còn URL lỗi; giữ warning và URL đầy đủ.
- `continue_on_article_errors: true`: tháng có lỗi từng bài vẫn được ghi warning và chuyển tháng sau.
- `stopped` (bao gồm HTTP 401/403/429 hoặc robots từ chối): dừng toàn hàng đợi, không tự vượt chặn.
- `checkpointed`/`interrupted`: dừng hàng đợi tại tháng hiện tại để resume cùng dữ liệu.

Khi resume, tháng đã `finished`/`finished_with_errors` được giữ nguyên; chỉ tiếp tục các tháng
chưa xong. Muốn retry URL lỗi của một tháng đã kết thúc, dùng core với `crawl_config.json`
của tháng đó khi không có writer đang chạy, sau đó đối chiếu lại summary hàng đợi.

Khóa `.monthly.lock` và `.crawl.lock` không tự gỡ dựa trên tuổi file. Sau gián đoạn đột ngột,
chỉ gỡ khi xác minh process đã kết thúc. Không ghi đè dataset đã chốt phiên bản.

Đủ manifest không chứng minh đủ mọi bài trên website. Vẫn cần đánh giá ngày/nhóm 0 bài,
các URL lỗi, scope category và chất lượng text sau từng tháng.
