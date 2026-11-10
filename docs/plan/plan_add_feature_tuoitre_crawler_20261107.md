# Tuổi Trẻ — Kế hoạch triển khai crawler

## Phase 0: Input Clarification

Yêu cầu: branch riêng, crawl mẫu theo crawl_plan.md, xác minh trước khi mở rộng.
Python CLI, requests + BeautifulSoup; không thay đổi notebook/dữ liệu lịch sử.
Thông số mạng, selectors, schema, tên file, khoảng thời gian và tiêu chí mẫu đặt trong config JSON.
Phạm vi: crawl_tuoitre.py, config/tuoitre.json, tests/test_tuoitre.py, requirements-crawl.txt, .gitignore và hướng dẫn README.

## Phase 1: Requirements Analysis (EARS)

- R1: Khi parse bài, phải xuất đủ schema, đúng ngày đăng +07:00, giữ đoạn và dấu tiếng Việt; không dùng ngày sửa.
- R2: Khi URL có fragment/tracking, phải bỏ thành phần tracking đã xác định, giữ query có ý nghĩa và tạo SHA-256(source|url).
- R3: Khi chạy mẫu, chọn 20 bài mới và 10 bài cũ từ sitemap chính thức; tối thiểu 27/30 hợp lệ, không ID/URL trùng; đối chiếu 5 bài cũ/mới.
- R4: Khi chạy backfill, chia CSV theo tháng, lưu sau mỗi bài, bỏ qua URL đã lưu, báo lỗi và độ phủ thực tế.
- R5: Khi bị chặn, robots từ chối hoặc rate limit, ghi lỗi và dừng; timeout/5xx retry giới hạn, tải tuần tự có nghỉ.

## Phase 2: Specification

Luồng: robots → sitemap index → sitemap theo kỳ → URL → HTML → parser → CSV + JSONL lỗi + báo cáo JSON.

| Cách làm | Ưu điểm | Hạn chế | Độ phức tạp | Truy cập | Chọn |
|---|---|---|---|---|---|
| Sitemap + requests | URL lịch sử công khai, dễ resume | HTML có thể đổi | Thấp | Theo robots | Có |
| Browser cho toàn bộ bài | Render JavaScript | Chậm, tốn tài nguyên | Cao | Cùng quy tắc | Không |

| Edge case | Điều kiện | Hành vi | Rủi ro nếu bỏ qua |
|---|---|---|---|
| Thiếu ngày/text | Không có field bắt buộc | Ghi lỗi, không xuất bài giả | Sai dữ liệu |
| Thiếu offset | Ngày đăng không timezone | Từ chối, ghi lỗi | Lệch ngày |
| Bài khác năm | Ngày thực ngoài khoảng | Ghi nhận loại khỏi phạm vi | Sai corpus |
| Nội dung ngắn | Dưới ngưỡng config | Gắn cờ, vẫn giữ | Mất bài hợp lệ |
| Chạy lại | URL/ID đã lưu | Bỏ qua | Crawl trùng |

| Exception | Nguồn | Xử lý | Phục hồi |
|---|---|---|---|
| Timeout/5xx | HTTP | Retry giới hạn | Chạy lại URL lỗi |
| 403/429 | HTTP | Dừng, ghi lỗi | Kiểm tra quyền/tần suất trước chạy lại |
| HTML/schema lỗi | Parser | Ghi URL và lý do | Xem mẫu, sửa parser |

Không chạy đồng thời hai writer trên cùng thư mục; khóa độc quyền cho mỗi lượt chạy.
CSV UTF-8, dữ liệu và HTML mẫu nằm trong data/ được Git bỏ qua. Không commit/push tự động.

## Phase 3: Implementation Planning

1. Parser: tests Red cho hợp đồng extraction → code Green → không refactor nếu không cần. Verify: python -m pytest -q.
2. Crawl/resume: tests giả lập HTTP/CSV cho dedup và lỗi → code Green. Verify: python -m pytest -q.
3. Chạy sample thật; kiểm tra 30 URL và đối chiếu 5 HTML gốc. Verify: python crawl_tuoitre.py sample --config config/tuoitre.json.
4. Review code, cập nhật README với lệnh sample/backfill, giới hạn độ phủ. Chỉ chạy full sau khi mẫu đạt và giải quyết lựa chọn xem mẫu của người dùng.

Mục tiêu full: 01/01/2026 đến ngày chạy theo Asia/Ho_Chi_Minh; sitemap không chứng minh đủ mọi bài trên website.
