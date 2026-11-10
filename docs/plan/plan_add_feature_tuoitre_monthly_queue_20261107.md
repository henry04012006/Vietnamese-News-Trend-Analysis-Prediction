# Tiếp tục Tuổi Trẻ theo từng tháng

## Phase 0: Input Clarification

Yêu cầu mới: tiếp tục crawl và lưu dữ liệu theo tháng. Phạm vi từ 01/01/2026 đến ngày chạy;
giữ 18 chuyên mục và chính sách HTTP hiện tại. Tiếp tục dữ liệu tháng 1 đã có trước khi sang tháng 2.
Tiến trình cũ không tồn tại; report cuối 10:53, CSV thực tế 62 bài và journal 1516 URL.

## Phase 1: Requirements Analysis (EARS)

- R1: Khi lập hàng đợi, chia khoảng ngày thành các tháng lịch, tháng cuối kết thúc ngày chạy.
- R2: Khi chạy tháng 1, dùng thư mục pilot hiện có và checkpoint để không mất/tải lại bài đã lưu.
- R3: Khi hết một tháng, chuyển tuần tự sang tháng sau, mỗi tháng có CSV/report/journal/config riêng.
- R4: Khi có lỗi từng bài, giữ warning và URL lỗi; có thể tiếp tục tháng sau theo config. Khi bị chặn hoặc dừng toàn lượt, dừng hàng đợi.
- R5: Khi chạy lại hàng đợi, dùng khoảng ngày đã đóng băng và bỏ qua tháng đã xong; không có hai writer cùng hàng đợi.

## Phase 2: Specification

| Cách làm | Ưu điểm | Hạn chế | Phức tạp | Truy cập | Chọn |
|---|---|---|---|---|---|
| Python gọi crawler tuần tự | Tái sử dụng checkpoint, ít code | Máy phải hoạt động liên tục | Thấp | Giữ HTTP hiện có | Có |
| Scheduler hệ thống/database | Tự khởi động sau reboot | Vượt nhu cầu hiện tại | Cao | Thêm cấu hình hệ thống | Không |

| Edge case | Điều kiện | Hành vi | Rủi ro |
|---|---|---|---|
| Tháng 1 đã có dữ liệu | Override thư mục theo config | Resume pilot cũ | Crawl lại/mất bài |
| Chạy lại ngày khác | Hàng đợi đã tạo | Giữ kế hoạch ngày đã đóng băng | Manifest sai khoảng |
| Lỗi bài | finished_with_errors | Ghi warning, tiếp tục nếu policy cho phép | Che giấu thiếu dữ liệu |
| Lỗi chặn | stopped | Dừng toàn hàng đợi | Tiếp tục bị chặn |
| Gián đoạn đột ngột | Khóa còn, PID không còn | Chỉ gỡ sau xác minh không có writer | Ghi đè đồng thời |

| Exception | Nguồn | Xử lý | Phục hồi |
|---|---|---|---|
| Lock tồn tại | Filesystem | Không chạy writer thứ hai | Xác minh trước gỡ khóa |
| Core dừng/lỗi | Crawler | Persist monthly status, dừng | Resume cùng hàng đợi |

Config chứa root/template thư mục, tên status/lock/config snapshot, override tháng cũ và policy lỗi.
Một monthly lock và core lock mỗi tháng; không tự gỡ khóa dựa riêng timestamp.

## Phase 3: Implementation Planning

1. Tests Red/Green cho chia tháng, resume, freeze range, warning và stop.
2. Tạo crawl_tuoitre_monthly.py gọi core hiện có; không refactor core.
3. Audit dữ liệu cũ, xác nhận không có process, gỡ riêng khóa cũ; chạy queue nền.
4. Xác minh dữ liệu tăng từ 62, không trùng; cập nhật README và hướng dẫn theo dõi.

Files: crawl_tuoitre_monthly.py, config/tuoitre.json, tests/test_tuoitre_monthly.py, README.md, docs/tuoitre_monthly_crawl.md.
