# Tăng tốc crawl Tuổi Trẻ

## Phase 0: Input Clarification

Người dùng yêu cầu cải thiện tốc độ. Giữ dataset/checkpoint, output theo tháng, thứ tự tuần tự,
robots và dừng 401/403/429. Không tăng số writer hoặc chạy nhiều tháng song song.

## Phase 1: Requirements Analysis (EARS)

- R1: Khi chạy mức nhanh, khoảng cách giữa request vẫn ít nhất 1 giây hoặc crawl-delay lớn hơn từ robots.
- R2: Khi một URL có ngày đăng đã xác minh từ tháng khác và nằm ngoài tháng hiện tại, bỏ request và ghi rõ bằng chứng cache.
- R3: Khi ngày cache nằm trong tháng đang crawl, vẫn tải nội dung; khi ngày mâu thuẫn/thiếu timezone, không dùng cache để loại URL.
- R4: Khi áp dụng, dừng có checkpoint, audit dữ liệu trước/sau rồi benchmark 100 URL mới trước khi resume hàng đợi.
- R5: Khi benchmark gặp chặn, giữ quy tắc dừng; không đổi IP hoặc tìm cách vượt chặn. Không nói nhanh gấp đôi nếu chưa đo.

## Phase 2: Specification

| Cách làm | Ưu điểm | Hạn chế | Phức tạp | Truy cập | Chọn |
|---|---|---|---|---|---|
| 1 giây/request + cache ngày giữa tháng | Tăng throughput, giảm request dư | Cần benchmark và metadata chắc chắn | Thấp | Giữ robots/stop | Có |
| Nhiều worker cùng host | Che được độ trễ | Tăng tải, phức tạp limiter/writer | Cao | Cần điều phối thêm | Không |

| Edge case | Điều kiện | Hành vi | Rủi ro |
|---|---|---|---|
| Cache trong tháng | Ngày hợp lệ đúng tháng | Tải lại body nếu chưa có | Mất nội dung |
| Cache mâu thuẫn | Cùng URL có hai ngày khác | Không skip | Bỏ nhầm bài |
| Journal khác chưa có dòng cuối | Dòng cuối viết dở | Chỉ đọc các dòng hoàn chỉnh, không sửa file nguồn | Hỏng journal |
| Đang có writer | Worker còn chạy | Dừng bằng Ctrl+C, đợi checkpoint/exit | Mất dữ liệu |

| Exception | Nguồn | Xử lý | Phục hồi |
|---|---|---|---|
| 403/429 | HTTP | Dừng như hiện tại | Xem log trước chạy tiếp |
| Metadata cache lỗi | JSON/date | Không dùng record không đủ bằng chứng | Vẫn tải URL |

Config chứa delay, journal globs, trạng thái cache được tin cậy, checkpoint cache và benchmark limit.
Cache chỉ dùng ngày đăng thực tế đã lưu, không suy luận từ URL/lastmod. Một writer như hiện tại.

## Phase 3: Implementation Planning

1. Tests Red/Green cho cache chỉ loại URL ngoài ngày, xung đột ngày và pacing/robots.
2. Dừng worker có checkpoint; audit CSV/journal. Thay delay config và code cache.
3. Benchmark 100 lượt request, đối chiếu tốc độ với baseline ~1788 URL/giờ; kiểm tra không block, không mất/trùng bài.
4. Resume monthly queue, cập nhật README/báo cáo với số đo thực tế.

Files: crawl_tuoitre.py, config/tuoitre.json, config/tuoitre.speedtest.json, tests/test_tuoitre_speed.py,
README.md, docs/tuoitre_speed_optimization.md.
