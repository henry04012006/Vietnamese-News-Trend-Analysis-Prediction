# Tăng tốc tải Tuổi Trẻ có giới hạn chung

## Phase 0: Input Clarification

Người dùng yêu cầu hoàn tất nhanh nhất có thể. Đã đo tuần tự: 1 giây ~3509 URL/giờ,
0,5 giây ~5895, 0,25 giây ~6123. Cần chồng thời gian chờ mạng, giữ ghi CSV một luồng.

## Phase 1: Requirements Analysis (EARS)

- Khi tải song song, giới hạn số worker và prefetch theo config (thử 3 worker, 6 future).
- Khi bắt đầu request/retry/redirect, tất cả worker phải chia sẻ một pacer, tối thiểu 0,25 giây hoặc crawl-delay lớn hơn.
- Khi gặp StopCrawl, ngăn request mới, hủy queue chưa chạy; giữ kết quả đã ghi và checkpoint.
- Khi xử lý kết quả, chỉ main thread parse/store/report; body phản hồi chỉ giữ trong số future hữu hạn.
- Khi resume/cache/scope không cần tải, không submit URL đó. Các bài đã lưu không mất hoặc trùng.

## Phase 2: Specification

| Cách làm | Ưu điểm | Hạn chế | Phức tạp | Truy cập | Chọn |
|---|---|---|---|---|---|
| 3 worker + pacer chung + writer chính | Che độ trễ HTTP, reuse parser/checkpoint | Cần cancel và bounded queue | Vừa | Tối đa 4 request/giây | Có |
| Chỉ giảm delay nữa | Ít thay đổi | Đã đo lợi ích nhỏ, dễ tạo burst | Thấp | Tăng trần không giúp độ trễ | Không |

| Edge case | Trigger | Xử lý | Rủi ro |
|---|---|---|---|
| 403/429/robots | Một worker bị từ chối | Shared stop event, dừng toàn lượt | Request tiếp sau chặn |
| Alias sau redirect | Hai URL trỏ một bài | Main writer dedup, bỏ future không cần | Ghi trùng |
| Benchmark hết limit | Main đã xử lý đủ quota | Hủy future chưa chạy; chỉ tối đa prefetch response có thể đã in-flight | Tải dư không giới hạn |
| Ctrl+C | Đang đợi future | Stop event + shutdown bounded pool, checkpoint | Hỏng CSV |

| Exception | Nguồn | Xử lý | Recovery |
|---|---|---|---|
| RequestException | Future | Main ghi lỗi từng URL | Resume như core |
| StopCrawl | Future | Propagate + shared stop | Xem report trước chạy tiếp |

Session riêng từng worker; RobotFileParser dùng chung sau bootstrap, chỉ đọc. Pacer lock chỉ giữ
trong phần cấp lượt bắt đầu request, không giữ khi tải body. Không tạo writer trong worker.

## Phase 3: Implementation Planning

1. Tests Red: concurrency/prefetch bound, single writer, global spacing và cancel.
2. Code Green: RequestPacer + DownloadPool, chỉ bật cho backfill với workers >1; sample giữ hành vi cũ.
3. Benchmark 100 lượt xử lý (có thể có thêm tối đa prefetch URL đã in-flight khi dừng), audit prefix/manifest/schema/dedup.
4. Chọn config nhanh nhất đã đạt kiểm tra, resume hàng đợi và công bố số đo thật.

Scope: crawl_tuoitre.py, config/tuoitre.json, config/tuoitre.fast.json, config/tuoitre.speedtest.json,
tests/test_tuoitre_parallel.py và tài liệu tối ưu. Tiếp tục cùng execution log của yêu cầu tăng tốc này.
