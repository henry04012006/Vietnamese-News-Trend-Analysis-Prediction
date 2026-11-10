# Tăng tốc crawl Tuổi Trẻ ngày 07/11/2026

Hàng đợi đã tiếp tục lúc 20:30 với `config/tuoitre.fast.json`: 3 worker tải HTTP,
prefetch 6 URL, khoảng cách chung 0,25 giây giữa lượt bắt đầu request. Giữ một luồng
parse/ghi CSV/journal/report, cùng dữ liệu và checkpoint các tháng đang có.

## Số đo thực tế

| Cấu hình | Lượt xử lý | Thời gian | URL/giờ | So với baseline |
|---|---:|---:|---:|---:|
| 1 worker, 1 giây | 2.815 | 2.887,71 giây | 3.509 | 1,00× |
| 1 worker, 0,5 giây | 100 | 61,07 giây | 5.895 | 1,68× |
| 1 worker, 0,25 giây | 100 | 58,80 giây | 6.123 | 1,74× |
| 3 worker, 0,25 giây | 100 | 37,28 giây | **9.657** | **2,75×** |

Đây là tốc độ xử lý URL, gồm cả URL ngoài phạm vi hoặc lỗi, chưa phải số bài lưu/giờ.
Các đợt dùng những URL tiếp theo trong cùng manifest; thời gian phản hồi và layout có thể khác.
Đợt song song lưu 94 bài, có 1 lỗi category được ghi log, 5 kết quả ngoài scope/ngày.
Tổng CSV sau benchmark: 3.755 bài, còn 3.289 URL chưa xử lý trong manifest tháng 1.
Không suy ra thời gian hoàn tất cả năm chỉ từ một đợt thử 100 URL.

Tốc độ tuần tự tăng ít khi giảm từ 0,5 xuống 0,25 giây vì còn thời gian chờ phản hồi.
Các worker chồng thời gian tải, mỗi worker dùng session riêng. Pacer chung áp dụng cho
cả request đầu, retry và redirect; tối đa 4 lượt bắt đầu/giây cho toàn bộ worker,
hoặc thấp hơn khi robots yêu cầu crawl-delay lớn hơn.

## Kiểm chứng

- `python -m pytest -q`: **39 passed**, gồm concurrency có giới hạn, một writer,
  pacing chung, access stop và 429 trả về lúc đang đóng prefetch.
- Tám checks trên dữ liệu thật PASS: checkpoint/quota, hash phần CSV cũ, hash manifest,
  URL/ID duy nhất, trường bắt buộc, số bài append và không HTTP access block.
- Runtime evidence: `data/tuoitre/monthly/rapid_speed_validation.json`.
- Queue tải trước hữu hạn: benchmark có thể tải thêm tối đa 6 URL ngoài 100 lượt đã xử lý.
  Những response chưa ghi vẫn pending và được xử lý lại khi resume.
- HTTP 401/403/429 hoặc robots từ chối dừng toàn lượt, hủy việc chưa chạy và giữ checkpoint.
  Lỗi layout/category từng bài tiếp tục được giữ trong journal để rà soát.

## Tiếp tục và theo dõi

```powershell
python crawl_tuoitre_monthly.py --config config/tuoitre.fast.json
```

Chỉ chạy khi tiến trình hiện tại đã dừng. Hàng đợi tiếp tục cùng phạm vi
01/01/2026–07/11/2026 và cùng thư mục CSV, tự chuyển tháng khi hết manifest.
Config gốc `tuoitre.json` giữ delay 1 giây, một worker; các giá trị nhanh nằm trong
config kế thừa. Config benchmark có quota 100, không dùng để chạy toàn hàng đợi.

Xem [hướng dẫn theo tháng](tuoitre_monthly_crawl.md) để kiểm tra PID/report và vị trí CSV.
Tối ưu này không chứng minh sitemap bao phủ toàn bộ website; vẫn cần rà soát các URL lỗi
và độ phủ ngày/chuyên mục sau crawl.
