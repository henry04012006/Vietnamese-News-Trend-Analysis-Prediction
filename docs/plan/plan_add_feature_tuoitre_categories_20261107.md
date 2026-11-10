# Tuổi Trẻ — Crawl theo 18 chuyên mục chính thức

## Phase 0: Input Clarification

Người dùng yêu cầu dùng 18 chuyên mục đã được Tuổi Trẻ phân loại. Tiếp tục branch hiện tại,
chỉ crawl mẫu để xem trước, chưa chạy full. Giữ mẫu cũ để đối chiếu.

## Phase 1: Requirements Analysis (EARS)

- R1: Khi parse bài, lấy category chính thức từ breadcrumb hoặc article:section, không suy đoán từ nội dung.
- R2: Khi chạy category-sample, lấy URL từ từng trang chuyên mục được cung cấp; mục tiêu 2 bài hợp lệ/chuyên mục, tối đa 6 URL ứng viên/chuyên mục, đặt trong config.
- R3: Khi một bài hiện ở nhiều trang, giữ primary category của bài; không gán nhầm chuyên mục của sidebar/trang giới thiệu và không ghi trùng URL/ID.
- R4: Khi parse Video, dùng phần text mô tả/thân bài được xuất bản; không tạo transcript. Phân loại Video dựa URL chính thức /video/.
- R5: Khi lưu mẫu, báo cáo số hợp lệ/lỗi theo category, thiếu category phải bị phát hiện; giữ khả năng resume.

## Phase 2: Specification

| Cách làm | Ưu điểm | Hạn chế | Độ phức tạp | Truy cập | Chọn |
|---|---|---|---|---|---|
| Trang chuyên mục + breadcrumb/meta | Dùng nhãn do nguồn cung cấp, đủ nhóm mẫu | Một bài có thể được giới thiệu ở nhiều nhóm | Thấp | HTTP công khai, robots | Có |
| Tự phân loại bằng nội dung | Không phụ thuộc HTML | Không đáp ứng yêu cầu dùng nhãn nguồn | Cao | Thêm model | Không |

| Edge case | Điều kiện | Xử lý | Rủi ro |
|---|---|---|---|
| Cross-listing | Trang giới thiệu khác primary category | Ghi nhận mismatch, thử URL tiếp trong giới hạn | Nhãn sai |
| Video | Không có body text ngoài sapo | Giữ mô tả được đăng, không bịa transcript | Nội dung giả |
| Category không nhận diện | Meta/breadcrumb thiếu hoặc ngoài danh sách | Ghi lỗi | Ô trống âm thầm |
| Resume | CSV cũ chưa có category | Dùng output riêng cho mẫu mới | Bỏ qua dữ liệu lỗi |

| Exception | Nguồn | Xử lý | Phục hồi |
|---|---|---|---|
| HTTP/robots/chặn | Mạng | Giữ chính sách Client hiện tại | Chạy lại có log |
| Parse category/body | HTML | Ghi lỗi URL, không thay nhãn bằng suy đoán | Kiểm tra mẫu |

Không thêm writer đồng thời; dùng khóa hiện có. Config chứa danh sách tên/URL/aliases,
selectors, quota và tên file. Thêm CLI category-sample; sample/backfill có category chính thức.
Backfill lịch sử tiếp tục tìm URL qua sitemap rồi đọc nhãn từng bài, chưa khẳng định 18 trang đầu phủ toàn bộ lịch sử.

## Phase 3: Implementation Planning

1. Tests Red/Green cho category breadcrumb/meta và Video text; verify python -m pytest -q.
2. Tests Red/Green cho discovery đủ chuyên mục, quota, cross-listing/resume; verify cùng lệnh.
3. Chạy category-sample, kiểm tra CSV có đủ 18 nhóm, đối chiếu bài thật và giữ lỗi công khai.
4. Cập nhật README/báo cáo, review. Bàn giao mẫu; chưa chạy full.

Files: crawl_tuoitre.py, config/tuoitre.json, tests/test_tuoitre.py, README.md, docs/tuoitre_category_sample_review.md.
