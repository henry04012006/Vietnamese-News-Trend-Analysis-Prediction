# Tăng tốc crawl Tuổi Trẻ — 07/11/2026

Đã áp dụng vào hàng đợi đang chạy: `http.delay_seconds = 1`, cache ngày đăng giữa các tháng.
Giữ một writer, robots/crawl-delay, retry giới hạn và dừng khi HTTP 401/403/429.

## Đo tốc độ thật

| Chỉ số | Trước | Sau |
|---|---:|---:|
| Khoảng cách tối thiểu giữa request | 2 giây | 1 giây |
| Lượt URL dùng để đo | 683 | 100 |
| Thời gian lượt đo | 1.372,52 giây | 101,72 giây |
| Tốc độ xử lý URL | 1.791/giờ | 3.539/giờ |

Tăng **1,98 lần** trong hai cửa sổ đo này. Đây là tốc độ URL, không phải số bài hợp lệ/giờ;
network, redirect, retry và loại bài vẫn ảnh hưởng tốc độ ở những giai đoạn khác.

Đợt thử mới lưu 98 bài, 1 URL ngoài nhóm và 1 lỗi category được giữ trong log. Không gặp
HTTP chặn. Không đổi IP/UA hoặc bỏ qua giới hạn truy cập để đạt số đo.

## Bảo toàn dữ liệu và triển khai

1. Gửi Ctrl+C vào console riêng của crawler, sau khi kiểm tra console chỉ có worker và helper.
2. Worker ghi checkpoint, cả core và hàng đợi đều có status `interrupted`; không kill cưỡng bức hoặc gỡ lock khi process đang ghi.
3. Audit trước thử: 703 bài, URL/ID duy nhất, đủ required fields.
4. Benchmark 100 lượt qua config kế thừa; sau thử có 801 bài.
5. SHA-256 của phần CSV đã tồn tại (3.195.070 byte) và manifest giữ nguyên; số hàng tăng đúng 98.
6. Resume hàng đợi nền với config chung đã cập nhật. Config snapshot của tháng được ghi lại khi resume.

Bằng chứng: `data/tuoitre/monthly/speed_validation.json` có baseline, số đo mới và 8 checks PASS.
33 tests PASS, gồm pacing 1 giây, ưu tiên crawl-delay dài hơn, cache ngoài ngày,
vẫn fetch nội dung trong ngày, bỏ metadata mâu thuẫn/naive và không sửa journal nguồn.

## Cache giữa tháng

`date_cache.journal_globs` chỉ đến journal các tháng đã crawl. Chỉ tin các kết quả
`saved`/`outside_range` có `published_at` đầy đủ timezone; loại cache của journal hiện tại.
Nếu URL có hai ngày mâu thuẫn, không dùng nó để loại bài. Không suy đoán ngày từ URL hoặc lastmod.

Nếu ngày đã biết nằm ngoài tháng cần lấy, ghi kết quả `outside_range` với lý do chứa journal
nguồn và tăng `date_cache_skips`, không gửi HTTP request. Nếu ngày nằm trong tháng cần lấy,
vẫn gửi request để lấy body; không tạo bài từ metadata.

Lượt benchmark tháng 1 chưa có journal tháng khác để đo lợi ích cache ngoài thực tế.
Hiệu quả giảm request giữa các tháng sẽ theo dõi qua `date_cache_skips`; hiện đã xác minh
hành vi và bảo toàn dữ liệu bằng tests. Không cộng lợi ích cache chưa đo vào hệ số 1,98 lần.

## Theo dõi

Xem [hướng dẫn hàng đợi theo tháng](tuoitre_monthly_crawl.md). Trạng thái hiện tại là trong
`data/tuoitre/monthly/monthly_status.json`; số bài/tiến độ trong tháng xem `backfill_report.json`
của tháng đang chạy. Toàn bộ collection chưa hoàn tất tại thời điểm bàn giao tối ưu này.
